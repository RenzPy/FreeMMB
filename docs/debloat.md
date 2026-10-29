# Debloating

Everything here is a user-level removal, `pm uninstall --user 0 <package>` over ADB: it
leaves the APK on `/system` untouched and is reversible with no flashing. Package lists
live in `docs/live/`, pulled from the device with `pm list packages`.

## What's removed

- **`wave1.txt`** (20 packages): preinstalled streaming apps most people won't use on a
  shared car screen (Netflix, Amazon, Hulu, KKBox…), test/demo apps, the uCloudlink
  cloud-SIM service, the OTA and hot-patch apps (`Rsota`/`SystemUpdater` and
  `TinkerCore`/`TinkerHelper` — the latter pair can silently reinstall other removed apps
  after an update, see the security audit), TeamViewer QuickSupport, and a couple of
  launcher widgets (`FloatingBall`, `FlashDot`).
- **`wave2-nav.txt`**: Waze. (Google Maps looks like a similar candidate — don't remove
  it; see Gotchas below.)
- **`wave3.txt`**: the print service stack (`bips`, `printspooler`, print-service
  recommendations — unused without a printer), a third-party YouTube client bundled by
  the OEM (see YouTube below), and the OEM's Bluetooth-call/contacts relay service.

Apply a wave:
```
while read -r p; do adb shell pm uninstall --user 0 "$p"; done < docs/live/wave1.txt
```

Undo one:
```
sh docs/live/restore.sh docs/live/wave1.txt
```
This uses `cmd package install-existing`, which works for anything still on `/system`.
Disney+ and HBO Max were installed to `/data` from `/system/xapp` on first boot and need
their APK reinstalled directly: `adb shell pm install -r /system/xapp/<Name>/*.apk`.

## Gotchas

- **Don't remove `com.google.android.apps.maps`.** The stock launcher keeps a live Google
  Maps panel on the home screen, rendered on its own virtual display. Without the app
  installed, the launcher repeatedly tries to recreate that display — several times a
  second — which exhausts the graphics system within a couple of minutes and crashes
  `system_server` in a loop. If you don't want it tracking your location for the weather
  widget, revoke its location permission instead (see `docs/security-audit.md`); the
  panel still renders, just without live position.
- `pm`/`appops` changes take roughly a minute to be written to disk — wait before
  rebooting, or they're lost.
- The telephony stack (dialer, SMS, IMS, cell broadcast) is left alone on purpose: this
  box takes a physical SIM and can route calls, SMS and mobile data through it.

## YouTube

The OEM ships a third-party rebuilt "Vanced" client — unrelated to the real, long
discontinued YouTube Vanced project — that fetches its own stream links. Those links can
expire mid-playback, causing a stutter/reload and persistent audio/video desync. It's
removed in wave 3. Two drop-in alternatives avoid this entirely:

- **ReVanced**: a patched build of the official YouTube client with ads removed, using
  the real player. Needs ReVanced Manager and a microG/GmsCore build for sign-in, both
  regular APKs.
- **SmartTube**: a TV-style YouTube client with its own player, no sign-in required.

With either, prefer a quality setting that decodes in hardware (H.264/AVC or VP9) over
AV1, which this SoC only decodes in software — see the CPU/thermal section of
`docs/security-audit.md` for why that matters for heat.

## Optional: the Google app

`com.google.android.googlequicksearchbox` runs three always-on processes using several
hundred MB of RAM. Removing it loses the launcher's Google search card, the Assistant
button, and "Hey Google." If you don't use those in the car, disable it first:

```
adb shell pm disable-user --user 0 com.google.android.googlequicksearchbox
```

reversible with `pm enable`. Confirm nothing else depends on it (give it a couple of
minutes and watch for crashes, the same way removing Maps was checked) before uninstalling
it outright.
