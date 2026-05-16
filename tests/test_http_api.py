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


def write_package(repo: Path, package_id: str, version: str, content: bytes):
    package_dir = repo / package_id
    package_dir.mkdir()
    (package_dir / "firmware.bin").write_bytes(content)
    manifest = {
        "package_id": package_id,
        "version": version,
        "compatible_model": "demo-board",
        "slot_class": "rootfs",
        "payload": {
            "filename": "firmware.bin",
            "size": len(content),
            "md5": hashlib.md5(content).hexdigest(),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def parse_json(stdout):
    return json.loads(stdout)


class HttpClientServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.repo = self.base_dir / "firmware"
        self.repo.mkdir()
        write_package(self.repo, "v2_success", "2.0.0", b"firmware version 2\n")

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

    def test_firmware_command_lists_package_manifest_fields(self):
        response = self.run_client("firmware")

        self.assertEqual(response["firmware"][0]["package_id"], "v2_success")
        self.assertEqual(response["firmware"][0]["version"], "2.0.0")
        self.assertEqual(response["firmware"][0]["compatible_model"], "demo-board")
        self.assertEqual(response["firmware"][0]["slot_class"], "rootfs")
        self.assertEqual(response["firmware"][0]["payload"]["filename"], "firmware.bin")
        self.assertEqual(response["firmware"][0]["payload"]["size"], len(b"firmware version 2\n"))

    def test_cli_one_shot_upgrade_talks_to_real_http_server(self):
        reset = self.run_client("reset")
        self.assertEqual(reset["state"]["active_slot"], "B")

        status = self.run_client("status")
        self.assertEqual(status["active_slot"], "B")
        self.assertEqual(status["current_version"], "1.0.0")

        upgrade = self.run_client("upgrade", "v2_success")
        self.assertEqual(upgrade["state"]["active_slot"], "B")
        self.assertEqual(upgrade["state"]["pending_slot"], "A")
        self.assertEqual(upgrade["state"]["slots"]["A"]["status"], "pending")

        reboot = self.run_client("reboot", "--boot-ok")
        self.assertEqual(reboot["state"]["active_slot"], "A")
        self.assertEqual(reboot["state"]["current_version"], "2.0.0")

        persisted = json.loads((self.base_dir / "data" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["active_slot"], "A")

    def test_cli_step_by_step_stage_verify_install_reboot(self):
        self.run_client("reset")
        stage = self.run_client("stage", "v2_success")
        self.assertEqual(stage["state"]["ota_state"], "staged")
        self.assertTrue((self.base_dir / "data" / "staging" / "v2_success" / "manifest.json").exists())
        self.assertTrue((self.base_dir / "data" / "staging" / "v2_success" / "firmware.bin").exists())

        verify = self.run_client("verify")
        self.assertEqual(verify["state"]["ota_state"], "verified")
        self.assertTrue(verify["state"]["staged_package"]["verified"])

        install = self.run_client("install")
        self.assertEqual(install["state"]["ota_state"], "pending_reboot")
        self.assertEqual(install["state"]["pending_slot"], "A")
        self.assertTrue((self.base_dir / "data" / "slots" / "A" / "firmware.bin").exists())

        reboot = self.run_client("reboot", "--boot-ok")
        self.assertEqual(reboot["state"]["active_slot"], "A")
        self.assertEqual(reboot["state"]["slots"]["A"]["status"], "good")


class ClientSeparationTests(unittest.TestCase):
    def test_client_module_does_not_import_or_mutate_server_state_files(self):
        client_path = PROJECT_ROOT / "ota_ab_sim" / "client.py"
        client_source = client_path.read_text(encoding="utf-8")
        tree = ast.parse(client_source)

        forbidden_text = [
            "OtaService",
            "state.json",
            "firmware/",
            "data/staging",
            "data/slots",
            "copytree",
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
