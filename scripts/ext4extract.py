"""Read-only ext4 image reader: list or extract files without mounting.

Usage:
    python scripts/ext4extract.py IMAGE ls [PATH]
    python scripts/ext4extract.py IMAGE cat PATH
    python scripts/ext4extract.py IMAGE extract OUTDIR [PATH]

Handles extents, legacy block maps, inline data and symlinks. Symlinks are written as
small text files named NAME.symlink, since Windows cannot create them unprivileged.
"""
import os
import struct
import sys

S_IFMT, S_IFDIR, S_IFREG, S_IFLNK = 0o170000, 0o040000, 0o100000, 0o120000
EXT4_EXTENTS_FL, EXT4_INLINE_DATA_FL = 0x80000, 0x10000000


class Ext4:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.f.seek(1024)
        sb = self.f.read(1024)
        if struct.unpack_from("<H", sb, 0x38)[0] != 0xEF53:
            raise ValueError("not ext4")
        self.block_size = 1024 << struct.unpack_from("<I", sb, 0x18)[0]
        self.blocks_per_group = struct.unpack_from("<I", sb, 0x20)[0]
        self.inodes_per_group = struct.unpack_from("<I", sb, 0x28)[0]
        self.inode_size = struct.unpack_from("<H", sb, 0x58)[0]
        self.first_data_block = struct.unpack_from("<I", sb, 0x14)[0]
        incompat = struct.unpack_from("<I", sb, 0x60)[0]
        self.is64 = bool(incompat & 0x80)
        self.desc_size = struct.unpack_from("<H", sb, 0xFE)[0] if self.is64 else 32
        self.volume_name = sb[0x78:0x88].rstrip(b"\0").decode(errors="replace")
        self.last_mounted = sb[0x88:0xC8].rstrip(b"\0").decode(errors="replace")
        self._gd_cache = {}

    def read_block(self, n, count=1):
        self.f.seek(n * self.block_size)
        return self.f.read(self.block_size * count)

    def inode_table(self, group):
        if group not in self._gd_cache:
            gd_block = self.first_data_block + 1
            off = gd_block * self.block_size + group * self.desc_size
            self.f.seek(off)
            d = self.f.read(self.desc_size)
            lo = struct.unpack_from("<I", d, 8)[0]
            hi = struct.unpack_from("<I", d, 0x28)[0] if self.desc_size >= 64 else 0
            self._gd_cache[group] = lo | (hi << 32)
        return self._gd_cache[group]

    def inode(self, ino):
        group, index = divmod(ino - 1, self.inodes_per_group)
        self.f.seek(self.inode_table(group) * self.block_size + index * self.inode_size)
        raw = self.f.read(self.inode_size)
        mode = struct.unpack_from("<H", raw, 0)[0]
        size = struct.unpack_from("<I", raw, 4)[0] | (struct.unpack_from("<I", raw, 0x6C)[0] << 32)
        flags = struct.unpack_from("<I", raw, 0x20)[0]
        return {"ino": ino, "mode": mode, "size": size, "flags": flags, "block": raw[0x28:0x28 + 60],
                "uid": struct.unpack_from("<H", raw, 2)[0], "gid": struct.unpack_from("<H", raw, 0x18)[0]}

    def _extent_runs(self, node):
        magic, entries, _, depth = struct.unpack_from("<HHHH", node, 0)
        if magic != 0xF30A:
            raise ValueError("bad extent header")
        for i in range(entries):
            e = node[12 + 12 * i: 24 + 12 * i]
            if depth == 0:
                lblk, length, hi, lo = struct.unpack("<IHHI", e)
                if length > 32768:  # uninitialized extent reads as zeros
                    yield lblk, length - 32768, None
                else:
                    yield lblk, length, lo | (hi << 32)
            else:
                _, lo, hi = struct.unpack("<IIH", e[:10])
                yield from self._extent_runs(self.read_block(lo | (hi << 32)))

    def _blockmap_runs(self, block):
        ptrs = struct.unpack("<15I", block)
        per = self.block_size // 4
        lblk = 0

        def walk(b, level):
            nonlocal lblk
            if level == 0:
                if b:
                    yield lblk, 1, b
                lblk += 1
                return
            if not b:
                lblk += per ** level
                return
            for p in struct.unpack(f"<{per}I", self.read_block(b)):
                yield from walk(p, level - 1)

        for p in ptrs[:12]:
            yield from walk(p, 0)
        for level, p in enumerate(ptrs[12:], start=1):
            yield from walk(p, level)

    def read(self, inode):
        size = inode["size"]
        if inode["flags"] & EXT4_INLINE_DATA_FL:
            return inode["block"][:size]
        if (inode["mode"] & S_IFMT) == S_IFLNK and size < 60 and not inode["flags"] & EXT4_EXTENTS_FL:
            return inode["block"][:size]
        runs = (self._extent_runs(inode["block"]) if inode["flags"] & EXT4_EXTENTS_FL
                else self._blockmap_runs(inode["block"]))
        out = bytearray(size)
        bs = self.block_size
        for lblk, length, pblk in runs:
            start = lblk * bs
            if start >= size:
                continue
            n = min(length * bs, size - start)
            if pblk is not None:
                out[start:start + n] = self.read_block(pblk, length)[:n]
        return bytes(out)

    def listdir(self, inode):
        data = self.read(inode)
        pos, entries = 0, []
        while pos + 8 <= len(data):
            ino, rec_len, name_len, ftype = struct.unpack_from("<IHBB", data, pos)
            if rec_len < 8:
                break
            if ino:
                name = data[pos + 8: pos + 8 + name_len].decode(errors="replace")
                if name not in (".", ".."):
                    entries.append((name, ino))
            pos += rec_len
        return entries

    def lookup(self, path):
        node = self.inode(2)
        for part in [p for p in path.strip("/").split("/") if p]:
            match = dict(self.listdir(node)).get(part)
            if match is None:
                raise FileNotFoundError(path)
            node = self.inode(match)
        return node

    def walk(self, inode, prefix=""):
        for name, ino in sorted(self.listdir(inode)):
            child = self.inode(ino)
            path = f"{prefix}/{name}"
            yield path, child
            if (child["mode"] & S_IFMT) == S_IFDIR:
                yield from self.walk(child, path)


def main():
    img, cmd = sys.argv[1], sys.argv[2]
    fs = Ext4(img)
    if cmd == "ls":
        node = fs.lookup(sys.argv[3] if len(sys.argv) > 3 else "/")
        for name, ino in sorted(fs.listdir(node)):
            i = fs.inode(ino)
            kind = {S_IFDIR: "d", S_IFLNK: "l"}.get(i["mode"] & S_IFMT, "-")
            print(f"{kind} {i['size']:>10}  {name}")
    elif cmd == "cat":
        sys.stdout.buffer.write(fs.read(fs.lookup(sys.argv[3])))
    elif cmd == "extract":
        out = sys.argv[3]
        root_path = sys.argv[4] if len(sys.argv) > 4 else "/"
        root = fs.lookup(root_path)
        count = 0
        for path, node in fs.walk(root, root_path.rstrip("/")):
            dest = os.path.join(out, path.lstrip("/"))
            kind = node["mode"] & S_IFMT
            if kind == S_IFDIR:
                os.makedirs(dest, exist_ok=True)
            elif kind == S_IFREG:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as o:
                    o.write(fs.read(node))
                count += 1
            elif kind == S_IFLNK:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest + ".symlink", "wb") as o:
                    o.write(fs.read(node))
        print(f"extracted {count} files to {out}")


if __name__ == "__main__":
    main()
