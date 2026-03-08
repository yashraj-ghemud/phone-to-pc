"""
phone_sender.py — Android (Termux) Side
========================================
Detects a "Closed Fist" gesture using MediaPipe hand landmarks.
On detection → captures screenshot via termux-api → sends it over TCP to the PC.

Designed to run HEADLESS in Termux (no GUI window needed).
Uses termux-camera-photo to grab frames for hand detection.

Install on Termux:
    pkg install python termux-api
    pip install mediapipe opencv-python-headless

Run:
    python phone_sender.py
"""

import mediapipe as mp
import numpy as np
import socket
import struct
import os
import time
import sys
import subprocess

# Try importing cv2 — on Termux use opencv-python-headless
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[!] cv2 not found. Using termux-camera-photo for frame capture.")
    print("    Install with: pip install opencv-python-headless")
    print("    Or:           pkg install python-opencv\n")

# ──────────────────────────── CONFIG ────────────────────────────
PC_IP = "192.168.43.1"        # Static IP of your PC on phone hotspot
PC_PORT = 5555                 # Must match pc_receiver.py
SCREENSHOT_PATH = "/data/data/com.termux/files/home/screenshot.png"
FRAME_PATH = "/data/data/com.termux/files/home/frame.jpg"
COOLDOWN_SECONDS = 3           # Minimum gap between consecutive captures
CAMERA_INDEX = 0               # 0 = front camera, 1 = back camera
SCAN_INTERVAL = 0.5            # Seconds between each frame capture (headless)
# ────────────────────────────────────────────────────────────────

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=True,     # True = works on individual images
    max_num_hands=1,
    min_detection_confidence=0.7,
)

# Finger tip landmark IDs and their corresponding middle-knuckle (PIP) IDs
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]


def is_closed_fist(hand_landmarks) -> bool:
    """
    A fist is detected when ALL four finger tips are BELOW
    their respective PIP (middle knuckle) joints.
    In MediaPipe's coordinate system, y increases downward,
    so tip.y > pip.y means the finger is curled.
    """
    for tip_id, pip_id in zip(FINGER_TIPS, FINGER_PIPS):
        tip_y = hand_landmarks.landmark[tip_id].y
        pip_y = hand_landmarks.landmark[pip_id].y
        if tip_y <= pip_y:
            return False
    return True


def capture_frame_termux() -> np.ndarray:
    """
    Capture a single camera frame using termux-camera-photo.
    Returns the image as a numpy array (RGB), or None on failure.
    """
    try:
        if os.path.exists(FRAME_PATH):
            os.remove(FRAME_PATH)

        result = subprocess.run(
            ["termux-camera-photo", "-c", str(CAMERA_INDEX), FRAME_PATH],
            timeout=10, capture_output=True
        )
        if result.returncode != 0:
            return None

        # Wait for file
        for _ in range(10):
            if os.path.exists(FRAME_PATH) and os.path.getsize(FRAME_PATH) > 0:
                break
            time.sleep(0.2)

        if not os.path.exists(FRAME_PATH):
            return None

        # Read as numpy array without cv2
        if CV2_AVAILABLE:
            img = cv2.imread(FRAME_PATH)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            # Fallback: use MediaPipe's image reading
            from PIL import Image
            img = Image.open(FRAME_PATH).convert("RGB")
            return np.array(img)

        return None
    except Exception as e:
        print(f"[!] Frame capture error: {e}")
        return None


def capture_screenshot() -> bool:
    """Take a screenshot using Termux:API. Returns True on success."""
    if os.path.exists(SCREENSHOT_PATH):
        os.remove(SCREENSHOT_PATH)

    ret = os.system(f"termux-screenshot -f {SCREENSHOT_PATH}")
    if ret != 0:
        print("[!] termux-screenshot command failed. Is termux-api installed?")
        return False

    for _ in range(10):
        if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 0:
            return True
        time.sleep(0.3)

    print("[!] Screenshot file not found after capture attempt.")
    return False


