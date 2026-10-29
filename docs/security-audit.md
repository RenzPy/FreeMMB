# Privacy and remote-control audit (2026-10-29)

Sources: the live box over ADB (shell user, hook v7) and an offline sweep of the slot-B
`system`, `vendor`, `product` and `system_ext` images. No traffic capture yet: in ADB mode
the box has no network, and capturing needs root.

## Evidence from the live box

- **SELinux is Permissive** (`getenforce`). Nothing confines root services.
- `/system/xbin/msu` is setuid root but fails for the shell user (`setgid failed`), so it is
  not a privilege escalation from apps or ADB.
- Mobile data history (`dumpsys netstats --full --uid`, SIM MCC/MNC 228/02, Jul–Oct 2026):
  - OEM uid-1000 apps: no traffic at all.
  - root (uid 0): about 1 MB sent, nothing received, in small bursts per drive.
  - `com.zjinnova.zlink` (CarPlay engine): a few hundred bytes sent per drive, nothing received.
  - uid -4 (apps since uninstalled, including uCloudlink and Rsota OTA): 7.6 GB in total. This
    can't be split per app any more.
- No device admins, no accessibility services, no VPN, proxy or private DNS, no ADB over TCP.
- Mic access history: only Google TTS and Gboard. No OEM app has used the camera.
- `/sdcard/.debug/and_*.ini` holds root-written logcat (dhcpcd, gocsdk licence `auth get imei`).
- `com.applepie.bluetooth` runs `com.tinker.coresdk.core.MainSDKService`. It is inert while
  TinkerCore stays uninstalled.

## High: root code-execution channels (`/system/etc/init/hw/init.rc`)

| Service | Trigger | What it does | State |
|---|---|---|---|
| `doShell` | `sys.start.shell=1` | Runs `/data/android_shell_command.sh` as root, `u:r:init:s0` | Dormant, file absent; any uid-1000 app can set the prop |
| `updatexq` | `sys.xq.update=1` | Unzips `/sdcard/Download/xqcarplay.zip` and `gocsdk.zip` into `/data`; root daemons then run them | Downloader was TinkerCore (Aliyun OSS Hong Kong), now uninstalled |
| `copy_file` | `sys.lynx.copy.*` | Root `cp -rf` between any two paths | Only TinkerHelper used it, now uninstalled |
| USB stick | any mount | `copyZsender.sh`: silent APK install, factory reset, root binary replacement | Physical access |

## Medium: telemetry and phone-home

| Component | Endpoints | Data |
|---|---|---|
| gocsdk Bluetooth stack (root, always on) | `pwdserver.goodocom.com`, `pwdserverqz.goodocom.com`, `120.77.203.18`, `47.92.37.111`; reachability checks to baidu.com, qq.com, aliyun.com, 114.114.114.114 | IMEI, SoC serial, eMMC CID (licence registration) |
| `com.zjinnova.zlink` | Tencent Bugly (`android.bugly.qq.com`, `astat.bugly.qcloud.com`), `119.91.73.132:8888` activation, self-update from `sudingtech.oss-cn-shenzhen.aliyuncs.com` | eMMC serial; holds mic, fine/background location, phone state |
| SharkCarPlay (root) | `120.24.79.21:18080/activate/submit` | Device ID, SoC serial. Only if `shark.cert` is missing (it is present) |
| Launcher (`APMLauncher3`, active) | QWeather `*.qweather.net`, `api.openweathermap.org` | Location, for the weather widget |
| `wifi_adb.sh` | `sys.setadb.mode=1` | ADB on port 5555 on every interface, mobile data included. RSA approval is still required |
| `connect-ap.sh` + `keeplog` | none (local) | Logs the car's Wi-Fi SSID/password; copied to any USB stick with a `Debug1288_log` folder |

## Low / info

- A UART console shell always runs on `ttyMSM0` (needs physical access).
- `bootTimeout.sh` factory-resets the box if the boot animation hasn't ended within 300 s.
- `/system/etc/hosts` maps four Tesla China hostnames to 6.6.6.6.
- `com.wits.pms` (TXZrec, uid system) has an exported unprotected service. The TXZ voice
  core itself is absent.
- `com.quicinc.voice.activation`: Qualcomm hotword app, with mic access but no internet.
- Present but dormant: CQ-Blink/BitAnswer, Mapgoo firewall, uCloudlink `unet`.

## Clean

- No ssh, telnetd, frpc or ngrok.
- vendor and system_ext scripts are stock.
- No Chinese push SDKs (Umeng, JPush, Getui).
- CA store: 129 public roots.
- Qualcomm cloud Wi-Fi positioning is off.
- Native OEM CarPlay/AA binaries other than SharkCarPlay have no remote endpoints.

## Applied over ADB (2026-10-29, verified after reboot)

Wait ~60 s before rebooting after `pm`/`appops` changes: an immediate reboot lost them once.

| Change | Command | Undo |
|---|---|---|
| Launcher: no location (weather widget) | `pm revoke com.android.launcher3 android.permission.ACCESS_{FINE,COARSE,BACKGROUND}_LOCATION`, `appops set ... {FINE,COARSE}_LOCATION ignore` | `pm grant` + `appops set ... allow` |
| zlink: no phone ID, no background location, no self-install | `pm revoke com.zjinnova.zlink android.permission.{READ_PHONE_STATE,ACCESS_BACKGROUND_LOCATION}`, `appops set com.zjinnova.zlink REQUEST_INSTALL_PACKAGES deny` | `pm grant` / `appops set ... default` |
| TXZrec removed | `pm uninstall --user 0 com.wits.pms` | `cmd package install-existing com.wits.pms` |
| Qualcomm hotword disabled | `pm disable-user --user 0 com.quicinc.voice.activation` | `pm enable com.quicinc.voice.activation` |
| Local debug logs deleted | `rm -f /sdcard/.debug/*` (keeplog recreates them) | none |

CarPlay with the trimmed zlink permissions is not yet tested in the car.
