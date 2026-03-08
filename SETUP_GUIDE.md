# Gesture-to-Transfer — Setup Guide

A wireless system where a **Closed Fist** on the phone captures a screenshot and sends it to the PC, and an **Open Palm** on the PC webcam opens the received image.

```
┌─────────────────┐    Wi-Fi Hotspot     ┌─────────────────────┐
│   Android Phone  │ ──────────────────► │        PC            │
│                  │    TCP :5555         │                      │
│  Closed Fist     │  ───(image bytes)──► │  Socket Server       │
│  → Screenshot    │                      │  + Open Palm → View  │
│  → Send to PC    │                      │                      │
└─────────────────┘                       └─────────────────────┘
```

---

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Phone     | Android with **Termux** + **Termux:API** from F-Droid |
| PC        | Windows / Linux / macOS with Python 3.8+ |
| Network   | Phone Hotspot enabled, PC connected to it |

---

## Step 1 — Phone Setup (Termux)

### 1.1 Install Termux & Termux:API

Download **both** from [F-Droid](https://f-droid.org/) (NOT Play Store — the Play Store version is outdated):
- **Termux**
- **Termux:API**

### 1.2 Grant Permissions

Open Termux and run:
```bash
termux-setup-storage
```
Then in Android Settings → Apps → Termux:API → Permissions → allow **Display over other apps** (needed for screenshots).

### 1.3 Install Packages

```bash
# Update repos
pkg update && pkg upgrade -y

# Install Python, OpenCV dependencies, and Termux:API tools
pkg install python python-pip termux-api -y
pkg install opencv-python -y   # or: pip install opencv-python

# Install MediaPipe
pip install mediapipe
```

> **Note:** If `opencv-python` fails via pip, try `pkg install python-opencv` or build from source. Some Termux setups need `pkg install x11-repo` first.

### 1.4 Test Screenshot

```bash
termux-screenshot -f ~/test.png
ls -la ~/test.png
```
If this fails, ensure Termux:API is installed from the **same source** (F-Droid) as Termux.

### 1.5 Transfer the Script

Copy `phone_sender.py` to your phone (via USB, `scp`, or `wget`). Then place it in Termux's home:
```bash
cp /sdcard/Download/phone_sender.py ~/phone_sender.py
```

---

## Step 2 — PC Setup

### 2.1 Install Python Dependencies

```bash
pip install opencv-python mediapipe
```

### 2.2 Place the Script

Put `pc_receiver.py` in any folder on your PC. The received images will be saved in the **same folder** as the script.

---

## Step 3 — Network Setup (P2P Hotspot)

### 3.1 Enable Phone Hotspot

Go to **Settings → Hotspot & Tethering → Wi-Fi Hotspot → ON**.

### 3.2 Connect PC to Phone's Hotspot

Join the phone's Wi-Fi network from your PC.

### 3.3 Find the PC's IP Address

On the PC:
```bash
# Windows
ipconfig

# Linux / macOS
ifconfig
# or
ip addr
```

Look for the IP on the **Wi-Fi adapter** — typically something like `192.168.43.XXX`.

### 3.4 Update IP in phone_sender.py

Edit `phone_sender.py` on the phone and set `PC_IP` to your PC's actual IP:
```python
PC_IP = "192.168.43.1"   # ← Replace with your PC's IP
```

---

## Step 4 — Run the System

### 4.1 Start PC Receiver FIRST

On the PC:
```bash
python pc_receiver.py
```
You should see:
```
  PC RECEIVER — Gesture-to-Transfer (Open Palm)
  Listening on : 0.0.0.0:5555
  ...
  [*] Socket server listening on 0.0.0.0:5555
  [*] Starting webcam for Open Palm detection...
```

### 4.2 Start Phone Sender

On the phone (Termux):
```bash
python phone_sender.py
```
You should see:
```
  PHONE SENDER — Gesture-to-Transfer (Closed Fist)
  Target PC : 192.168.43.1:5555
  ...
```

### 4.3 Test the Flow

1. **Make a Closed Fist** in front of the phone camera → screenshot is taken and sent to PC.
2. On the PC terminal you'll see `[✓] Image saved → received_capture.png`.
3. **Show an Open Palm** to the PC webcam → the image opens automatically!

---

## How It Works

### Gesture Detection (MediaPipe Landmarks)

```
        8   12  16  20       ← Finger Tips
        |   |   |   |
        7   11  15  19
        |   |   |   |
        6   10  14  18       ← PIP Joints (knuckles)
        |   |   |   |
        5   9   13  17       ← MCP Joints
         \  |   |  /
          \ |   | /
            \   /
              0              ← Wrist
```

- **Closed Fist:** Tips (8,12,16,20) are **below** PIPs (6,10,14,18) → `tip.y > pip.y`
- **Open Palm:** Tips are **above** PIPs → `tip.y < pip.y` + thumb extended

### Network Protocol

```
Phone ──TCP──► PC

Packet layout:
┌──────────────────┬────────────────────────┐
│  8 bytes: SIZE   │  N bytes: IMAGE DATA   │
│  (uint64 BE)     │  (raw PNG bytes)       │
└──────────────────┴────────────────────────┘
```

The 8-byte header ensures the receiver knows **exactly** how many bytes to read, preventing corrupted or partial images.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` on phone | Ensure `pc_receiver.py` is running first. Check the IP/port. |
| `termux-screenshot` fails | Install Termux:API from F-Droid. Grant overlay permission. |
| Camera won't open (Termux) | Run `termux-setup-storage` and grant camera permission. |
| Webcam black on PC | Try changing `CAMERA_INDEX` to `1` in `pc_receiver.py`. |
| Firewall blocking connection | Allow Python through Windows Firewall on port 5555. |
| MediaPipe not detecting hands | Ensure good lighting. Keep hand 30–60 cm from camera. |
| Image opens but is corrupted | Network interruption during transfer. Try again — the size header ensures integrity. |

---

## Controls

- Press **`q`** in either webcam window to quit the respective script.
- **Cooldown:** By default, 3 seconds between captures (phone) and 3 seconds between opens (PC) to prevent spam.

---

## File Structure

```
pht capturing/
├── phone_sender.py        ← Run on Android (Termux)
├── pc_receiver.py         ← Run on PC
├── received_capture.png   ← Auto-created when image arrives
└── SETUP_GUIDE.md         ← This file
```
