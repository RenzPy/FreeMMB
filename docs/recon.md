# Phase 1 recon: stock firmware (slot B)

Everything here comes from the offline dumps in `dumps/full` (see the README). Nothing was
run on the device. Paths are inside the slot-B logical partitions unless noted.

## Firmware

| Part | Build | Notes |
|---|---|---|
| system / system_ext / product | `qti/qssi/qssi:13/TKQ1.221013.002/lynx05271935:user/release-keys` | Android 13 QSSI; `ro.build.version.release` is spoofed to `14` |
| vendor / odm / boot | `qti/trinket/trinket:11/RKQ1.211119.001/lynx05272007:user/test-keys` | Android 11, security patch 2021-10-01 |
| kernel | `4.14.190-perf`, clang 10.0.7, built 2026-05-27 by `lynx@applepie-220` | gzip `Image` + 1.4 MB dtb, boot header v2 |

The OEM ("lynx" / "ApplePie" / "XQ") runs an Android 13 system on an Android 11 vendor.

### super and Virtual A/B

`super` (8 GiB, LP metadata v10.2) holds `system`, `system_ext`, `product` and `vendor`.
Slot 1 metadata still lists `system_b-cow` and `product_b-cow` (dm-snapshot `SnAp` stores),
but `/metadata/ota/state` is empty and `/metadata/ota/snapshots` has no entries, so the
last OTA is fully merged. All slot-B images match their AVB hashtree root digests
(`scripts/avbverify.py`), so `dumps/super/*_b.img` are exactly what the box runs.

Verified boot: `vbmeta_b` has flags `1` (hashtree disabled) and chains `vbmeta_system`
(flags `0`). `devinfo` reads `is_unlocked=1`, `is_tampered=1`.

## Boot ramdisk

First-stage-only ramdisk: `init`, `fstab.default`, `fstab.emmc`, GSI AVB keys, `e2fsck`.
There is **no `prop.default`**: Android 11+ init reads default props from
`/system/etc/prop.default` and the partition `build.prop` files, so editing props in this
ramdisk does nothing. Root/ADB via boot image means Magisk (or an equivalent init hook).

## Properties that matter

Load order is system → system_ext → vendor/default.prop → vendor/build.prop → odm →
product, and later files override earlier ones.

