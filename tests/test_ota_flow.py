import hashlib
import json
import tempfile
import unittest
from pathlib import Path


def write_firmware(
    repo: Path,
    name: str,
    version: str,
    content: bytes,
    bad_md5: bool = False,
    bad_sha256: bool = False,
):
    firmware_path = repo / name
    firmware_path.write_bytes(content)
    metadata = {
        "name": name,
        "filename": name,
        "version": version,
        "size": len(content),
        "md5": "bad-md5" if bad_md5 else hashlib.md5(content).hexdigest(),
        "sha256": "bad-sha256" if bad_sha256 else hashlib.sha256(content).hexdigest(),
        "target_slot": "A",
        "compatible_model": "demo-board",
    }
    (repo / f"{name}.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


def write_index(repo: Path, entries):
    (repo / "index.json").write_text(json.dumps({"firmware": entries}), encoding="utf-8")


class OtaFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.repo = self.base_dir / "firmware_repo"
        self.repo.mkdir()
        firmware_entries = []
        firmware_entries.append(write_firmware(self.repo, "firmware_v2.bin", "2.0.0", b"firmware version 2\n"))
        firmware_entries.append(write_firmware(self.repo, "firmware_v3.bin", "3.0.0", b"firmware version 3\n"))
        firmware_entries.append(write_firmware(
            self.repo,
            "firmware_bad_checksum.bin",
            "9.9.9",
            b"corrupted firmware\n",
            bad_md5=True,
        ))
        firmware_entries.append(write_firmware(
            self.repo,
            "firmware_bad_sha256.bin",
            "9.9.8",
            b"sha256 corrupted firmware\n",
            bad_sha256=True,
        ))
        write_index(self.repo, firmware_entries)

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

        self.assertEqual(status["active_slot"], "B")
        self.assertEqual(status["current_version"], "1.0.0")
        self.assertEqual(status["target_slot"], "A")
        self.assertEqual(status["slot_versions"], {"A": None, "B": "1.0.0"})
        self.assertIsNone(status["pending_upgrade"])
        self.assertEqual(status["slots"]["B"]["version"], "1.0.0")
        self.assertIsNone(status["slots"]["A"]["version"])

    def test_checksum_failure_does_not_write_slot_a_and_is_persisted(self):
        service = self.make_service()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        result = service.upgrade("firmware_bad_checksum.bin")
        persisted = self.read_persisted_state()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["ota_state"], "verification_failed")
        self.assertIn("MD5", result["state"]["last_error"])
        self.assertIsNone(result["state"]["slots"]["A"]["version"])
        self.assertIsNone(persisted["slots"]["A"]["version"])
        self.assertEqual(persisted["ota_state"], "verification_failed")
        self.assertFalse(slot_file.exists())

    def test_sha256_failure_does_not_write_slot_a_and_is_persisted(self):
        service = self.make_service()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        result = service.upgrade("firmware_bad_sha256.bin")
        persisted = self.read_persisted_state()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["ota_state"], "verification_failed")
        self.assertIn("SHA256", result["state"]["last_error"])
        self.assertIsNone(result["state"]["slots"]["A"]["version"])
        self.assertIsNone(persisted["slots"]["A"]["version"])
        self.assertEqual(persisted["ota_state"], "verification_failed")
        self.assertFalse(slot_file.exists())

    def test_successful_upgrade_writes_slot_a_then_reboot_commits_a(self):
        service = self.make_service()
        expected_content = b"firmware version 2\n"
        expected_md5 = hashlib.md5(expected_content).hexdigest()
        expected_sha256 = hashlib.sha256(expected_content).hexdigest()

        upgrade = service.upgrade("firmware_v2.bin")
        pending = self.read_persisted_state()
        reboot = service.reboot(simulate_boot_failure=False)
        committed = self.read_persisted_state()
        slot_file = self.base_dir / "data" / "slots" / "A" / "firmware.bin"

        self.assertTrue(upgrade["ok"])
        self.assertEqual(upgrade["state"]["active_slot"], "B")
        self.assertEqual(upgrade["state"]["slots"]["A"]["version"], "2.0.0")
        self.assertEqual(upgrade["state"]["slots"]["A"]["boot_status"], "pending")
        self.assertEqual(upgrade["state"]["slots"]["A"]["file_path"], str(slot_file))
        self.assertEqual(upgrade["state"]["slots"]["A"]["size"], len(expected_content))
        self.assertEqual(upgrade["state"]["slots"]["A"]["checksum_md5"], expected_md5)
        self.assertEqual(upgrade["state"]["slots"]["A"]["checksum_sha256"], expected_sha256)
        self.assertTrue(slot_file.exists())
        self.assertEqual(hashlib.md5(slot_file.read_bytes()).hexdigest(), expected_md5)
        self.assertEqual(hashlib.sha256(slot_file.read_bytes()).hexdigest(), expected_sha256)
        self.assertEqual(upgrade["state"]["pending_upgrade"], "A")
        self.assertIn("staged", upgrade["state"]["events"])
        self.assertIn("verified", upgrade["state"]["events"])
        self.assertIn("written_to_A", upgrade["state"]["events"])
        self.assertIn("pending_reboot", upgrade["state"]["events"])
        self.assertEqual(pending["ota_state"], "pending_reboot")
        self.assertTrue(reboot["ok"])
        self.assertEqual(reboot["state"]["active_slot"], "A")
        self.assertEqual(reboot["state"]["current_version"], "2.0.0")
        self.assertIsNone(reboot["state"]["pending_upgrade"])
        self.assertIn("reboot_started", reboot["state"]["events"])
        self.assertIn("boot_confirmed", reboot["state"]["events"])
        self.assertEqual(committed["active_slot"], "A")
        self.assertEqual(committed["current_version"], "2.0.0")
        self.assertEqual(committed["slot_versions"], {"A": "2.0.0", "B": "1.0.0"})

    def test_failed_boot_rolls_back_to_b_and_persists_state(self):
        service = self.make_service()

        upgrade = service.upgrade("firmware_v2.bin")
        reboot = service.reboot(simulate_boot_failure=True)
        persisted = self.read_persisted_state()
        reloaded_status = self.make_service().status()

        self.assertEqual(upgrade["state"]["pending_upgrade"], "A")
        self.assertTrue(reboot["ok"])
        self.assertEqual(reboot["state"]["active_slot"], "B")
        self.assertEqual(reboot["state"]["current_version"], "1.0.0")
        self.assertIsNone(reboot["state"]["pending_upgrade"])
        self.assertEqual(reboot["state"]["slots"]["A"]["boot_status"], "failed")
        self.assertEqual(reboot["state"]["ota_state"], "rolled_back")
        self.assertEqual(reboot["state"]["boot_attempts"], 1)
        self.assertEqual(reboot["state"]["max_boot_attempts"], 1)
        self.assertEqual(reboot["state"]["rollback_reason"], "boot_failed")
        self.assertTrue(reboot["state"]["boot_failed_at_reboot"])
        self.assertIn("reboot_started", reboot["state"]["events"])
        self.assertIn("boot_failed", reboot["state"]["events"])
        self.assertIn("rolled_back", reboot["state"]["events"])
        self.assertEqual(persisted["active_slot"], "B")
        self.assertEqual(persisted["current_version"], "1.0.0")
        self.assertIsNone(persisted["pending_upgrade"])
        self.assertEqual(reloaded_status["active_slot"], "B")
        self.assertEqual(reloaded_status["ota_state"], "rolled_back")

    def test_successful_boot_to_a_sets_next_target_to_b_for_second_upgrade(self):
        service = self.make_service()

        first_upgrade = service.upgrade("firmware_v2.bin")
        first_reboot = service.reboot(simulate_boot_failure=False)
        second_upgrade = service.upgrade("firmware_v3.bin")

        self.assertTrue(first_upgrade["ok"])
        self.assertEqual(first_reboot["state"]["active_slot"], "A")
        self.assertEqual(first_reboot["state"]["target_slot"], "B")
        self.assertTrue(second_upgrade["ok"])
        self.assertEqual(second_upgrade["state"]["active_slot"], "A")
        self.assertEqual(second_upgrade["state"]["pending_upgrade"], "B")
        self.assertEqual(second_upgrade["state"]["slots"]["B"]["version"], "3.0.0")
        self.assertEqual(second_upgrade["state"]["slots"]["B"]["boot_status"], "pending")
        self.assertIn("written_to_B", second_upgrade["state"]["events"])

    def test_upgrade_rejects_firmware_not_listed_in_index(self):
        write_firmware(self.repo, "rogue.bin", "9.9.7", b"rogue firmware\n")
        service = self.make_service()

        result = service.upgrade("rogue.bin")
        persisted = self.read_persisted_state()

        self.assertFalse(result["ok"])
        self.assertIn("index", result["state"]["last_error"])
        self.assertIsNone(result["state"]["slots"]["A"]["version"])
        self.assertEqual(persisted["ota_state"], "index_rejected")


if __name__ == "__main__":
    unittest.main()