def send_image_to_pc(filepath: str) -> bool:
    """
    Sends the image file over TCP with a 8-byte size header.
    Protocol:  [8 bytes: file size as uint64]  [N bytes: raw image data]
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()

        file_size = len(data)
        if file_size == 0:
            print("[!] Image file is empty, skipping send.")
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((PC_IP, PC_PORT))

        header = struct.pack("!Q", file_size)
        sock.sendall(header + data)
        sock.close()

        print(f"[✓] Sent {file_size:,} bytes to {PC_IP}:{PC_PORT}")
        return True

    except ConnectionRefusedError:
        print(f"[!] Connection refused — is pc_receiver.py running on {PC_IP}:{PC_PORT}?")
        return False
    except socket.timeout:
        print("[!] Connection timed out.")
        return False
    except Exception as e:
        print(f"[!] Send error: {e}")
        return False


def main_headless():
    """Headless mode: uses termux-camera-photo for frame capture (no GUI)."""
    print("[MODE] Headless (Termux) — using termux-camera-photo")
    print(f"  Scanning every {SCAN_INTERVAL}s | Camera: {CAMERA_INDEX}")
    print("  Press Ctrl+C to quit.\n")

    last_capture_time = 0

    while True:
        print(".", end="", flush=True)
        rgb_frame = capture_frame_termux()

        if rgb_frame is None:
            print("\n[!] Could not capture frame. Retrying...")
            time.sleep(1)
            continue

        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            for hand_lm in results.multi_hand_landmarks:
                if is_closed_fist(hand_lm):
                    now = time.time()
                    if now - last_capture_time > COOLDOWN_SECONDS:
                        print("\n[*] CLOSED FIST detected! Taking screenshot...")
                        if capture_screenshot():
                            print("[*] Screenshot captured. Sending to PC...")
                            send_image_to_pc(SCREENSHOT_PATH)
                        last_capture_time = now
                    else:
                        remaining = COOLDOWN_SECONDS - (now - last_capture_time)
                        print(f" (cooldown {remaining:.1f}s)", end="")

        time.sleep(SCAN_INTERVAL)


def main_gui():
    """GUI mode: uses cv2.VideoCapture with live preview (if display available)."""
    print("[MODE] GUI — live camera preview")
    print("  Press 'q' to quit.\n")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[!] Cannot open camera via OpenCV. Falling back to headless mode...\n")
        main_headless()
        return

    last_capture_time = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[!] Failed to grab frame.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            gesture_text = "Scanning..."

            if results.multi_hand_landmarks:
                for hand_lm in results.multi_hand_landmarks:
                    if is_closed_fist(hand_lm):
                        now = time.time()
                        if now - last_capture_time > COOLDOWN_SECONDS:
                            gesture_text = "FIST DETECTED — Capturing..."
                            print("\n[*] Closed Fist detected! Taking screenshot...")
                            if capture_screenshot():
                                print("[*] Screenshot captured. Sending to PC...")
                                send_image_to_pc(SCREENSHOT_PATH)
                            last_capture_time = now
                        else:
                            remaining = COOLDOWN_SECONDS - (now - last_capture_time)
                            gesture_text = f"Cooldown: {remaining:.1f}s"
                    else:
                        gesture_text = "Hand visible (not a fist)"

            # Try to show GUI — if it fails, switch to headless
            try:
                cv2.putText(frame, gesture_text, (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.imshow("Phone Sender", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            except cv2.error:
                print("\n[!] No display available. Switching to headless mode...\n")
                cap.release()
                main_headless()
                return

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()
        print("[*] Phone sender stopped.")


def main():
    print("=" * 55)
    print("  PHONE SENDER — Gesture-to-Transfer (Closed Fist)")
    print("=" * 55)
    print(f"  Target PC : {PC_IP}:{PC_PORT}")
    print(f"  Cooldown  : {COOLDOWN_SECONDS}s between captures\n")

    if not CV2_AVAILABLE:
        # No OpenCV → headless mode only
        main_headless()
    else:
        # Try GUI first, auto-fallback to headless if no display
        main_gui()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Phone sender stopped.")
    finally:
        hands.close()
