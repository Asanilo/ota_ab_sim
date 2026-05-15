import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from ota_ab_sim.ota import OtaService
from ota_ab_sim.server import make_handler


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_firmware(repo: Path, name: str, version: str, content: bytes):
    firmware_path = repo / name
    firmware_path.write_bytes(content)
    metadata = {
        "name": name,
        "version": version,
        "md5": hashlib.md5(content).hexdigest(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    (repo / f"{name}.json").write_text(json.dumps(metadata), encoding="utf-8")


def parse_json(stdout):
    return json.loads(stdout)


class HttpClientServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.repo = self.base_dir / "firmware_repo"
        self.repo.mkdir()
        write_firmware(self.repo, "firmware_v2.bin", "2.0.0", b"firmware version 2\n")

        service = OtaService(self.base_dir)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        self.server_url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def run_client(self, *args, expect_success=True):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ota_ab_sim.client",
                "--server",
                self.server_url,
                *args,
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return parse_json(result.stdout)

    def test_cli_talks_to_real_http_server_for_upgrade_and_reboot(self):
        reset = self.run_client("reset")
        self.assertEqual(reset["state"]["active_slot"], "B")

        status = self.run_client("status")
        self.assertEqual(status["active_slot"], "B")
        self.assertEqual(status["current_version"], "1.0.0")

        upgrade = self.run_client("upgrade", "firmware_v2.bin")
        self.assertEqual(upgrade["state"]["active_slot"], "B")
        self.assertEqual(upgrade["state"]["pending_upgrade"], "A")
        self.assertEqual(upgrade["state"]["slots"]["A"]["boot_status"], "pending")

        reboot = self.run_client("reboot", "--boot-ok")
        self.assertEqual(reboot["state"]["active_slot"], "A")
        self.assertEqual(reboot["state"]["current_version"], "2.0.0")

        persisted = json.loads((self.base_dir / "data" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["active_slot"], "A")


class ClientSeparationTests(unittest.TestCase):
    def test_client_module_does_not_import_or_mutate_server_state_files(self):
        client_path = PROJECT_ROOT / "ota_ab_sim" / "client.py"
        client_source = client_path.read_text(encoding="utf-8")
        tree = ast.parse(client_source)

        forbidden_text = [
            "OtaService",
            "state.json",
            "firmware_repo",
            "staging",
            "copyfile",
            "shutil",
        ]
        for token in forbidden_text:
            self.assertNotIn(token, client_source)

        imported_modules = set()
        called_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_names.add(node.func.attr)

        self.assertNotIn("pathlib", imported_modules)
        self.assertNotIn("Path", imported_modules)
        self.assertNotIn("open", called_names)
        self.assertNotIn("Path", called_names)


if __name__ == "__main__":
    unittest.main()
