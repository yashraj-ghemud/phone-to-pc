# Phone-to-PC Kotlin Android App: Complete Build Specification and AI Prompt

This document is the single source of truth for building the Android APK that connects to the existing Python PC gateway in `pc/phone_to_pc_server.py`. Give the copy-paste prompt in the final section to another coding AI, or use it as the implementation checklist in Android Studio.

> **Important:** Do not replace the PC protocol with WebSocket, multipart form data, Bluetooth, Firebase, or a custom protocol. The current PC server expects one raw binary request body and three HTTP headers. The Android app must implement that contract exactly.

## 1. Product goal

Build a native Android application named **Phone-to-PC**. The application stores a PC gateway URL and pairing token, keeps a visible Android foreground service available for background transfers, accepts images from the in-app picker and the Android Share menu, uploads them to the PC over the local Wi-Fi or hotspot, and reports success or failure in the notification and app UI.

The first release must prioritize reliable transfer. Gesture detection, automatic screenshot capture, clipboard synchronization, OCR, remote PC commands, and encrypted internet transport are future modules. Do not make the first release depend on MediaPipe, Termux, CameraX, accessibility APIs, root access, or internet cloud services.

The existing PC server is intentionally small and uses only the Python standard library. It listens on port `8765` by default, creates a local token in `pc/.pairing_token`, accepts uploads at `/api/v1/upload`, and stores files under `pc/received/`.

## 2. Repository and Android module location

The repository is:

```text
https://github.com/yashraj-ghemud/phone-to-pc
```

The Android project must live at:

```text
phone-to-pc/android/
```

Use this package and application identity throughout the project:

| Item | Required value |
| --- | --- |
| Kotlin package | `com.yashraj.phonetopc` |
| Application ID | `com.yashraj.phonetopc` |
| App name | `Phone-to-PC` |
| Module | `app` |
| Minimum SDK | `26` |
| Compile SDK | `35` |
| Target SDK | `35` |
| Java/Kotlin target | Java 17 / JVM target 17 |
| Root activity | `MainActivity` |
| Upload service | `UploadService` |
| Boot receiver | `BootReceiver` |

The current repository already contains a starter Android module. If the coding AI opens the repository, it should improve the existing files rather than creating a second Android project beside `android/`.

## 3. Exact PC API contract

### 3.1 Base URL

The user enters a base URL such as:

```text
http://192.168.43.20:8765
```

The app must trim whitespace and trailing slashes before storing it. The upload URL is formed as:

```text
${serverUrl}/api/v1/upload
```

Do not append `/api/v1/upload` twice. If the user enters a URL that already ends with `/api/v1/upload`, either normalize it back to the base URL or display a validation error.

### 3.2 Health endpoint

The app may test pairing and connectivity with:

```http
GET /api/v1/health
```

A successful response is JSON similar to:

```json
{
  "started_at": 1723960000.0,
  "last_upload": null,
  "upload_count": 0,
  "last_device": null,
  "ok": true,
  "max_upload_bytes": 26214400
}
```

A connectivity test is successful only when the HTTP status is `200` and the decoded JSON field `ok` is `true`.

### 3.3 Upload request

Send the image as the **raw request body**, not as multipart form data.

```http
POST /api/v1/upload HTTP/1.1
Content-Length: <exact byte count when available>
Content-Type: image/jpeg
X-Phone-Token: <pairing token>
X-Phone-Name: <friendly phone name>
X-Filename: <display filename>

<raw image bytes>
```

Required Android constants:

```kotlin
const val API_UPLOAD_PATH = "/api/v1/upload"
const val HEADER_PHONE_TOKEN = "X-Phone-Token"
const val HEADER_PHONE_NAME = "X-Phone-Name"
const val HEADER_FILENAME = "X-Filename"
const val MAX_UPLOAD_BYTES = 25L * 1024L * 1024L
```

The server accepts payloads greater than `0` and less than or equal to `25 * 1024 * 1024` bytes. The Android app must check the size before opening the network connection and show a clear error if the file is too large.

