# Custom boot animation

The box plays `/bootanimation.zip` from its `persist` partition before anything in
`/system` loads. It's a standard Android bootanimation: a folder of JPEG frames per part,
plus a `desc.txt` describing resolution, frame rate and playback.

`scripts/bootanimation_tool.py` builds one from any video and installs it by overwriting
the existing file's data blocks directly over EDL — no root, no app, no code running on
the device, and no change to the filesystem's own bookkeeping.

On this board, the stock file is 2660×802 at 24 fps, matching the panel; `apks/` has a
worked example built from a video at that resolution (`bootanimation_2660x802.zip`, with
`bootanimation_preview.mp4` as the same frames reassembled so you can watch it without a
device). Find your own board's numbers from `desc.txt` inside the current zip (step 1
below) rather than assuming these.

## 1. Read the current file and its size

```
python -I scripts/ext4extract.py persist.bin cat /bootanimation.zip > current.zip
```
(`persist.bin` is a full read of the persist partition — `edl.ps1 rs <start> <count>`, or
see the main README's "Stock backup" section for a ready-made dump of the whole board.)

Unzip `current.zip` and read `desc.txt` for its `WIDTH HEIGHT FPS`, and note its exact
byte size — the replacement has to match it.

## 2. Build a same-size replacement

```
python -I scripts/bootanimation_tool.py build your-video.mp4 new.zip \
    --width 2660 --height 802 --fps 24 --max-size <size of current.zip>
```

This scales the video to the panel's width, center-crops to its height, and tries
decreasing JPEG quality until the result fits `--max-size`, then pads it with a dummy
zip entry to land on that size exactly. The animation plays once and holds on its last
frame — a few seconds of intro followed by a static logo or title card works well, since
Android keeps booting underneath it regardless of how long that takes.

Check the result before writing anything — `unzip -l new.zip`, or turn the frames back
into a video with ffmpeg to watch it.

## 3. Generate the write plan

```
python -I scripts/bootanimation_tool.py plan persist.bin /bootanimation.zip new.zip out/ \
    --base-sector 8
```

This looks up the file's on-disk block ranges inside the ext4 image and writes
`out/apply.ps1`: one `edl.ps1 ws` per range, a read-back (`edl.ps1 rs`) of each, and a
hash comparison. `--base-sector` is where that partition starts on the LUN, in
4096-byte units (`edl.ps1 printgpt`, or a `rawprogram*.xml`, will tell you; it's `8` for
this board's `persist`).

Read `out/apply.ps1` before running it. It only touches the exact bytes belonging to the
one file you named — nothing else on the partition.

## 4. Write it

Put the box in EDL (see the main README), then from the repo root:

```powershell
.\out\apply.ps1
```

Each block run prints `OK` once its read-back matches what was written. Reboot normally
afterward (`edl.ps1 reset`, or unplug and plug back in).

## Why overwrite in place instead of resizing the file

Growing or shrinking a file means updating the filesystem's own bookkeeping — inode size,
block allocation, free-space bitmaps — which is more moving parts and more ways to get
wrong on a filesystem you can't `fsck` afterward from this toolchain. Matching the
original size means only the file's existing data blocks change: its directory entry,
inode and allocation stay untouched, and the read-back check catches any USB hiccup
during the write immediately, against the exact bytes that were sent. If your build would
be larger than the current file even at the lowest usable quality, shorten the clip or
drop the frame rate rather than trying to grow it in place.
