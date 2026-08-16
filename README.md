<p align="center">
  <img src="./.github/readme-assets/signal.gif" alt="Animated signal / product visual for phone-to-pc" width="100%" />
</p>

<h1 align="center">phone-to-pc</h1>

<p align="center"><strong>Proof-of-concept tool to send screenshots from an Android device running Termux to a PC using MediaPipe-based hand-gesture triggers.</strong></p>

<p align="center"><code>REPO//SIGNAL</code> · <code>SIGNAL / PRODUCT</code> · <code>LOOPING README EXPERIENCE</code></p>

## Live signal

| Lens | Readout |
| --- | --- |
| Portfolio lane | **SIGNAL / PRODUCT** |
| Code surface | **3** tracked files observed |
| Primary materials | **Python, Markdown** |
| Verification | **0** test-related files observed |

> A moving scan of the project surface. The animated frame above is a lightweight visual signature; the sections below remain the source of truth for implementation details.

## Motion map

`SIGNAL` → `SHAPE` → `RELEASE`

Use the animated banner as the first signal, then move into the implementation dossier. The recommended next step is to verify the documented setup command against the repository scripts before extending the project.

<details open>
<summary><strong>Open the full project dossier</strong></summary>

## Overview
A minimal, two-process proof-of-concept: a phone-side script (phone_sender.py) detects a closed-fist gesture on an Android device running Termux, captures a screenshot via termux-api, and (per code intent) transmits it over TCP to a PC. The PC-side script (pc_receiver.py) runs a TCP listener, saves received image bytes to disk, and concurrently runs MediaPipe hand tracking on the PC webcam to detect an open-palm gesture that automatically opens the most recent received image.

## What it does
- Detects closed-fist on phone to trigger a screenshot capture and send.
- Runs a TCP server on the PC to receive and save image bytes.
- Uses the PC webcam + MediaPipe to detect an open-palm and open the saved image automatically.
- Uses a simple peer-to-peer TCP approach with basic inter-thread coordination on the PC (threading.Event).

## Key capabilities
- Phone-side headless gesture detection (MediaPipe) intended for Termux.
- Screenshot capture on phone via termux-api (termux-camera-photo / termux-api references).
- PC-side image receiver that writes to a fixed SAVE_PATH (received_capture.png).
- Cross-platform image opening on the PC (Windows/macOS/Linux handled in code paths).
- Top-level configuration exposed via constants (e.g., ports, save path, cooldown).

## Technology
- Python 3
- MediaPipe (mediapipe)
- OpenCV (cv2 / opencv-python-headless)
- termux-api (termux-camera-photo, termux-api for screenshots)
- Pillow (PIL) referenced as a fallback
- Python stdlib: socket, struct, threading, subprocess, os, platform

## Repository structure
- SETUP_GUIDE.md — (present in repository; contents not included in the supplied excerpts)
- phone_sender.py — phone-side script intended to run in Termux (gesture detection + capture + send).
- pc_receiver.py — PC-side TCP server + save + webcam MediaPipe loop to open images.

## Getting started
- There are no explicit, complete setup or run commands provided in the supplied excerpts.
- Check SETUP_GUIDE.md in this repository for any maintainer-provided setup steps.
- To inspect runtime behavior and configuration, open phone_sender.py and pc_receiver.py:
  - Look for top-level constants to adjust (examples seen in the code: PC_IP, LISTEN_IP, LISTEN_PORT, SAVE_PATH).
  - Review how screenshots are captured (termux-api calls) and how image bytes are sent/received over TCP.
- The repository excerpts do not include packaging, installation scripts, or automated tests.

## Configuration
- Configuration is exposed as top-level constants inside the two main scripts. Relevant names seen in the codebase include:
  - phone_sender.py: PC_IP (hard-coded destination IP on the phone side)
  - pc_receiver.py: LISTEN_IP (defaults seen as '0.0.0.0' in excerpts), LISTEN_PORT
  - SAVE_PATH (received filename; seen as received_capture.png in the code)
  - Other parameters referenced: COOLDOWN_SECONDS, CAMERA_INDEX
- To change behavior, edit those constants or add runtime argument parsing (not present in supplied excerpts).

## Development and quality notes
- The repository is a minimal proof-of-concept. The supplied excerpts show:
  - No unit tests, integration tests, or CI configuration included.
  - Partial/truncated network send/receive implementations in excerpts (not complete in supplied material).
  - Hard-coded addresses/ports and a single fixed output filename (overwriting risk).
  - Limited error handling for network and subprocess operations.
- Suggested improvements (from static review in repository excerpts):
  - Add argparse to override runtime settings (IP, ports, save path, camera index, cooldown).
  - Restrict or make LISTEN_IP configurable (avoid 0.0.0.0 by default).
  - Implement receive size limits, atomic file writes (temp file + rename), and timestamped filenames.
  - Add basic authentication or encryption (shared token, TLS) and input validation.
  - Replace prints with structured logging and improve exception handling.
  - Add unit tests for deterministic functions (e.g., is_open_palm / is_closed_fist) and integration tests for send/receive.

## Safety and responsible use
- Important security findings from code excerpts:
  - Data is sent over unencrypted, unauthenticated TCP—subject to eavesdropping and injection on the same network.
  - pc_receiver.py defaults to LISTEN_IP = "0.0.0.0" in excerpts, exposing the listener on all interfaces.
  - Hard-coded PC_IP and fixed SAVE_PATH create risks (accidental overwrites, misuse).
  - No size checks on received data visible—risk of large transfers, disk exhaustion, or DoS.
  - Subprocess calls (termux-camera-photo, xdg-open/open) may be risky if file paths can be influenced.
  - No authentication/pairing—any device that can reach the listening port could send images.
- Recommended immediate mitigations before running on untrusted networks:
  - Run the PC listener on loopback or a restricted interface and avoid 0.0.0.0 unless necessary.
  - Use network isolation when testing (local network you control).
  - Add maximum payload size checks and atomic saves; avoid using a single fixed filename.
  - Implement at least a short shared-token authentication or TLS for transports before using across untrusted networks.

## Contributing
- The repository does not include a CONTRIBUTING.md excerpt. Suggested ways to contribute based on the current codebase:
  - Improve configuration handling (add argparse, environment variable support).
  - Harden the network protocol (size limits, authentication, optional TLS).
  - Replace single fixed SAVE_PATH with timestamped/rotating filenames and atomic writes.
  - Add unit tests for gesture detection helpers and integration tests for local send/receive.
  - Improve logging and error handling.
- To work on any of the above, inspect phone_sender.py and pc_receiver.py to locate the constants and logic you will change, and update SETUP_GUIDE.md with any new or changed setup steps.

(There is no license file evident in the supplied excerpts; no license section is included here.)

</details>

---

<p align="center"><sub>README motion system · visual layer by RepoSignal · implementation details remain project-specific</sub></p>