The `X-Filename` value must be only a display filename. Never send a path. Use the Android `ContentResolver` to read `OpenableColumns.DISPLAY_NAME`, then fall back to `capture.jpg`.

The `Content-Type` must use the most specific MIME type available from `ContentResolver.getType(uri)`. If it is unavailable, use `application/octet-stream`.

### 3.4 Upload response

A successful upload returns HTTP `201` and JSON similar to:

```json
{
  "ok": true,
  "file": {
    "filename": "20260818T065340.857281Z_0005b1.jpg",
    "original_name": "hello.jpg",
    "size": 123456,
    "device": "My Android phone",
    "received_at": "2026-08-18T06:53:40.857281+00:00",
    "url": "/received/20260818T065340.857281Z_0005b1.jpg"
  }
}
```

Treat any `2xx` status as transport success, but expect `201` from the current server. Parse the JSON only for a user-facing filename/status; do not require the server filename to equal the phone filename.

### 3.5 Error responses

| HTTP status | Meaning | Android behavior |
| --- | --- | --- |
| `400` | Missing/invalid content length, interrupted transfer, or size error | Show a validation or transfer error; do not retry endlessly. |
| `401` | Wrong pairing token | Tell the user to copy the token again from the PC terminal. |
| `404` | Wrong path | Show “server URL or API path is incorrect.” |
| `500` | PC could not save | Show “PC storage error”; allow retry. |
| Network timeout/refused | PC offline, wrong IP, firewall, or different Wi-Fi | Show connection troubleshooting and allow retry. |

The app must never log the pairing token or the full image contents.

## 4. Required Android behavior

### 4.1 Pairing screen

`MainActivity` must provide these inputs and controls:

| UI label | View ID | Stored key | Type |
| --- | --- | --- | --- |
| PC gateway URL | `serverUrlInput` | `KEY_SERVER_URL` | `EditText` |
| Pairing token | `tokenInput` | `KEY_PAIRING_TOKEN` | `EditText` |
| Phone name | `phoneNameInput` | `KEY_PHONE_NAME` | `EditText` |
| Service status | `statusText` | not stored | `TextView` |
| Save pairing and start service | `savePairingButton` | none | `Button` |
| Test connection | `testConnectionButton` | none | `Button` |
| Choose image and send | `pickImageButton` | none | `Button` |
| Stop background service | `stopServiceButton` | none | `Button` |

Use these exact preference constants:

```kotlin
const val PREFS_NAME = "phone_to_pc_preferences"
const val KEY_SERVER_URL = "server_url"
const val KEY_PAIRING_TOKEN = "pairing_token"
const val KEY_PHONE_NAME = "phone_name"
```

Default phone name:

```kotlin
"My Android phone"
```

When the user taps **Save pairing and start service**, validate that the URL is non-empty, begins with `http://` or `https://`, the token is non-empty, and the phone name is non-empty. Save the values with `SharedPreferences`, then call `ContextCompat.startForegroundService()` with an explicit intent for `UploadService` and action `ACTION_START`.

Use `http://` for the current local PC gateway. Because Android blocks cleartext HTTP by default for newer target SDKs, the current local-network prototype includes `android:usesCleartextTraffic="true"`. This is acceptable only for a trusted private LAN. The production version should use HTTPS and remove that setting.

### 4.2 Test connection

When **Test connection** is pressed, call `GET ${serverUrl}/api/v1/health` on a background executor or coroutine. Use a short connect timeout, a short read timeout, and never block the Android main thread.

Recommended messages:

```text
Connected to PC gateway
Wrong token
PC gateway not reachable
Invalid server URL
```

If the health request succeeds, update `statusText` and the notification. The health endpoint itself does not require the token in the current Python implementation, so the test button validates network reachability; the real token is validated by the upload request.

### 4.3 Image picker

Use the Activity Result API, preferably:

```kotlin
ActivityResultContracts.GetContent()
```

Launch it with:

```kotlin
picker.launch("image/*")
```

