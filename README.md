# Phone-to-PC

**Phone-to-PC** is a local-network bridge that lets an Android phone send images to a computer. The repository now contains a more reliable first version of the original gesture proof of concept: a dependency-light Python gateway for the PC and a native Kotlin Android client with a foreground background service.

> The recommended product direction is to make basic transfer reliable first, then add gesture control as an optional second layer. Gesture detection should trigger an upload; it should not be responsible for networking, pairing, storage, and UI all at once.

## What is included

| Part | Location | Responsibility |
| --- | --- | --- |
| PC gateway | `pc/phone_to_pc_server.py` | Serves the dashboard, authenticates phones with a pairing token, receives uploads, and saves them atomically. |
| PC dashboard | `pc/static/index.html` | Shows the local URL, pairing token, gateway health, and latest received image. |
| Android app | `android/` | Kotlin app for pairing, selecting an image, Android Share-menu uploads, and a persistent foreground service. |
| Legacy gesture prototype | `phone_sender.py`, `pc_receiver.py` | Original Termux + MediaPipe experiment retained for reference. |
| Tests | `pc/test_phone_to_pc_server.py` | Verifies token protection, safe filenames, and upload persistence. |

## How the new architecture works

```text
┌────────────────────────────┐       Wi-Fi / hotspot       ┌─────────────────────────────┐
│ Android Kotlin app         │ ───────────────────────────► │ Python PC gateway           │
│                            │       HTTP POST             │                             │
│ ForegroundService          │  X-Phone-Token header       │ /api/v1/upload              │
│ Share menu / image picker  │  X-Filename + image bytes   │ token auth + size limit      │
└────────────────────────────┘                             └──────────────┬──────────────┘
                                                                         │
                                                                         ▼
                                                               pc/received/*.jpg|png
                                                                         │
                                                                         ▼
                                                                  Local dashboard
```

The PC gateway binds to port **8765** by default. It creates a random local pairing token on first run and stores it in `pc/.pairing_token`, which is ignored by Git. The Android service includes that token with each upload. The gateway rejects unauthenticated requests, limits uploads to 25 MB, sanitizes filenames, and writes through a temporary file before replacing it with the completed file.

## Run the PC gateway

From the repository root:

```bash
cd pc
python phone_to_pc_server.py
```

The terminal prints a dashboard URL and token. Open the dashboard from the PC, note the PC's LAN address, and use an address such as `http://192.168.43.20:8765` in the Android app. On a same-computer test, run with `--host 127.0.0.1` and use `http://127.0.0.1:8765`.

If the dashboard does not open automatically, visit the printed URL manually. The PC and phone must be connected to the same Wi-Fi network or phone hotspot. A firewall may need an inbound rule for TCP port 8765.

## Build and run the Android app

Open the `android/` folder in Android Studio. Let Gradle sync, select an Android device or emulator, and run the `app` configuration. On the app screen:

1. Enter the PC gateway URL, for example `http://192.168.43.20:8765`.
2. Enter the pairing token printed by the PC gateway.
3. Enter a friendly phone name and tap **Save pairing & start service**.
4. Use **Choose image and send**, or use Android's Share menu and select Phone-to-PC.

The Android app starts `UploadService` as a foreground service. This gives the user-visible Android notification expected for a long-running background connection and allows uploads to continue after leaving the activity. Android may still apply battery restrictions; excluding the app from aggressive battery optimization is recommended on phones that stop background work.

## Run the tests

The PC gateway uses only the Python standard library:

```bash
cd pc
python -m unittest -v
```

The tests cover token rejection, filename sanitization, and successful byte-for-byte upload saving.

## API reference

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Returns gateway health and latest upload metadata. |
| `GET` | `/api/v1/pairing` | Returns the current LAN host, port, and local pairing token for the dashboard. |
| `POST` | `/api/v1/upload` | Accepts an image body with `X-Phone-Token`, `X-Phone-Name`, and `X-Filename` headers. |
| `GET` | `/received/<filename>` | Serves a previously received file through the local dashboard. |

The upload endpoint expects a `Content-Length` header and accepts up to 25 MB. This is a local-network prototype rather than an internet-facing service. Do not expose it directly to the public internet without TLS, stronger identity management, rate limits, and a careful threat model.

## Why the Python + Kotlin idea is good

Your suggested split is the right direction. Python is fast to iterate on for the PC side, where filesystem access, a local HTTP API, automation, and optional computer-vision modules are convenient. Kotlin is the correct native layer for Android because it can use Android's foreground-service rules, Share menu, notification system, permissions, and later CameraX or MediaProjection APIs without depending on Termux.

The important design decision is to keep the boundary small: **Android sends an authenticated file over HTTP; the PC owns storage and automation**. That means either side can evolve independently. For example, a future gesture detector can call the same upload service, and a future PC automation module can consume the saved-file event without changing the Android app.

## Recommended roadmap

| Stage | Feature | Reason |
| --- | --- | --- |
| 1 | Pairing, image picker, Share menu, local dashboard | Establishes a dependable end-to-end transfer path. |
| 2 | Camera capture inside the Android app | Removes the need to select an existing image. |
| 3 | Optional hand gesture trigger | Adds the original closed-fist idea without making it a hard dependency. |
| 4 | PC actions such as open, OCR, resize, or save to folders | Turns transfer into a useful automation tool. |
| 5 | QR-based pairing and encrypted transport | Improves usability and security for broader use. |
| 6 | Clipboard sync, files, notifications, and remote commands | Expands the project into a local-device productivity bridge. |

## Security notes

The gateway is designed for a trusted LAN. The token protects against casual unauthorized uploads, but the current transport is plain HTTP. Keep the service on a private network, do not port-forward it, and rotate the token by deleting `pc/.pairing_token` and restarting the server if it is exposed. For production-quality remote access, add HTTPS, device-specific keys, explicit pairing approval, and request rate limits.

## Legacy files

`phone_sender.py` and `pc_receiver.py` remain in the root because they document the original Termux and MediaPipe experiment. They are useful for testing gesture recognition, but the new Kotlin app and Python gateway are the recommended path for continued development.