| Property | Effective value | Set in |
|---|---|---|
| `ro.adb.secure` | `1` (overrides system's `0`) | `vendor/default.prop` |
| `ro.debuggable`, `ro.secure` | **unset at boot** | OEM renamed them to `ro.xdebuggable=0` / `ro.xsecure=1` in `system/build.prop` |
| `dalvik.vm.heapsize` | `512m` (overrides `36m`) | `vendor/build.prop` |
| zram | 1 GiB swap | `fstab.default` |

Because `ro.debuggable` and `ro.secure` are never set by init, any root script can still
set them once at runtime. The OEM scripts below do exactly that.

## USB

The USB-C port runs in **peripheral (gadget) mode**. Gadget setups in
`vendor/etc/init/hw/init.qcom.usb.rc`:

- `sys.usb.config=appleSvc`: impersonates an iPhone to the car (`05ac:12a8`,
  "Apple Inc." / "iPhone", PTP + iPod + Apple Mobile Device + Apple USB Ethernet).
  Default in wireless and wired CarPlay modes.
- `sys.usb.configxq=accessory`: Android Open Accessory (`18d1:2d01`, product `Anroid_AA`).
- `sys.usb.debug.enabled=1`: builds the stock Android gadget with `ffs.adb`.

### Built-in ADB paths (no flashing)

1. **Settings toggle → ADB over Wi-Fi.** Both `Settings.apk` and `ApplePieSetting.apk`
   set `sys.setadb.mode=1`. That starts `wifi_adb.sh`, which sets
   `service.adb.tcp.port=5555`, restarts adbd, then sets `ro.debuggable=1` and
   `ro.secure=0`. The exact menu location is not yet known (needs the APK decompiled).
2. **Wired Android Auto mode → ADB over USB.** `z-sender.sh` (runs at every boot) checks
   for `/data/disable_carplay` **or** `persist.sys.mode.wired=2`. Either one sets the
   gadget to `diag,adb` with `sys.usb.debug.enabled=1`, and sets `ro.debuggable=1` /
   `ro.secure=0`. Ways to get to mode 2:
   - Reset button (GPIO 99): hold 3–5 s → cycles wireless (0) → wired CarPlay (1) →
     wired AA (2) and reboots. Requires `persist.sys.enable.multiconn=1`.
   - USB stick with `CarPlayMode.txt` containing `2` (also requires `multiconn=1`).

Either way `ro.adb.secure=1` stays in force, so the first connection must be approved on
the box's screen (the car display). Whether `adb root` works depends on how the apex
`adbd` was compiled (user builds normally refuse); to be tested.

> **Danger:** in `z-sender.sh`, holding the reset button for more than ~10 polling
> cycles broadcasts `MASTER_CLEAR` (**factory reset**). A USB stick containing a file
> named `recovery_command` does the same.

## USB-stick hooks (`copyZsender.sh`, run on every mount)

Runs as root in the `shell` SELinux domain whenever any USB stick is mounted:

- `PIEAPK/*.apk` → `pm install -r` each one (silent sideload)
- `xqcarplay.zip` → unzipped into `/data/xqcarplay` (CarPlay engine hot-fix)
- `z-sender` + `zsender_config.txt=update_zsender` → replaces the `z-sender` binary in `/data`
- `bootanimation.zip`, `btype.txt`, `CarPlayMode.txt`, `bdhcpcd`, `clean_apmoem.txt`
- `recovery_command` → **factory reset**
- `screenrecord_command` → 20 s screen recording to the stick
- Always copies `/data/anr`, `/data/tombstones`, `/etc/version` and `/data/goc6125` to the stick

`xq-reverse.sh` and `z-sender.sh` also run native code from `/data` as root
(`/data/z-sender`, `/data/AndroidAuto`, `LD_LIBRARY_PATH=/data/xqcarplay` or
`/data/data/com.xq.hotfix/lib`), so the OEM's OTA/hot-fix channel can replace root-level
code without touching the signed partitions.

## Performance and thermal

From `vendor/bin/init.qcom.post_boot.sh` (trinket branch) and the boot cmdline:

- `thermal-engine.conf` is **empty**, so thermal-engine uses its built-in defaults.
- Little cluster `scaling_min_freq=614400`, big cluster `scaling_min_freq=902400`:
  the cores never drop to their lowest frequency, so idle heat stays higher.
- Big cluster `scaling_max_freq=1804800` (stock SM6125 gold is ~2.0 GHz).
- schedutil with `up/down_rate_limit_us=0`, `hispeed_load=85`, `sched_load_boost=-6`.
- Kernel cmdline boots with `lpm_levels.sleep_disabled=1`; post_boot re-enables LPM
  later. If post_boot fails or runs late, deep sleep stays off.
- `z-sender.sh` keeps running forever, polling the reset GPIO every 1–3 s.

## Preinstalled apps (132 packages)

Largest, by on-disk size:

| Location | Apps |
|---|---|
| `system/bundled_uninstall_back-app` (re-installed by OEM scripts) | Youtube 238 MB, GoogleArm 221, Spotify 149, Netflix 144, Amazon 120, VLCVideo 74, TeamViewer 53, KKBOXMusic 43, XQCarPlay 39, APKPure 21, Hulu 21, XQAuto 8, Egg, GPSTest, GoogleAssist, Test |
| `system/xapp` (installed by `install_apk.sh` on first boot/OTA) | Waze 148, HBO 108, Disney 74, GoogleGemini 7 |
| `product/app` | webview 170, Maps 168, LatinImeGoogle 85, Trichrome 75, SpeechServices 70, YTMusic 66, Chrome 56, Gallery2, PhotoTable, ConferenceDialer, xdivert, uim* |
| `product/priv-app` | GmsCore 128, Phonesky 60, Contacts, SettingsIntelligence |
| `system_ext/priv-app` | **two launchers**: Launcher3_NewUi 104 + APMLauncher3 94, plus Launcher3_QuickStep 23; QtiDialer, Mms, ims |
| `system/app` (OEM) | GlocalMeCarUI 44 + Uservice 29 (uCloudlink SIM, `ro.vendor.ucloud.sim.device=XQ_CarPlayBox1`), TinkerCore/TinkerHelper (hot-patch framework), Rsota/SystemUpdater (OTA), ApplePieSetting, FloatingBall, FlashDot, SplitScreen, TXZrec, ReturnCar, AutoTest, ApkInstaller, Traceur |

Telephony (TeleService, Telecom, Mms, QtiDialer, ims, CarrierConfig, SimContact) is
present; whether the box has a modem in use for anything besides uCloudlink is to be
confirmed on the live system before removing it.

## Implications for the plan

1. **Phase 2 may not need a flash to get ADB.** Try the Settings toggle (Wi-Fi ADB) or
   wired-AA mode first; both are OEM paths that also set `ro.debuggable=1`.
2. Magisk is still the route to persistent root. Patch `boot_b`, keeping
   `dumps/full/lun4/boot_b.bin` for restore.
3. Debloat targets: the `bundled_uninstall_back-app` and `xapp` sets, one of the two
   launchers, streaming apps, and possibly GMS. Neutralise `install_apk.sh` so they don't
   come back after an OTA.
4. Thermal and perf: lower the min freqs, add a real `thermal-engine.conf`, and check
   that LPM is actually enabled on the running system.
5. Be careful with the reset button and with USB sticks: both can factory-reset the box.
