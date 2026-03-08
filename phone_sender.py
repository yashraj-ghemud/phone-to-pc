"""
phone_sender.py — Android (Termux) Side
========================================
Detects a "Closed Fist" gesture using MediaPipe hand landmarks.
On detection → captures screenshot via termux-api → sends it over TCP to the PC.

Run inside Termux with:
    python phone_sender.py
"""

import cv2
import mediapipe as mp
import socket
import struct
import os
import time
import sys

# ──────────────────────────── CONFIG ────────────────────────────
PC_IP = "192.168.43.1"        # Static IP of your PC on phone hotspot
PC_PORT = 5555                 # Must match pc_receiver.py
SCREENSHOT_PATH = "/data/data/com.termux/files/home/screenshot.png"
COOLDOWN_SECONDS = 3           # Minimum gap between consecutive captures
CAMERA_INDEX = 0               # 0 = default camera
# ────────────────────────────────────────────────────────────────

# MediaPipe setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6,
)

# Finger tip landmark IDs and their corresponding middle-knuckle (PIP) IDs
# Index=8/6, Middle=12/10, Ring=16/14, Pinky=20/18
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
        if tip_y <= pip_y:          # finger is still extended
            return False
    return True


def capture_screenshot() -> bool:
    """Take a screenshot using Termux:API. Returns True on success."""
    # Remove old screenshot if it exists
    if os.path.exists(SCREENSHOT_PATH):
        os.remove(SCREENSHOT_PATH)

    ret = os.system(f"termux-screenshot -f {SCREENSHOT_PATH}")
    if ret != 0:
        print("[!] termux-screenshot command failed. Is termux-api installed?")
        return False

    # Wait briefly for the file to be written
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

        # Send 8-byte header (big-endian unsigned long long) then payload
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


def main():
    print("=" * 55)
    print("  PHONE SENDER — Gesture-to-Transfer (Closed Fist)")
    print("=" * 55)
    print(f"  Target PC : {PC_IP}:{PC_PORT}")
    print(f"  Cooldown  : {COOLDOWN_SECONDS}s between captures")
    print("  Press 'q' to quit.\n")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[!] Cannot open camera. Check permissions (termux-setup-storage).")
        sys.exit(1)

    last_capture_time = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[!] Failed to grab frame.")
                break

            # Flip for natural mirror view & convert BGR → RGB for MediaPipe
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            gesture_text = "Scanning..."

            if results.multi_hand_landmarks:
                for hand_lm in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)

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

            # Draw status on frame
            cv2.putText(frame, gesture_text, (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("Phone Sender — Fist to Capture", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()
        print("[*] Phone sender stopped.")


if __name__ == "__main__":
    main()
