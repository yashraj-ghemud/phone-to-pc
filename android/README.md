# Phone-to-PC Android client

This folder contains the Kotlin Android client for the Python gateway in `../pc/phone_to_pc_server.py`.

For the complete implementation contract and a copy-paste prompt for another coding AI, read [`../KOTLIN_APP_BUILD_PROMPT.md`](../KOTLIN_APP_BUILD_PROMPT.md). That document is the source of truth for API paths, headers, Kotlin constants, manifest permissions, service behavior, Share-menu support, error handling, retries, security, and tests.

## Open and run

Open this `android/` folder in Android Studio. Allow Gradle to sync, connect an Android device or start an emulator, and run the `app` configuration. The project includes the Gradle wrapper, so from a terminal you can also run:

```bash
cd android
./gradlew testDebugUnitTest assembleDebug
```

The debug APK is generated at `android/app/build/outputs/apk/debug/app-debug.apk`. The current local prototype uses an HTTP PC server, so the app manifest allows cleartext traffic for trusted Wi-Fi/hotspot testing.

Start the PC first:

```bash
cd ../pc
python phone_to_pc_server.py --no-browser
```

Copy the printed pairing token. Find the PC's LAN IP address, then enter a URL such as:

```text
http://192.168.43.20:8765
```

in the Android app. The phone and PC must be on the same Wi-Fi network or phone hotspot. Save pairing, test the connection, select a small image, and send it. The resulting file appears in `../pc/received/` and in the PC dashboard.

## Implemented Android files

The completed client now includes `MainActivity.kt`, `PairingStore.kt`, `GatewayApiClient.kt`, `FileMetadataReader.kt`, `NotificationHelper.kt`, `UploadService.kt`, and `BootReceiver.kt`. It also includes a JVM test for URL normalization and a Gradle wrapper for repeatable builds.

## Current behavior

The app supports pairing, health testing, image picking, Share-menu image intake, a foreground upload service, bounded retries for temporary network failures, file-size validation, and boot recovery. The Python server expects the image as a raw HTTP request body with these headers:

```text
X-Phone-Token: <pairing token>
X-Phone-Name: <friendly phone name>
X-Filename: <display filename>
Content-Type: <image MIME type>
Content-Length: <byte count>
```

The first release intentionally does not request camera, microphone, location, contacts, accessibility, storage, or root permissions. Add gesture recognition only after the basic upload path is stable, and route gesture-triggered captures through the same upload service.

## Production warning

The current Python gateway is intended for a trusted local network. It uses plain HTTP. Do not expose it to the public internet. A production version should use HTTPS, device-specific keys, explicit pairing approval, rate limiting, and a proper encrypted transport.
