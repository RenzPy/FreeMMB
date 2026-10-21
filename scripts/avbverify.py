"""Check partition images against the AVB hashtree descriptors in a vbmeta image.

Usage:
    python scripts/avbverify.py VBMETA name=IMAGE [name=IMAGE ...]
    python scripts/avbverify.py dumps/full/lun0/vbmeta_system_b.bin system=dumps/super/system_b.img

Recomputes every data-block hash and the root digest, so it tells you whether an image
is byte-identical to what the vbmeta was signed over (data area only; FEC is not checked).
"""
import hashlib
import struct
import sys

TAG_HASHTREE, TAG_HASH, TAG_CHAIN = 1, 2, 4


def descriptors(vbmeta):
    if vbmeta[:4] != b"AVB0":
        sys.exit("not a vbmeta image")
    auth_size, aux_size = struct.unpack_from(">QQ", vbmeta, 12)
    desc_off, desc_size = struct.unpack_from(">QQ", vbmeta, 96)
    flags = struct.unpack_from(">I", vbmeta, 120)[0]
    aux = vbmeta[256 + auth_size: 256 + auth_size + aux_size]
    pos, out = desc_off, []
    while pos < desc_off + desc_size:
        tag, n = struct.unpack_from(">QQ", aux, pos)
        body = aux[pos + 16: pos + 16 + n]
        if tag == TAG_HASHTREE:
            (_, image_size, tree_off, tree_size, data_bs, hash_bs, _, _, _) = struct.unpack_from(">IQQQIIIQQ", body, 0)
            alg = body[56:88].rstrip(b"\0").decode()
            name_len, salt_len, digest_len, _ = struct.unpack_from(">IIII", body, 88)
            p = 88 + 16 + 60
            name = body[p:p + name_len].decode()
            salt = body[p + name_len:p + name_len + salt_len]
            root = body[p + name_len + salt_len:p + name_len + salt_len + digest_len]
            out.append({"kind": "hashtree", "name": name, "image_size": image_size, "tree_offset": tree_off,
                        "tree_size": tree_size, "block": data_bs, "hash_block": hash_bs, "alg": alg,
                        "salt": salt, "root": root})
        elif tag == TAG_HASH:
            image_size = struct.unpack_from(">Q", body, 0)[0]
            alg = body[8:40].rstrip(b"\0").decode()
            name_len, salt_len, digest_len = struct.unpack_from(">III", body, 40)
            p = 40 + 16 + 60
            name = body[p:p + name_len].decode()
            salt = body[p + name_len:p + name_len + salt_len]
            digest = body[p + name_len + salt_len:p + name_len + salt_len + digest_len]
            out.append({"kind": "hash", "name": name, "image_size": image_size, "alg": alg,
                        "salt": salt, "digest": digest})
        elif tag == TAG_CHAIN:
            _, name_len, _ = struct.unpack_from(">III", body, 0)
            out.append({"kind": "chain", "name": body[76:76 + name_len].decode()})
        pos += 16 + n
    return flags, out


def verify_hashtree(d, path):
    bs, hbs = d["block"], d["hash_block"]
    h = lambda data: hashlib.new(d["alg"], d["salt"] + data).digest()
    dsize = len(h(b""))
    padded = 1 << (dsize - 1).bit_length()
    with open(path, "rb") as f:
        level, n = [], 0
        while n < d["image_size"]:
            level.append(h(f.read(bs)))
            n += bs
        f.seek(d["tree_offset"])
        stored = f.read(d["tree_size"])

    def pack(hashes):
        per = hbs // padded
        blocks = []
        for i in range(0, len(hashes), per):
            blk = b"".join(x.ljust(padded, b"\0") for x in hashes[i:i + per])
            blocks.append(blk.ljust(hbs, b"\0"))
        return blocks

    levels = []
    cur = pack(level)
    while True:
        levels.append(b"".join(cur))
        if len(cur) == 1:
            break
        cur = pack([h(b) for b in cur])
    root = h(levels[-1])
    tree = b"".join(reversed(levels))  # avbtool stores the top level first
    return root == d["root"], tree == stored[:len(tree)]


def main():
    flags, descs = descriptors(open(sys.argv[1], "rb").read())
    images = dict(a.split("=", 1) for a in sys.argv[2:])
    print(f"vbmeta flags={flags}")
    for d in descs:
        line = f"  {d['kind']:<9} {d['name']}"
        if d["name"] in images and d["kind"] == "hashtree":
            root_ok, tree_ok = verify_hashtree(d, images[d["name"]])
            line += f"  root={'OK' if root_ok else 'MISMATCH'}  stored-tree={'OK' if tree_ok else 'MISMATCH'}"
        elif d["name"] in images and d["kind"] == "hash":
            data = open(images[d["name"]], "rb").read(d["image_size"])
            ok = hashlib.new(d["alg"], d["salt"] + data).digest() == d["digest"]
            line += f"  digest={'OK' if ok else 'MISMATCH'}"
        print(line)


if __name__ == "__main__":
    main()