Do not request broad storage permissions for this flow. The picker returns a content `Uri`, and the upload service must stream the bytes using `ContentResolver.openInputStream(uri)`.

Before dispatching the upload, call `contentResolver.query()` with:

```kotlin
arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
```

Reject a known file size above `MAX_UPLOAD_BYTES`. If the size is unknown, stream it and let the server enforce its limit, but do not load the entire image into a `ByteArray`.

### 4.4 Android Share menu

The app must receive images shared from Gallery, Google Photos, file managers, and other applications. Add this intent filter to `MainActivity`:

```xml
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="image/*" />
</intent-filter>
```

Also set:

```xml
android:launchMode="singleTop"
```

Handle both `onCreate(intent)` and `onNewIntent(intent)`. Extract:

```kotlin
val sharedUri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
```

Start the upload using an explicit service intent and preserve `Intent.FLAG_GRANT_READ_URI_PERMISSION`. The receiving activity/service must be able to read the temporary content URI permission while the upload is running.

The app itself does not need to generate a Share menu. It is a **share target**. The Android system provides the Sharesheet from the Gallery or another sender.

### 4.5 Background service

Implement a private started foreground service named `UploadService`.

Required service constants:

```kotlin
const val ACTION_START = "com.yashraj.phonetopc.action.START"
const val ACTION_UPLOAD = "com.yashraj.phonetopc.action.UPLOAD"
const val ACTION_STOP = "com.yashraj.phonetopc.action.STOP"
const val EXTRA_URI = "extra_uri"
const val NOTIFICATION_CHANNEL_ID = "phone_to_pc_service"
const val NOTIFICATION_ID = 8765
```

The service must:

1. Create a notification channel in `onCreate()`.
2. Call `startForeground()` immediately with a visible low-importance notification.
3. Return `START_STICKY` from `onStartCommand()` so the service can be recreated after process loss.
4. Run network and file I/O on a single-thread executor or coroutine dispatcher, never on the main thread.
5. Accept an image URI from the explicit `ACTION_UPLOAD` intent.
6. Stream the URI into an HTTP request body.
7. Set `X-Phone-Token`, `X-Phone-Name`, and `X-Filename` exactly.
8. Update the notification to “Ready”, “Sending…”, “Sent successfully”, or a concise failure state.
9. Avoid logging the token.
10. Clean up the executor in `onDestroy()`.
11. Support `ACTION_STOP` by calling `stopForeground(STOP_FOREGROUND_REMOVE)` and `stopSelf()`.

Use `HttpURLConnection` if the goal is zero third-party dependencies. OkHttp is also acceptable, but if used, configure a streaming request body and do not use multipart form data. The current repository starter uses `HttpURLConnection`; maintaining that is the simplest way to match the Python standard-library server.

Suggested service upload method names:

```kotlin
private fun uploadUri(uri: Uri)
private fun openUploadConnection(uri: Uri, metadata: FileMetadata): HttpURLConnection
private fun readDisplayName(uri: Uri): String
private fun readContentLength(uri: Uri): Long
private fun readMimeType(uri: Uri): String
private fun updateNotification(message: String)
```

### 4.6 Notification permission

For Android 13 and newer, request `Manifest.permission.POST_NOTIFICATIONS` from the activity before relying on user-visible upload status. The service should still handle notification creation gracefully if the user denies notification permission, but the user should be told that Android may hide status updates.

### 4.7 Boot restart

Add:

```xml
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
```

Register a non-exported-by-default or explicitly controlled `BootReceiver` for `android.intent.action.BOOT_COMPLETED`. On boot, read `KEY_PAIRING_TOKEN` and `KEY_SERVER_URL`. If pairing is complete, start the foreground service with an explicit `ACTION_START` intent.

Do not start camera capture or gesture recognition automatically after boot in the first release. Only restore the connection-ready/upload service. This avoids unexpected camera access and keeps the product behavior understandable.

## 5. Manifest requirements

