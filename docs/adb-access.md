# Getting ADB access

This board ships with `ro.adb.secure=1` and ADB disabled, and there's no exposed host USB
port to use the usual OEM USB-stick tricks. Two paths in the stock firmware bring up ADB
without flashing anything.

## Wi-Fi ADB (recommended)

Found by tracing the OEM Settings app's code (`com.applepie.setting`): a tap counter on
one of its rows sets the property `sys.setadb.mode=1`, which triggers the stock
`wifi_adb.sh` script (already on `/system/bin`) and starts `adbd` listening on TCP 5555.

1. Get the box onto a Wi-Fi network your PC can also reach, via the Settings app's Wi-Fi
   screen.
2. On the box's own screen, open **Settings**, scroll to the bottom, and tap the
   **JoyeBox Version** row rapidly — about 7 taps, each within half a second of the last.
   It restarts `adbd` once the tap count registers.
3. On the PC: `adb connect <box-ip>:5555` (read the IP from your router's client list,
   or from a Wi-Fi details screen on the box).

The first connection needs the usual on-screen RSA key approval; after that, your PC's
key stays trusted. This resets on every boot, so steps 2–3 repeat each time.

**Don't use `/data/disable_carplay`** as a shortcut to permanent ADB: it does enable it,
but it also disables the CarPlay engine entirely.

Port 5555 listens on every interface the box has, mobile data included — a connection
still needs your PC's trusted key, but only enable it when you intend to use it.

## Wired mode-cycle button

The single recovery button also serves as a mode switch once Android is running: hold it
until the status LED turns yellow, then release — the box reboots into the next mode.
It cycles **wireless CarPlay → wired CarPlay → wired Android Auto → wireless CarPlay**.

Wired Android Auto mode is meant to expose ADB over the USB cable too (the firmware
switches the USB gadget to `diag,adb`), but on this unit a boot script also forces
Android's own ADB toggle off unless `/data/disable_carplay` exists, so nothing appears
over USB in that mode in practice. Use Wi-Fi ADB above instead.

**Caution:** holding the same button well past the yellow signal (continuing to hold for
roughly another 10 seconds after it turns solid white) triggers a factory reset.

## Entering EDL (9008) instead

For anything that needs raw partition access rather than a shell — reading or writing
partitions directly, as the rest of this repo's tools do — see "Entering EDL (9008) mode"
in the main README. That's a hardware-level mode entered by holding the same button while
powering the box on, independent of whether Android or ADB is working at all.
