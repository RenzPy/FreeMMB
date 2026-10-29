# FreeMMB

Tools and resources for the **APM-6125-T7-Dual-V1.0** board — a Qualcomm SM6125 wireless
CarPlay/Android Auto adapter ("JoyeBox" / "XQ" OEM firmware). Everything here is read from
or written to the device with [EDL](https://github.com/bkerler/edl) or ADB; no bootloader
unlock, no root exploit, no soldering.

## Contents

- This file — board facts, EDL entry, raw partition read/write, offline analysis tools.
- [docs/recon.md](docs/recon.md) — what's actually in the stock firmware: boot flow, USB
  gadget modes, the OEM's own USB-stick update mechanism, preinstalled apps.
- [docs/adb-access.md](docs/adb-access.md) — getting an ADB shell with nothing flashed.
- [docs/debloat.md](docs/debloat.md) — removing preinstalled apps safely, package lists
  and a one-line restore.
- [docs/boot-animation.md](docs/boot-animation.md) — replacing the boot animation with
  your own video, written in place over EDL.
- [docs/security-audit.md](docs/security-audit.md) — a privacy/remote-control audit of the
  stock firmware (phone-home endpoints, dormant root channels, what was found clean) and
  the ADB-level mitigations applied.
- [docs/car-mode-hook.md](docs/car-mode-hook.md) — a design, not yet built, for a
  persistent hook that would firewall the audited phone-home servers and close a dormant
  root channel.

## Board Information

| Field     | Value                                                              |
|-----------|--------------------------------------------------------------------|
| Board     | APM-6125-T7-Dual-V1.0                                             |
| SoC       | Qualcomm SM6125 (nicobar)                                         |
| HWID      | `0x0010a0e100000000`                                               |
| PK_HASH   | `0xd40eee56f3194665574109a39267724ae7944134cd53cb767e293d3c40497955` |
| MSM_ID    | `0x0010a0e1` (OEM_ID `0x0000`, MODEL_ID `0x0000`)                  |
| Serial    | `0xbc4328db`                                                       |

The PK_HASH is Qualcomm's generic test key, so the generic QCM6125 firehose loader works.

## Entering EDL (9008) mode

1. Unplug USB-C and wait about 10 s so the board is fully powered down.
2. Press and hold the tactile recovery button on the PCB.
3. Plug USB-C into the PC while still holding it, and keep holding for about 10 s total,
   then release.
4. Device Manager should show `QUSB_BULK` / `Qualcomm HS-USB QDLoader 9008`, with no LED
   activity (WinUSB driver installed via Zadig). If the board boots normally instead (LED
   comes on, USB enumerates as the regular device), it read the button as a normal power-on
   rather than EDL — unplug and try again, holding a little longer before plugging in.

The same button also serves as a runtime mode switch once Android is running — see
[docs/adb-access.md](docs/adb-access.md). Holding it for EDL entry (board off, nothing on
the LED) and holding it to cycle modes (board on, LED lit) are different operations that
happen to share a button; don't hold it down after the board has already booted.

## Usage

`scripts/edl.ps1` wraps [bkerler/edl](https://github.com/bkerler/edl) and always passes
`--loader=loader/prog_firehose.bin`. Auto-detection skips it because its filename prefix
is `001750e1`, not our MSM_ID `0010a0e1`.

```powershell
.\scripts\edl.ps1 printgpt > dumps\gpt.txt
.\scripts\edl.ps1 r boot_a dumps\boot_a.img
```

Set `$env:EDL_MEMORY = "emmc"` or `"ufs"` if storage autodetect fails. `edl.ps1` looks for
[bkerler/edl](https://github.com/bkerler/edl) at `tools\edl` by default (gitignored); set
`$env:EDL_DIR` to point it elsewhere.

## Storage layout

UFS, 6 LUNs, A/B slots. Stock firmware is Android 11 (security patch 2021-10), boot header v2.
**Slot B is active** (`boot_b` flags `0x77`: active + successful), so patches target `boot_b`.
Both `vbmeta` images ship with flags `1` (hashtree/dm-verity disabled), and `devinfo`
reports `is_unlocked=1`.

## Stock backup

`dumps/full/lunN/` holds a raw dump of every partition except `userdata`, made with:

```powershell
.\scripts\edl.ps1 rl dumps\full --skip=userdata --genxml
```

Each LUN folder also has its `gpt_main`, `gpt_backup` and `rawprogramN.xml`. The SHA-256 of
every file is in [docs/stock-sha256sums.txt](docs/stock-sha256sums.txt); check a copy with
`sha256sum -c` from inside `dumps/full`. Keep a copy of `dumps/full` off this PC:
`persist`, `modemst1`, `modemst2`, `fsg` and `devinfo` are unique to this board and cannot
be rebuilt from any firmware package.

To restore a single partition (for example after a bad boot patch):

```powershell
.\scripts\edl.ps1 w boot_b dumps\full\lun4\boot_b.bin
```

## Offline analysis

Pure-Python tools (no WSL or 7-Zip needed). In Git Bash, set `MSYS_NO_PATHCONV=1` so
image paths like `/system/build.prop` aren't rewritten into Windows paths.

| Script | Does |
|---|---|
| `scripts/lpunpack.py` | Lists or extracts logical partitions from `super` |
| `scripts/ext4extract.py` | `ls` / `cat` / `extract` inside an ext4 image |
| `scripts/avbverify.py` | Checks images against vbmeta hashtree and hash descriptors |
| `scripts/bootanimation_tool.py` | Builds and installs a custom boot animation — see [docs/boot-animation.md](docs/boot-animation.md) |

Findings are in [docs/recon.md](docs/recon.md).

> **Warning:** holding the reset button for more than about 10 seconds factory-resets the
> box, and so does inserting a USB stick that contains a file named `recovery_command`.
> See the recon notes.

## Repository Structure

```
FreeMMB/
├── apks/        # Assets installed onto the device (wallpaper, boot animation)
├── docs/        # Guides, recon notes, checksums
│   └── live/    # Debloat package lists and the restore script
├── dumps/       # Partition dumps (git-ignored, local only)
├── loader/      # Qualcomm EDL firehose loader
│   └── prog_firehose.bin
├── scripts/     # Utility scripts (EDL wrapper, offline analysis, boot animation tool)
├── .gitignore
└── README.md
```

## Loader

The EDL firehose programmer for QCM6125 is stored at `loader/prog_firehose.bin`.
It is used by tools such as [edl](https://github.com/bkerler/edl) to communicate
with the device in Emergency Download (EDL / 9008) mode.

## Contributors

- [**RenzPy**](https://github.com/RenzPy) — Project owner
