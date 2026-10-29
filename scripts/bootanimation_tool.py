"""Build and install a custom Android bootanimation.zip from any video, including
replacing one in place on a live partition image with no root and no code running on
the device — only a byte-for-byte EDL write of the file's existing data blocks.

Requires ffmpeg on PATH (or pass --ffmpeg). Run with `python -I`.

Commands
--------

build: encode a video into a bootanimation.zip sized to fit a target byte budget.

    python scripts/bootanimation_tool.py build input.mp4 out.zip \
        --width 2660 --height 802 --fps 24 --max-size 8579441

  Scales to WIDTH wide, center-crops to WIDTH x HEIGHT, tries decreasing JPEG quality
  until the zip fits --max-size (if given), then pads it with a dummy stored entry to
  land on exactly that size. Omit --max-size to just use --quality (default 8) with no
  padding, e.g. when installing into free space rather than overwriting a same-size file.

plan: given a partition image and the path of the file you're replacing inside it, work
out its on-disk block ranges and emit ready-to-run EDL commands that overwrite them with
a same-size replacement file, plus a read-back check for each range.

    python scripts/bootanimation_tool.py plan persist.bin /bootanimation.zip new.zip out_dir \
        --base-sector 8

  --base-sector is the partition's start, in 4096-byte units, as `edl.ps1 printgpt` (or
  `rawprogram*.xml`) reports it for the LUN the image came from. This repo's persist
  partition is at sector 8. The replacement file must be exactly the same size as the
  original (use `build --max-size` to arrange that) — this tool only overwrites existing
  data blocks, it does not resize the file or touch filesystem metadata.

  Writes out_dir/apply.ps1: one `edl.ps1 ws` per block run, a read-back `edl.ps1 rs` of
  each range into out_dir/verify_*.bin, and a comparison against the chunk that was
  written. Review it, then run it from the repo root with the box in EDL mode.
"""
import argparse
import os
import struct
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ext4extract import Ext4, EXT4_EXTENTS_FL  # noqa: E402

BLOCK = 4096


def runs(fs, ino):
    """(logical_block, count, physical_block) triples covering the whole file."""
    if ino["flags"] & EXT4_EXTENTS_FL:
        return list(fs._extent_runs(ino["block"]))
    return list(fs._blockmap_runs(ino["block"]))


def ffmpeg_frames(ffmpeg, video, outdir, width, height, fps, quality):
    # subprocess/CreateProcess on Windows won't resolve a relative path with forward
    # slashes against PATH the way a shell does, so make it absolute if it looks local.
    if os.path.sep in ffmpeg or "/" in ffmpeg:
        ffmpeg = os.path.abspath(ffmpeg)
    vf = (
        f"scale={width}:-2:flags=lanczos+accurate_rnd,"
        f"crop={width}:{height}:0:(ih-{height})/2,"
        "unsharp=5:5:0.5:5:5:0.0"
    )
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", video, "-an", "-vf", vf,
         "-q:v", str(quality), "-pix_fmt", "yuvj420p", os.path.join(outdir, "%04d.jpg")],
        check=True,
    )


def make_zip(framedir, width, height, fps, pad_to=None):
    frames = sorted(f for f in os.listdir(framedir) if f.endswith(".jpg"))
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("desc.txt", f"{width} {height} {fps}\np 1 0 part0\n")
        for f in frames:
            z.write(os.path.join(framedir, f), "part0/" + f)
    data = buf.getvalue()
    if pad_to is not None:
        pad = pad_to - len(data) - 200  # headroom for the pad entry's own zip overhead
        if pad < 0:
            return None
        buf2 = io.BytesIO()
        with zipfile.ZipFile(buf2, "w", zipfile.ZIP_STORED) as z:
            z.writestr("desc.txt", f"{width} {height} {fps}\np 1 0 part0\n")
            for f in frames:
                z.write(os.path.join(framedir, f), "part0/" + f)
            z.writestr("pad/pad.bin", b"\0" * max(pad, 0))
        data = buf2.getvalue()
        if len(data) != pad_to:
            # one more correction pass now that we know the exact overhead
            pad += pad_to - len(data)
            buf3 = io.BytesIO()
            with zipfile.ZipFile(buf3, "w", zipfile.ZIP_STORED) as z:
                z.writestr("desc.txt", f"{width} {height} {fps}\np 1 0 part0\n")
                for f in frames:
                    z.write(os.path.join(framedir, f), "part0/" + f)
                z.writestr("pad/pad.bin", b"\0" * max(pad, 0))
            data = buf3.getvalue()
    return data


