# FreeMMB

Tools and resources for the **APM-6125-T7-Dual-V1.0** board.

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

1. Unplug USB-C.
2. Hold the tactile recovery button on the PCB.
3. Plug USB-C into the PC, keep holding for 3–5 s, then release.
4. Device Manager should show `QUSB_BULK` / `Qualcomm HS-USB QDLoader 9008`
   (WinUSB driver installed via Zadig).

## Usage

`scripts/edl.ps1` wraps [bkerler/edl](https://github.com/bkerler/edl) and always passes
`--loader=loader/prog_firehose.bin`. Auto-detection skips it because its filename prefix
is `001750e1`, not our MSM_ID `0010a0e1`.

```powershell
.\scripts\edl.ps1 printgpt > dumps\gpt.txt
.\scripts\edl.ps1 r boot_a dumps\boot_a.img
```

Set `$env:EDL_MEMORY = "emmc"` or `"ufs"` if storage autodetect fails, and `$env:EDL_DIR`
if edl is not in `C:\Users\Asus\Downloads\edl-3.52.1`.

## Repository Structure

```
FreeMMB/
├── apks/        # APK files
├── dumps/       # Partition dumps (git-ignored, local only)
├── loader/      # Qualcomm EDL firehose loader
│   └── prog_firehose.bin
├── scripts/     # Utility scripts
├── .gitignore
└── README.md
```

## Loader

The EDL firehose programmer for QCM6125 is stored at `loader/prog_firehose.bin`.
It is used by tools such as [edl](https://github.com/bkerler/edl) to communicate
with the device in Emergency Download (EDL / 9008) mode.

## Contributors

- [**RenzPy**](https://github.com/RenzPy) — Project owner
- **Antigravity AI** — AI pair-programming assistant (repo setup, documentation)
