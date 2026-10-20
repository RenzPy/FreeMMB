# FreeMMB

Tools and resources for the **APM-6125-T7-Dual-V1.0** board.

## Board Information

| Field     | Value                                                              |
|-----------|--------------------------------------------------------------------|
| Board     | APM-6125-T7-Dual-V1.0                                             |
| SoC       | Qualcomm SM6125 (nicobar)                                         |
| HWID      | `0x0010a0e100000000`                                               |
| PK_HASH   | `0xd40eee56f3194665574109a39267724ae7944134cd53cb767e293d3c40497955` |

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
