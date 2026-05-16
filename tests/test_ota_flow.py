import hashlib
import json
import tempfile
import unittest
from pathlib import Path


def write_package(
    repo: Path,
    package_id: str,
    version: str,
    content: bytes,
    bad_md5: bool = False,
    bad_sha256: bool = False,
):
    package_dir = repo / package_id
    package_dir.mkdir()
    firmware_path = package_dir / "firmware.bin"
    firmware_path.write_bytes(content)
    manifest = {
        "package_id": package_id,
        "version": version,
        "compatible_model": "demo-board",
        "slot_class": "rootfs",
        "payload": {
            "filename": "firmware.bin",
            "size": len(content),
            "md5": "bad-md5" if bad_md5 else hashlib.md5(content).hexdigest(),
            "sha256": "bad-sha256" if bad_sha256 else hashlib.sha256(content).hexdigest(),
        },
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


class OtaFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.repo = self.base_dir / "firmware"
        self.repo.mkdir()
        write_package(self.repo, "v2_success", "2.0.0", b"firmware version 2\n")
        write_package(self.repo, "v3_success", "3.0.0", b"firmware version 3\n")
        write_package(self.repo, "v2_bad_md5", "9.9.9", b"corrupted firmware\n", bad_md5=True)
        write_package(self.repo, "v2_bad_sha256", "9.9.8", b"sha256 corrupted firmware\n", bad_sha256=True)

    def tearDown(self):
        self.tmp.cleanup()

    def make_service(self):
        from ota_ab_sim.ota import OtaService

        return OtaService(self.base_dir)

    def read_persisted_state(self):
        return json.loads((self.base_dir / "data" / "state.json").read_text(encoding="utf-8"))

    def test_status_starts_on_slot_b_with_target_slot_a(self):
        service = self.make_service()

        status = service.status()

        self.assertEqual(status["device_model"], "demo-board")
        self.assertEqual(status["active_slot"], "B")
        self.assertEqual(status["current_version"], "1.0.0")
        self.assertEqual(status["target_slot"], "A")
        self.assertEqual(status["slot_versions"], {"A": None, "B": "1.0.0"})
        self.assertIsNone(status["pending_slot"])
        self.assertIsNone(status["pending_upgrade"])
        self.assertIsNone(status["staged_package"])
        self.assertEqual(status["slots"]["A"]["status"], "empty")
        self.assertEqual(status["slots"]["B"]["status"], "good")

    def test_stage_copies_package_directory_and_records_staged_package(self):
        service = self.make_service()

        result = service.stage("v2_success")
        staged_dir = self.base_dir / "data" / "staging" / "v2_success"

        self.assertTrue(result["ok"])
        self.assertTrue((staged_dir / "manifest.json").exists())
        self.assertTrue((staged_dir / "firmware.bin").exists())
        self.assertEqual(result["state"]["ota_state"], "staged")
        self.assertEqual(result["state"]["staged_package"]["package_id"], "v2_success")
        self.assertEqual(result["state"]["staged_package"]["path"], str(staged_dir))
        self.assertIn("package_staged", result["state"]["events"])
        self.assertIn("manifest_loaded", result["state"]["events"])
        self.assertIsNone(result["state"]["slots"]["A"]["size"])
        self.assertFalse((self.base_dir / "data" / "slots" / "A" / "firmware.bin").exists())

    def test_stage_rejects_path_traversal_package_id(self):
        service = self.make_service()

        result = service.stage("../v2_success")

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["ota_state"], "invalid_package")
        self.assertIn("Invalid package id", result["state"]["last_error"])
        self.assertFalse((self.base_dir / "data" / "staging" / "v2_success").exists())

    def test_checksum_failure_does_not_write_slot_a_and_is_persisted(self):
        service = self.make_service()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        result = service.upgrade("v2_bad_md5")
        persisted = self.read_persisted_state()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["ota_state"], "verification_failed")
        self.assertIn("MD5", result["state"]["last_error"])
        self.assertFalse(result["state"]["staged_package"]["verified"])
        self.assertIsNone(result["state"]["slots"]["A"]["version"])
        self.assertIsNone(persisted["slots"]["A"]["version"])
        self.assertEqual(persisted["ota_state"], "verification_failed")
        self.assertFalse(slot_file.exists())

    def test_sha256_failure_does_not_write_slot_a_and_is_persisted(self):
        service = self.make_service()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        result = service.upgrade("v2_bad_sha256")
        persisted = self.read_persisted_state()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["ota_state"], "verification_failed")
        self.assertIn("SHA256", result["state"]["last_error"])
        self.assertFalse(result["state"]["staged_package"]["verified"])
        self.assertIsNone(result["state"]["slots"]["A"]["version"])
        self.assertIsNone(persisted["slots"]["A"]["version"])
        self.assertEqual(persisted["ota_state"], "verification_failed")
        self.assertFalse(slot_file.exists())

    def test_verification_reads_staged_payload_not_repository_source(self):
        service = self.make_service()

        stage = service.stage("v2_success")
        (self.repo / "v2_success" / "firmware.bin").write_bytes(b"tampered repo firmware\n")
        verify = service.verify()

        self.assertTrue(stage["ok"])
        self.assertTrue(verify["ok"])
        self.assertEqual(verify["state"]["staged_package"]["package_id"], "v2_success")
        self.assertTrue(verify["state"]["staged_package"]["verified"])

    def test_successful_upgrade_writes_inactive_slot_a_then_reboot_commits_a(self):
        service = self.make_service()
        expected_content = b"firmware version 2\n"
        expected_md5 = hashlib.md5(expected_content).hexdigest()
        expected_sha256 = hashlib.sha256(expected_content).hexdigest()

        upgrade = service.upgrade("v2_success")
        pending = self.read_persisted_state()
        reboot = service.reboot(simulate_boot_failure=False)
        committed = self.read_persisted_state()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        self.assertTrue(upgrade["ok"])
        self.assertEqual(upgrade["state"]["active_slot"], "B")
        self.assertEqual(upgrade["state"]["pending_slot"], "A")
        self.assertEqual(upgrade["state"]["pending_upgrade"], "A")
        self.assertEqual(upgrade["state"]["slots"]["A"]["version"], "2.0.0")
        self.assertEqual(upgrade["state"]["slots"]["A"]["status"], "pending")
        self.assertEqual(upgrade["state"]["slots"]["A"]["file_path"], str(slot_file))
        self.assertEqual(upgrade["state"]["slots"]["A"]["size"], len(expected_content))
        self.assertEqual(upgrade["state"]["slots"]["A"]["md5"], expected_md5)
        self.assertEqual(upgrade["state"]["slots"]["A"]["sha256"], expected_sha256)
        self.assertTrue(slot_file.exists())
        self.assertEqual(hashlib.md5(slot_file.read_bytes()).hexdigest(), expected_md5)
        self.assertEqual(hashlib.sha256(slot_file.read_bytes()).hexdigest(), expected_sha256)
        self.assertTrue(upgrade["state"]["bootloader"]["upgrade_available"])
        self.assertEqual(upgrade["state"]["bootloader"]["boot_once_slot"], "A")
        self.assertIn("package_staged", upgrade["state"]["events"])
        self.assertIn("manifest_loaded", upgrade["state"]["events"])
        self.assertIn("verified", upgrade["state"]["events"])
        self.assertIn("written_to_A", upgrade["state"]["events"])
        self.assertIn("pending_reboot", upgrade["state"]["events"])
        self.assertEqual(pending["ota_state"], "pending_reboot")
        self.assertTrue(reboot["ok"])
        self.assertEqual(reboot["state"]["active_slot"], "A")
        self.assertEqual(reboot["state"]["current_version"], "2.0.0")
        self.assertIsNone(reboot["state"]["pending_slot"])
        self.assertIsNone(reboot["state"]["pending_upgrade"])
        self.assertEqual(reboot["state"]["slots"]["A"]["status"], "good")
        self.assertEqual(reboot["state"]["slots"]["B"]["status"], "good")
        self.assertFalse(reboot["state"]["bootloader"]["upgrade_available"])
        self.assertIsNone(reboot["state"]["bootloader"]["boot_once_slot"])
        self.assertIn("reboot_started", reboot["state"]["events"])
        self.assertIn("boot_confirmed", reboot["state"]["events"])
        self.assertEqual(committed["active_slot"], "A")
        self.assertEqual(committed["current_version"], "2.0.0")
        self.assertEqual(committed["slot_versions"], {"A": "2.0.0", "B": "1.0.0"})

    def test_failed_boot_rolls_back_to_b_and_persists_state(self):
        service = self.make_service()

        upgrade = service.upgrade("v2_success")
        reboot = service.reboot(simulate_boot_failure=True)
        persisted = self.read_persisted_state()
        reloaded_status = self.make_service().status()

        self.assertEqual(upgrade["state"]["pending_slot"], "A")
        self.assertTrue(reboot["ok"])
        self.assertEqual(reboot["state"]["active_slot"], "B")
        self.assertEqual(reboot["state"]["current_version"], "1.0.0")
        self.assertIsNone(reboot["state"]["pending_slot"])
        self.assertIsNone(reboot["state"]["pending_upgrade"])
        self.assertEqual(reboot["state"]["slots"]["A"]["status"], "failed")
        self.assertEqual(reboot["state"]["slots"]["B"]["status"], "good")
        self.assertEqual(reboot["state"]["ota_state"], "rolled_back")
        self.assertEqual(reboot["state"]["bootloader"]["boot_count"], 1)
        self.assertFalse(reboot["state"]["bootloader"]["upgrade_available"])
        self.assertIsNone(reboot["state"]["bootloader"]["boot_once_slot"])
        self.assertEqual(reboot["state"]["rollback_reason"], "boot_failed")
        self.assertTrue(reboot["state"]["boot_failed_at_reboot"])
        self.assertIn("reboot_started", reboot["state"]["events"])
        self.assertIn("boot_failed", reboot["state"]["events"])
        self.assertIn("rolled_back", reboot["state"]["events"])
        self.assertEqual(persisted["active_slot"], "B")
        self.assertEqual(persisted["current_version"], "1.0.0")
        self.assertIsNone(persisted["pending_slot"])
        self.assertEqual(reloaded_status["active_slot"], "B")
        self.assertEqual(reloaded_status["ota_state"], "rolled_back")

    def test_successful_boot_to_a_sets_next_upgrade_to_inactive_b(self):
        service = self.make_service()

        first_upgrade = service.upgrade("v2_success")
        first_reboot = service.reboot(simulate_boot_failure=False)
        second_upgrade = service.upgrade("v3_success")

        self.assertTrue(first_upgrade["ok"])
        self.assertEqual(first_reboot["state"]["active_slot"], "A")
        self.assertEqual(first_reboot["state"]["target_slot"], "B")
        self.assertTrue(second_upgrade["ok"])
        self.assertEqual(second_upgrade["state"]["active_slot"], "A")
        self.assertEqual(second_upgrade["state"]["pending_slot"], "B")
        self.assertEqual(second_upgrade["state"]["slots"]["B"]["version"], "3.0.0")
        self.assertEqual(second_upgrade["state"]["slots"]["B"]["status"], "pending")
        self.assertIn("written_to_B", second_upgrade["state"]["events"])


if __name__ == "__main__":
    unittest.main()