The final manifest must include the following permissions and components:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
```

The application must include `android:usesCleartextTraffic="true"` while the Python server is HTTP-only:

```xml
<application
    android:allowBackup="true"
    android:usesCleartextTraffic="true"
    android:label="Phone-to-PC"
    android:supportsRtl="true"
    android:theme="@style/Theme.PhoneToPc">
```

The service declaration must be:

```xml
<service
    android:name=".UploadService"
    android:exported="false"
    android:foregroundServiceType="dataSync" />
```

The `dataSync` foreground service type is appropriate for image upload/data transfer in the current local-network design. Android 14 and newer require foreground-service types and their corresponding manifest permissions for target SDK 34+ applications.[1]

## 6. Required Kotlin file structure

The coding AI must create or update these files:

```text
android/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
└── app/
    ├── build.gradle.kts
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/yashraj/phonetopc/
        │   ├── MainActivity.kt
        │   ├── UploadService.kt
        │   ├── BootReceiver.kt
        │   ├── GatewayApiClient.kt
        │   ├── PairingStore.kt
        │   ├── FileMetadataReader.kt
        │   └── NotificationHelper.kt
        └── res/
            ├── layout/activity_main.xml
            └── values/
                ├── strings.xml
                ├── colors.xml
                └── themes.xml
