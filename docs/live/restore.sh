#!/bin/sh
# Re-enable packages removed for user 0. Usage: sh docs/live/restore.sh docs/live/wave1.txt
# APKs still on /system come back with install-existing; /data-only apps (Disney, HBO)
# need the APK again: pm install -r /system/xapp/<Name>/*.apk
ADB=${ADB:-./tools/platform-tools/adb.exe}
while read -r p; do
  [ -n "$p" ] && "$ADB" shell cmd package install-existing "$p"
done < "${1:?list file}"
