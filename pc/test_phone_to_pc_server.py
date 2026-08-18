import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phone_to_pc_server as gateway


class GatewayTests(unittest.TestCase):
    def test_safe_filename_removes_path_and_unsafe_characters(self):
        self.assertEqual(gateway.safe_filename("../../my photo?.png"), "my_photo_.png")

    def test_upload_requires_pairing_token(self):
        with tempfile.TemporaryDirectory() as directory:
            old_upload_dir = gateway.UPLOAD_DIR
            gateway.UPLOAD_DIR = Path(directory)
            server = gateway.Server(("127.0.0.1", 0), "test-token", "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                connection.request("POST", "/api/v1/upload", b"abc", {"Content-Length": "3"})
                response = connection.getresponse()
                self.assertEqual(response.status, 401)
                self.assertFalse(list(Path(directory).iterdir()))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                gateway.UPLOAD_DIR = old_upload_dir

    def test_upload_saves_bytes_and_returns_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            old_upload_dir = gateway.UPLOAD_DIR
            gateway.UPLOAD_DIR = Path(directory)
            server = gateway.Server(("127.0.0.1", 0), "test-token", "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = b"fake-image-data"
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                connection.request("POST", "/api/v1/upload", body, {
                    "Content-Length": str(len(body)),
                    "X-Phone-Token": "test-token",
                    "X-Filename": "hello.jpg",
                    "X-Phone-Name": "Test phone",
                })
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 201)
                self.assertTrue(payload["ok"])
                saved = Path(directory) / payload["file"]["filename"]
                self.assertEqual(saved.read_bytes(), body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                gateway.UPLOAD_DIR = old_upload_dir


if __name__ == "__main__":
    unittest.main()