```

The current minimal repository has the first three Kotlin classes. The other helper classes are recommended for a clean, maintainable version. The coding AI may keep the logic in fewer files if all behavior, names, error handling, and tests remain clear.

### Recommended class responsibilities

| Class | Responsibility |
| --- | --- |
| `MainActivity` | Render pairing UI, validate inputs, launch picker, handle Share intents, and request notification permission. |
| `UploadService` | Own foreground lifecycle, background executor, upload action handling, notification updates, retry policy, and service stop. |
| `GatewayApiClient` | Build URLs, run health checks, stream raw image uploads, map status codes, and parse response JSON. |
| `PairingStore` | Read/write `serverUrl`, `pairingToken`, and `phoneName` from `SharedPreferences`. |
| `FileMetadataReader` | Read display name, byte length, and MIME type from a content URI. |
| `NotificationHelper` | Create the channel and build status notifications. |
| `BootReceiver` | Restore the foreground service after boot when pairing data exists. |

## 7. Gradle requirements

Use the existing repository versions unless a newer compatible stable version is required by Android Studio:

```kotlin
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
}
```

The app module should use:

```kotlin
android {
    namespace = "com.yashraj.phonetopc"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.yashraj.phonetopc"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}
```

The minimal dependency set is:

```kotlin
dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
```

The coding AI may use Kotlin coroutines or OkHttp, but it must then update the Gradle file, keep all network work off the main thread, and preserve the raw-body API contract.

## 8. Retry and queue behavior

The first release may upload one file at a time. Use a single-thread executor to avoid concurrent uploads and memory pressure. If a transfer fails due to timeout, connection refusal, or temporary `5xx`, retry at most three times with delays such as `1s`, `3s`, and `8s`. Do not retry `401`, `400`, or a file-too-large error.

For a more complete version, implement a small persistent queue using `WorkManager` with network constraints. The user-facing foreground service can remain the immediate upload path, while `WorkManager` handles deferred retry if the phone leaves the hotspot. Do not silently discard a selected image; tell the user whether it was sent, queued, or failed.

## 9. Security and privacy requirements

The current Python gateway uses plain HTTP because it is intended for a private LAN or hotspot. The app must show a warning in the pairing screen:

```text
Use this only on a trusted Wi-Fi network. The current PC gateway uses local HTTP.
```

The app must not:

- Send the pairing token as a URL query parameter.
- Print the token to Logcat.
- Upload files without the user selecting or sharing them in the first release.
- Request contacts, location, microphone, accessibility, root, SMS, or broad storage permissions.
- Expose `UploadService` to other apps.
- Use an implicit service intent.
- Upload over the public internet without explicit user confirmation.

The PC gateway already stores the token in `.pairing_token`, ignores that file in Git, rejects unauthenticated uploads, limits upload size, sanitizes filenames, and writes atomically. The Android app must preserve those protections.

## 10. UI requirements

The UI can use classic XML views or Jetpack Compose. For compatibility with the current starter module, classic XML views are preferred. The screen should include:

1. App title and short explanation.
2. PC gateway URL field.
3. Pairing token field.
4. Phone name field.
5. Save/start button.
6. Test connection button.
7. Choose image and send button.
8. Stop service button.
9. Current service state.
10. Last upload result.
11. A warning that phone and PC must be on the same Wi-Fi/hotspot.

Use meaningful IDs instead of generated names. Keep the interface usable on small screens with a `ScrollView`.

## 11. Testing checklist

The coding AI must provide at least these tests or manual verification steps:

| Test | Expected result |
| --- | --- |
| Empty URL | Validation error; no service start. |
| Empty token | Validation error; no service start. |
| Health request to `127.0.0.1` or LAN IP | Status becomes connected when server is running. |
| Wrong token upload | Server returns `401`; app shows pairing error. |
| JPEG under 25 MB | Server returns `201`; app shows success. |
| File over 25 MB | App rejects before upload. |
| Image Share menu | Phone-to-PC appears as a target and uploads the shared URI. |
| Activity backgrounded | Upload continues through foreground service. |
| Service notification | A visible low-importance notification remains while service runs. |
| PC stopped | App shows connection failure and does not crash. |
| Phone reboot | Pairing remains stored and service attempts restart. |
| Filename with spaces/path characters | Server sanitizes it and saves safely. |
| Multiple sends | Service serializes them or queues them without corrupting files. |

For an instrumented test server, use a local fake endpoint or MockWebServer. Do not test against a hard-coded personal IP in automated tests.

## 12. Manual end-to-end test

On the PC:

```bash
cd phone-to-pc/pc
python phone_to_pc_server.py --no-browser
```

Copy the printed dashboard URL and pairing token. Find the PC LAN address, for example `192.168.43.20`, and enter:

```text
http://192.168.43.20:8765
```

in the Android app. The phone and PC must be on the same network. Save pairing, test the connection, choose a small image, and send it. The PC should create a timestamped file in:

```text
phone-to-pc/pc/received/
```

The dashboard should show the latest upload. Then share an image from Gallery and verify that the Phone-to-PC target appears and sends the file through the same `UploadService` path.

## 13. Future gesture module

After basic transfer is stable, add gesture recognition as an optional module. Do not place MediaPipe code directly inside the networking service. Use separate classes such as:

```kotlin
class GestureCaptureController
class CameraFrameAnalyzer
interface CaptureTrigger
```

The gesture module should emit a simple event:

```kotlin
interface CaptureTrigger {
    fun onCaptureRequested()
}
```

`onCaptureRequested()` should call the same upload queue used by the image picker. This keeps gesture capture, manual picker capture, Share-menu capture, and future screenshot capture on one reliable transport path.

For Android screenshots, use the official MediaProjection flow and request explicit user consent. Do not attempt hidden screenshots, root commands, or private Android APIs.

## 14. Copy-paste prompt for another coding AI

Copy everything inside the following block and paste it into the coding AI:

```text
You are an expert Android/Kotlin engineer. Build the native Android application inside the existing repository folder `android/` for the project `phone-to-pc`.

Product name: Phone-to-PC
Package: com.yashraj.phonetopc
Application ID: com.yashraj.phonetopc
Min SDK: 26
Compile SDK: 35
Target SDK: 35
Java/Kotlin target: 17
Preferred UI: classic XML views with AppCompat, not Compose unless you can preserve all required behavior.

The Android app must connect to the existing Python server in `pc/phone_to_pc_server.py`. Do not change the network protocol. The server listens on a base URL like `http://192.168.43.20:8765` and accepts raw image bytes at `POST /api/v1/upload`.

Exact upload request:
- URL: `${serverUrl}/api/v1/upload`
- Body: raw binary image bytes, not multipart form data
- Header `Content-Type`: MIME type from ContentResolver, fallback `application/octet-stream`
- Header `Content-Length`: exact byte length when available
- Header `X-Phone-Token`: pairing token
- Header `X-Phone-Name`: friendly phone name
- Header `X-Filename`: sanitized display filename only, never a path
- Maximum file size: 25 * 1024 * 1024 bytes

Exact endpoints:
- `GET /api/v1/health` returns JSON with `ok`, `upload_count`, `last_upload`, and `max_upload_bytes`.
- `POST /api/v1/upload` returns HTTP 201 and JSON `{ "ok": true, "file": { ... } }` on success.
- HTTP 401 means invalid pairing token.
- HTTP 400 means invalid payload or size/interrupted transfer.
- HTTP 500 means PC storage failure.

Implement these classes in package `com.yashraj.phonetopc`:
1. `MainActivity`
2. `UploadService`
3. `GatewayApiClient`
4. `PairingStore`
5. `FileMetadataReader`
6. `NotificationHelper`
7. `BootReceiver`

Required constants:
- `PREFS_NAME = "phone_to_pc_preferences"`
- `KEY_SERVER_URL = "server_url"`
- `KEY_PAIRING_TOKEN = "pairing_token"`
- `KEY_PHONE_NAME = "phone_name"`
- `API_UPLOAD_PATH = "/api/v1/upload"`
- `HEADER_PHONE_TOKEN = "X-Phone-Token"`
- `HEADER_PHONE_NAME = "X-Phone-Name"`
- `HEADER_FILENAME = "X-Filename"`
- `MAX_UPLOAD_BYTES = 25L * 1024L * 1024L`
- `ACTION_START = "com.yashraj.phonetopc.action.START"`
- `ACTION_UPLOAD = "com.yashraj.phonetopc.action.UPLOAD"`
- `ACTION_STOP = "com.yashraj.phonetopc.action.STOP"`
- `EXTRA_URI = "extra_uri"`
- `NOTIFICATION_CHANNEL_ID = "phone_to_pc_service"`
- `NOTIFICATION_ID = 8765`

MainActivity requirements:
- Show EditTexts with IDs `serverUrlInput`, `tokenInput`, `phoneNameInput`.
- Show Buttons with IDs `savePairingButton`, `testConnectionButton`, `pickImageButton`, `stopServiceButton`.
- Show TextViews with IDs `statusText` and `lastUploadText`.
- Save pairing values to SharedPreferences.
- Validate non-empty URL, token, and phone name.
- Normalize the server URL by trimming whitespace and removing trailing slash.
- Start the explicit foreground service with `ACTION_START` after saving pairing.
- Test the PC with `GET /api/v1/health` on a background thread; never block the main thread.
- Use Activity Result API `GetContent()` with MIME type `image/*` for image selection.
- Handle `ACTION_SEND` image Share intents in both `onCreate()` and `onNewIntent()`.
- Read the shared URI from `Intent.EXTRA_STREAM`.
- Preserve URI read permission while the upload runs.
- Request `POST_NOTIFICATIONS` on Android 13+.
- Show clear messages for connected, wrong token, offline PC, invalid URL, file too large, upload success, and upload failure.

UploadService requirements:
- Extend `android.app.Service`.
- Declare it `android:exported="false"`.
- Declare `android:foregroundServiceType="dataSync"`.
- Create a notification channel and call `startForeground()` immediately.
- Return `START_STICKY`.
- Use a single-thread executor or Kotlin coroutine dispatcher for all network and file I/O.
- Never load the entire image into memory; stream `ContentResolver.openInputStream(uri)` into `HttpURLConnection` output stream.
- Use the exact raw-body request and headers above.
- Read `OpenableColumns.DISPLAY_NAME` and `OpenableColumns.SIZE`.
- Reject known files above 25 MB before network upload.
- Retry only temporary network errors and HTTP 5xx, at most three times with delays 1s, 3s, and 8s.
- Never retry HTTP 400 or 401.
- Update the notification as `Ready to send images`, `Sending <filename>`, `Sent <filename> successfully`, `Wrong pairing token`, or `Send failed`.
- Implement `ACTION_STOP` to remove the notification and stop the service.
- Shut down the executor in `onDestroy()`.

GatewayApiClient requirements:
- Use HttpURLConnection or OkHttp with a streaming request body.
- Do not use multipart form data.
- Provide `checkHealth(serverUrl)` and `uploadImage(serverUrl, token, phoneName, uri, metadata)` methods.
- Set connect timeout to about 8 seconds and read timeout to about 20 seconds.
- Map status codes into typed results or clear exceptions.
- Never log the pairing token or image bytes.

PairingStore requirements:
- Wrap SharedPreferences.
- Provide `getServerUrl()`, `getPairingToken()`, `getPhoneName()`, `savePairing()`, and `clearPairing()`.
- Default phone name is `My Android phone`.

Manifest requirements:
- Add `INTERNET`.
- Add `FOREGROUND_SERVICE`.
- Add `FOREGROUND_SERVICE_DATA_SYNC`.
- Add `POST_NOTIFICATIONS`.
- Add `RECEIVE_BOOT_COMPLETED`.
- Set `android:usesCleartextTraffic="true"` because the current PC gateway uses local HTTP. Add a visible warning that this is only for a trusted LAN and should become HTTPS for production.
- Register `MainActivity` with MAIN/LAUNCHER and SEND image intent filters.
- Set `MainActivity` launchMode to `singleTop`.
- Register private `UploadService`.
- Register `BootReceiver` for BOOT_COMPLETED.

Share intent filter:
```xml
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="image/*" />
</intent-filter>
```

BootReceiver requirements:
- On BOOT_COMPLETED, read saved pairing data.
- If token and URL exist, start the foreground service with an explicit `ACTION_START` intent.
- Do not start camera or gesture recognition on boot in this release.

Gradle requirements:
- Keep namespace and application ID exactly `com.yashraj.phonetopc`.
- Use AndroidX Core KTX, Activity KTX, and AppCompat.
- If you add OkHttp or coroutines, update Gradle dependencies and keep the server protocol unchanged.
- Include `androidx.core` version new enough for foreground-service support.
- Make the app buildable in Android Studio with `assembleDebug`.

Testing requirements:
- Add unit tests for URL normalization, pairing validation, filename fallback, file-too-large validation, HTTP 401 mapping, and HTTP 201 success mapping.
- Add a manual end-to-end test in the README.
- Use a fake local server or MockWebServer in tests, never a personal IP.
- Verify the Android app appears in the Gallery Share menu.
- Verify the foreground notification remains visible while the app is backgrounded.
- Verify a selected image arrives in `pc/received/` and appears in the PC dashboard.

Do not add:
- Firebase
- Cloud storage
- WebSocket protocol
- Multipart upload
- Termux dependency
- MediaPipe dependency in the first release
- Root/accessibility permissions
- Contacts/location/microphone permissions
- Hidden screenshot behavior
- Any secret committed to Git

At the end, show the full file tree, explain every changed file, run the Android build/tests, and report any limitation honestly. Update `android/README.md` with exact run instructions. Do not modify the Python API contract unless you also update the API documentation and tests.
```

## 15. Official references

The service design follows Android’s guidance that a long-running foreground service must display a notification and that blocking work must run off the main thread.[2] Android 14 and newer require an appropriate foreground-service type and matching manifest permission; `dataSync` covers data upload and transfer use cases.[1] Android’s Sharesheet uses `ACTION_SEND` with a URI in `Intent.EXTRA_STREAM` for binary content such as images.[3]

[1]: https://developer.android.com/about/versions/14/changes/fgs-types-required "Foreground service types are required — Android Developers"
[2]: https://developer.android.com/develop/background-work/services "Services overview — Android Developers"
[3]: https://developer.android.com/develop/ui/compose/sharing/send "Send data to other apps — Android Developers"