def cmd_build(a):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        if a.max_size:
            for q in range(a.quality, 32):
                ffmpeg_frames(a.ffmpeg, a.video, tmp, a.width, a.height, a.fps, q)
                data = make_zip(tmp, a.width, a.height, a.fps, pad_to=a.max_size)
                if data is not None:
                    print(f"quality {q} fits: {len(data)} bytes (target {a.max_size})")
                    break
            else:
                sys.exit(f"could not fit under {a.max_size} bytes even at lowest quality")
        else:
            ffmpeg_frames(a.ffmpeg, a.video, tmp, a.width, a.height, a.fps, a.quality)
            data = make_zip(tmp, a.width, a.height, a.fps)
            print(f"built {len(data)} bytes at quality {a.quality}, no size target")
        open(a.out, "wb").write(data)
    z = zipfile.ZipFile(a.out)
    assert z.testzip() is None, "zip failed its own integrity check"
    nframes = sum(1 for n in z.namelist() if n.startswith("part0/") and n.endswith(".jpg"))
    print(f"wrote {a.out}: {nframes} frames, {os.path.getsize(a.out)} bytes")


def cmd_plan(a):
    fs = Ext4(a.image)
    ino = fs.lookup(a.path)
    rs = runs(fs, ino)
    repl = open(a.replacement, "rb").read()
    if len(repl) != ino["size"]:
        sys.exit(
            f"{a.replacement} is {len(repl)} bytes, but {a.path} is {ino['size']} bytes. "
            "In-place overwrite needs an exact size match — pad the replacement first "
            "(see `build --max-size`)."
        )
    os.makedirs(a.outdir, exist_ok=True)
    lines = [
        "# Generated by bootanimation_tool.py plan. Review before running.",
        "# Run from the repo root with the box in EDL mode (see README.md).",
        "",
    ]
    for i, (lblk, count, pblk) in enumerate(rs):
        start = lblk * BLOCK
        chunk = repl[start:start + count * BLOCK]
        chunk_path = os.path.join(a.outdir, f"chunk_{i:02d}.bin")
        open(chunk_path, "wb").write(chunk)
        sector = a.base_sector + pblk
        verify_path = os.path.join(a.outdir, f"verify_{i:02d}.bin")
        lines += [
            f"# run {i}: logical block {lblk}, {count} blocks, physical block {pblk}",
            f".\\scripts\\edl.ps1 ws {sector} \"{chunk_path}\" --lun=0 --memory=ufs",
            f".\\scripts\\edl.ps1 rs {sector} {count} \"{verify_path}\" --lun=0 --memory=ufs",
            f"if ((Get-FileHash \"{chunk_path}\").Hash -eq (Get-FileHash \"{verify_path}\").Hash) "
            f"{{ Write-Host 'run {i}: OK' }} else {{ Write-Host 'run {i}: MISMATCH' -ForegroundColor Red }}",
            "",
        ]
    script_path = os.path.join(a.outdir, "apply.ps1")
    open(script_path, "w", newline="\n").write("\n".join(lines))
    print(f"{len(rs)} block run(s) covering {sum(c for _, c, _ in rs) * BLOCK} bytes")
    print(f"wrote {script_path} — read it, then run it from the repo root")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("video")
    b.add_argument("out")
    b.add_argument("--width", type=int, required=True)
    b.add_argument("--height", type=int, required=True)
    b.add_argument("--fps", type=int, default=24)
    b.add_argument("--max-size", type=int, default=None, help="pad/shrink to exactly this many bytes")
    b.add_argument("--quality", type=int, default=8, help="starting ffmpeg -q:v (lower = better); ignored search start when --max-size is set")
    b.add_argument("--ffmpeg", default="ffmpeg")
    b.set_defaults(func=cmd_build)

    pl = sub.add_parser("plan")
    pl.add_argument("image", help="raw partition image, e.g. a persist dump")
    pl.add_argument("path", help="path inside the image, e.g. /bootanimation.zip")
    pl.add_argument("replacement", help="same-size file to write in its place")
    pl.add_argument("outdir")
    pl.add_argument("--base-sector", type=int, default=8, help="partition start, in 4096-byte units (8 for this repo's persist partition)")
    pl.set_defaults(func=cmd_plan)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
