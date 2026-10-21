"""Minimal lpunpack: list or extract logical partitions from an Android super image.

Usage:
    python scripts/lpunpack.py dumps/full/lun0/super.bin            # list
    python scripts/lpunpack.py dumps/full/lun0/super.bin OUT [names] # extract (non-empty only)
"""
import os
import struct
import sys

SECTOR = 512
GEOMETRY_OFFSET = 4096
GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030


def read_metadata(f, slot=0):
    f.seek(GEOMETRY_OFFSET)
    geo = f.read(4096)
    magic, _, = struct.unpack_from("<II", geo, 0)
    if magic != GEOMETRY_MAGIC:
        sys.exit("not a super image (bad geometry magic)")
    meta_max, slot_count, block_size = struct.unpack_from("<III", geo, 40)

    base = GEOMETRY_OFFSET + 2 * 4096 + slot * meta_max
    f.seek(base)
    hdr = f.read(meta_max)
    magic, major, minor, hdr_size = struct.unpack_from("<IHHI", hdr, 0)
    if magic != HEADER_MAGIC:
        sys.exit("bad metadata header magic")
    tables_size = struct.unpack_from("<I", hdr, 44)[0]
    descs = [struct.unpack_from("<III", hdr, 80 + 12 * i) for i in range(4)]
    tables = hdr[hdr_size:hdr_size + tables_size]

    def entries(desc):
        off, num, size = desc
        return [tables[off + i * size: off + (i + 1) * size] for i in range(num)]

    groups = [e[:36].rstrip(b"\0").decode() for e in entries(descs[2])]
    extents = [struct.unpack_from("<QIQI", e) for e in entries(descs[1])]
    parts = []
    for e in entries(descs[0]):
        name = e[:36].rstrip(b"\0").decode()
        attrs, first, num, group = struct.unpack_from("<IIII", e, 36)
        exts = extents[first:first + num]
        size = sum(x[0] for x in exts) * SECTOR
        parts.append({"name": name, "attrs": attrs, "group": groups[group],
                      "extents": exts, "size": size})
    info = {"version": f"{major}.{minor}", "slots": slot_count,
            "block_size": block_size, "groups": groups}
    return info, parts


def extract(f, part, out_path):
    with open(out_path, "wb") as o:
        for num_sectors, target_type, target_data, _ in part["extents"]:
            if target_type == 0:  # LP_TARGET_TYPE_LINEAR
                f.seek(target_data * SECTOR)
                left = num_sectors * SECTOR
                while left:
                    chunk = f.read(min(left, 1 << 24))
                    o.write(chunk)
                    left -= len(chunk)
            else:  # LP_TARGET_TYPE_ZERO
                o.seek(num_sectors * SECTOR, 1)
        o.truncate()


def main():
    with open(sys.argv[1], "rb") as f:
        info, parts = read_metadata(f)
        print(f"LP metadata v{info['version']}, {info['slots']} slots, groups: {', '.join(info['groups'])}")
        for p in parts:
            print(f"  {p['name']:<24} {p['size'] / 2**20:10.1f} MiB  group={p['group']}  extents={len(p['extents'])}")
        if len(sys.argv) > 2:
            out = sys.argv[2]
            wanted = set(sys.argv[3:])
            os.makedirs(out, exist_ok=True)
            for p in parts:
                if p["size"] and (not wanted or p["name"] in wanted):
                    path = os.path.join(out, p["name"] + ".img")
                    print("extracting", path)
                    extract(f, p, path)


if __name__ == "__main__":
    main()
