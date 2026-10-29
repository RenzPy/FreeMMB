# Proposal: a persistent, read-only hardening hook

**Status: design only — not built or flashed.** The two problems this was originally meant
to solve are now handled without any hook at all: `docs/adb-access.md` covers getting a
shell with nothing flashed, and `docs/boot-animation.md` covers a custom boot animation
with nothing flashed. What's left below — a firewall for the hard-coded phone-home
servers found in `docs/security-audit.md`, closing the dormant `doShell` root channel, and
a one-off traffic capture to confirm exactly what a drive sends — all need code running on
the device at boot, so they're left here as a design for anyone who wants to build and
flash it.

## How it would be wired

- `/system/bin/z-sender.sh` runs at every boot and, near the end, does `sh
  /mnt/vendor/persist/boot*&` — a glob that today matches nothing, since no file on
  `persist` starts with `boot` except `bootanimation.zip` (not a shell script). Patching
  one line of that file (identical patch mechanism to the EDL writes used elsewhere in
  this repo — see `docs/recon.md`) to add a fixed second filename, e.g.
  `sh /mnt/vendor/persist/boot.sh /mnt/vendor/persist/boot*&`, is the only change to
  `z-sender.sh` this needs; it runs `boot.sh` if present and is a no-op otherwise.
- `boot.sh` itself would be written directly to free blocks on `persist` over EDL — no
  ADB, no app, nothing executed on the device to install it, the same way
  `docs/boot-animation.md` installs a file. Its contents are fixed at write time, so
  there is no path by which anything later on the device (an app, a USB stick, an OTA)
  could change what it does.

## What `boot.sh` does (fixed content, no external scripts)

| Area | Action | When |
|---|---|---|
| CPU | `scaling_min_freq` 300 MHz on both clusters, re-checked every 60 s | always |
| Firewall | `iptables -I OUTPUT -d <ip> -j DROP` for 120.77.203.18, 47.92.37.111 (goodocom licence), 119.91.73.132 (zlink activation), 120.24.79.21 (SharkCarPlay activation) | after `netd` is up |
| DNS block | bind-mount a hosts file over `/system/etc/hosts`: stock Tesla lines plus goodocom, Bugly/qq, QWeather, the sudingtech and xiaoqiangzhineng OSS buckets | at boot |
| Back door | root-owned mode-000 directory at `/data/android_shell_command.sh`, so `doShell` can't run anything | at boot |
| Audio quality | `setprop af.resampler.quality 7` (dynamic high quality, applies to new tracks) | at boot |
| Audio capture (one-off) | `setprop sys.lynx.shark.dump_tinycap 1` for the first 25 s of CarPlay audio, then off; keep the SharkCarPlay `audioFormats`/`compressionType` log lines | first 3 boots only |
| Traffic capture (one-off) | `tcpdump -i any -w /mnt/vendor/persist/zdbg/cap.pcap` for 10 min, size-capped | first 3 boots only |

Not included: the USB gadget, GPIO or ADB takeover (CarPlay works normally), wallpaper, or
anything that runs files from `/data` or USB.

## Reading the results

Plug the box into the PC, enter EDL, read the persist partition
(`.\scripts\edl.ps1 r persist dumps\persist.bin`), and on the PC extract `zdbg/`:

- `cap.pcap`: open in Wireshark to see every server contacted during the drive.
- `/sdcard/.debug` copy of `tinycap.pcm` and the log lines: shows what the car receives and
  whether the car negotiated PCM or AAC-LC.

## Open questions before building

- Check that `iptables`, `tcpdump` and `mount --bind` work from z-sender's context
  (SELinux is Permissive, so likely yes).
- The size cap on `cap.pcap`: persist has 11.8 MB free (27.6 MB, 56% used), so cap the
  capture at about 6 MB (`tcpdump -C`/`-s 128` headers only) and the PCM dump at 60 s
  (48 kHz × 16-bit × 2 ch ≈ 11 MB per minute, so 25 s fits better).
- Where `tinycap.pcm` lands: `/sdcard/.debug` is readable only over ADB, so `boot.sh` should
  copy it into persist.
