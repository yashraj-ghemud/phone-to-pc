"""
pc_receiver.py — PC Side (Windows / Linux / macOS)
====================================================
1. Runs a background TCP Socket Server that receives screenshot images
   from the phone and saves them to disk.
2. Simultaneously runs a MediaPipe hand-tracking loop on the PC webcam.
3. When an "Open Palm" gesture is detected AND a new image has arrived,
   the image is opened automatically.

Run with:
    python pc_receiver.py
"""

import cv2
import mediapipe as mp
import socket
import struct
import threading
import os
import sys
import time
import platform
import subprocess

# ──────────────────────────── CONFIG ────────────────────────────
LISTEN_IP = "0.0.0.0"         # Listen on all interfaces
LISTEN_PORT = 5555             # Must match phone_sender.py
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "received_capture.png")
CAMERA_INDEX = 0               # 0 = default webcam
# ────────────────────────────────────────────────────────────────

# Shared state between threads
new_image_ready = threading.Event()   # Signals that a new image was received
server_running = True                 # Flag to stop the server thread

# MediaPipe setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6,
)

# Finger tip and PIP landmark IDs
FINGER_TIPS = [8, 12, 16, 20]    # Index, Middle, Ring, Pinky tips
FINGER_PIPS = [6, 10, 14, 18]    # Corresponding PIP joints
THUMB_TIP = 4
THUMB_IP = 3


def is_open_palm(hand_landmarks) -> bool:
    """
    An open palm is detected when ALL five fingers are extended:
      - Fingers 8, 12, 16, 20: tip.y < pip.y  (tip above knuckle)
      - Thumb 4: tip.x is farther from palm center than thumb IP joint
        (handles both left and right hands)
    """
    # Check four fingers — tips must be ABOVE their PIP joints
    for tip_id, pip_id in zip(FINGER_TIPS, FINGER_PIPS):
        if hand_landmarks.landmark[tip_id].y >= hand_landmarks.landmark[pip_id].y:
            return False

    # Check thumb — tip should be extended outward from the IP joint
    thumb_tip_x = hand_landmarks.landmark[THUMB_TIP].x
    thumb_ip_x = hand_landmarks.landmark[THUMB_IP].x
    wrist_x = hand_landmarks.landmark[0].x
    middle_mcp_x = hand_landmarks.landmark[9].x

    # Determine hand orientation: if wrist is left of middle MCP → right hand
    if wrist_x < middle_mcp_x:
        # Right hand: thumb tip should be to the LEFT of thumb IP
        if thumb_tip_x >= thumb_ip_x:
            return False
    else:
        # Left hand: thumb tip should be to the RIGHT of thumb IP
        if thumb_tip_x <= thumb_ip_x:
            return False

    return True


def open_image(filepath: str):
    """Open the image with the system's default viewer."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(filepath)
        elif system == "Darwin":    # macOS
            subprocess.Popen(["open", filepath])
        else:                       # Linux
            subprocess.Popen(["xdg-open", filepath])
        print(f"[✓] Opened image: {filepath}")
    except Exception as e:
        print(f"[!] Could not open image: {e}")


def recv_exact(conn: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a socket connection."""
    data = b""
    while len(data) < n:
        chunk = conn.recv(min(n - len(data), 65536))
        if not chunk:
            raise ConnectionError("Connection closed before all data received.")
        data += chunk
    return data


def handle_client(conn: socket.socket, addr):
    """Handle a single incoming image transfer from the phone."""
    try:
        print(f"\n[*] Connection from {addr[0]}:{addr[1]}")

        # Read 8-byte header → file size (big-endian uint64)
        header = recv_exact(conn, 8)
        file_size = struct.unpack("!Q", header)[0]
        print(f"[*] Incoming image: {file_size:,} bytes")

        if file_size == 0 or file_size > 100_000_000:  # sanity: max ~100 MB
            print("[!] Invalid file size, ignoring.")
            return

        # Receive the full image payload
        image_data = recv_exact(conn, file_size)

        # Save to disk
        with open(SAVE_PATH, "wb") as f:
            f.write(image_data)

        print(f"[✓] Image saved → {SAVE_PATH}")

        # Signal the gesture loop that a new image is ready
        new_image_ready.set()

    except ConnectionError as e:
        print(f"[!] Transfer error: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
    finally:
        conn.close()


def socket_server():
    """Background TCP server that accepts image transfers from the phone."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)  # So we can check server_running periodically
    server.bind((LISTEN_IP, LISTEN_PORT))
    server.listen(1)
    print(f"[*] Socket server listening on {LISTEN_IP}:{LISTEN_PORT}")

    while server_running:
        try:
            conn, addr = server.accept()
            handle_client(conn, addr)
        except socket.timeout:
            continue
        except OSError:
            break

    server.close()
    print("[*] Socket server stopped.")


def gesture_loop():
    """Main loop: webcam → MediaPipe → detect Open Palm → open image."""
    print("[*] Starting webcam for Open Palm detection...")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[!] Cannot open webcam.")
        return

    open_cooldown = 3           # Seconds between consecutive opens
    last_open_time = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[!] Failed to grab frame.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            status = "Waiting for image & Open Palm..."
            color = (200, 200, 200)

            if results.multi_hand_landmarks:
                for hand_lm in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)

                    if is_open_palm(hand_lm):
                        if new_image_ready.is_set():
                            now = time.time()
                            if now - last_open_time > open_cooldown:
                                status = "OPEN PALM — Opening image!"
                                color = (0, 255, 0)
                                print("\n[*] Open Palm detected + new image ready!")
                                open_image(SAVE_PATH)
                                new_image_ready.clear()
                                last_open_time = now
                            else:
                                remaining = open_cooldown - (now - last_open_time)
                                status = f"Palm OK — cooldown {remaining:.1f}s"
                                color = (0, 200, 255)
                        else:
                            status = "Open Palm (no new image yet)"
                            color = (0, 180, 255)
                    else:
                        status = "Hand visible (not open palm)"
                        color = (100, 100, 255)

            # Image-received indicator
            if new_image_ready.is_set():
                cv2.putText(frame, "[NEW IMAGE READY]", (10, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            cv2.putText(frame, status, (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
            cv2.imshow("PC Receiver — Open Palm to View", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()


def main():
    global server_running

    print("=" * 55)
    print("  PC RECEIVER — Gesture-to-Transfer (Open Palm)")
    print("=" * 55)
    print(f"  Listening on : {LISTEN_IP}:{LISTEN_PORT}")
    print(f"  Save path    : {SAVE_PATH}")
    print("  Press 'q' in the webcam window to quit.\n")

    # Start the socket server in a background daemon thread
    server_thread = threading.Thread(target=socket_server, daemon=True)
    server_thread.start()

    # Run the gesture detection on the main thread (OpenCV needs it)
    try:
        gesture_loop()
    finally:
        server_running = False
        server_thread.join(timeout=3)
        print("[*] PC receiver stopped.")


if __name__ == "__main__":
    main()
