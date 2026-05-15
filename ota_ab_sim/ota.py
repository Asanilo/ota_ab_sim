import hashlib
import json
import shutil
from pathlib import Path


class OtaService:
    """Server-owned OTA state machine and persistence."""

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.repo_dir = self.base_dir / "firmware_repo"
        self.data_dir = self.base_dir / "data"
        self.staging_dir = self.data_dir / "staging"
        self.state_path = self.data_dir / "state.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self.reset()

    def reset(self):
        state = {
            "active_slot": "B",
            "target_slot": "A",
            "rollback_slot": "B",
            "ota_state": "idle",
            "pending_upgrade": None,
            "slots": {
                "A": {
                    "version": None,
                    "firmware_name": None,
                    "checksum_md5": None,
                    "checksum_sha256": None,
                    "boot_status": "empty",
                },
                "B": {
                    "version": "1.0.0",
                    "firmware_name": "factory_v1.bin",
                    "checksum_md5": None,
                    "checksum_sha256": None,
                    "boot_status": "confirmed",
                },
            },
            "staged_firmware": None,
            "last_error": None,
        }
        self._save_raw(state)
        return self.status()

    def status(self):
        return self._with_derived_fields(self._load_raw())

    def list_firmware(self):
        firmware = []
        for manifest_path in sorted(self.repo_dir.glob("*.json")):
            metadata = self._read_json(manifest_path)
            name = metadata.get("name") or manifest_path.name.removesuffix(".json")
            if (self.repo_dir / name).exists():
                firmware.append(
                    {
                        "name": name,
                        "version": metadata.get("version"),
                        "md5": metadata.get("md5"),
                        "sha256": metadata.get("sha256"),
                    }
                )
        return {"firmware": firmware}

    def upgrade(self, firmware_name):
        state = self._load_raw()
        target_slot = state["target_slot"]
        source_path = self.repo_dir / firmware_name
        manifest_path = self.repo_dir / f"{firmware_name}.json"

        if not source_path.exists():
            return self._fail(state, f"Firmware not found: {firmware_name}", "download_failed")
        if not manifest_path.exists():
            return self._fail(state, f"Firmware metadata not found: {firmware_name}.json", "download_failed")

        metadata = self._read_json(manifest_path)
        staged_path = self.staging_dir / firmware_name
        shutil.copyfile(source_path, staged_path)

        actual_md5 = self._hash_file(staged_path, "md5")
        actual_sha256 = self._hash_file(staged_path, "sha256")
        expected_md5 = metadata.get("md5")
        expected_sha256 = metadata.get("sha256")

        staged = {
            "name": firmware_name,
            "version": metadata.get("version"),
            "staged_path": str(staged_path),
            "expected_md5": expected_md5,
            "actual_md5": actual_md5,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "verified": False,
        }
        state["staged_firmware"] = staged
        state["ota_state"] = "staged"
        state["last_error"] = None

        errors = []
        if expected_md5 != actual_md5:
            errors.append("MD5 mismatch")
        if expected_sha256 != actual_sha256:
            errors.append("SHA256 mismatch")
        if errors:
            staged["verified"] = False
            state["ota_state"] = "verification_failed"
            state["last_error"] = "; ".join(errors)
            self._save_raw(state)
            return {"ok": False, "state": self.status()}

        staged["verified"] = True
        state["ota_state"] = "pending_reboot"
        state["pending_upgrade"] = target_slot
        state["slots"][target_slot] = {
            "version": metadata.get("version"),
            "firmware_name": firmware_name,
            "checksum_md5": actual_md5,
            "checksum_sha256": actual_sha256,
            "boot_status": "pending",
        }
        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def reboot(self, simulate_boot_failure=False):
        state = self._load_raw()
        pending_slot = state.get("pending_upgrade")
        if state.get("ota_state") != "pending_reboot" or not pending_slot:
            return self._fail(state, "No pending upgrade to boot", state.get("ota_state", "idle"))

        if simulate_boot_failure:
            state["slots"][pending_slot]["boot_status"] = "failed"
            state["active_slot"] = state["rollback_slot"]
            state["pending_upgrade"] = None
            state["ota_state"] = "rolled_back"
            state["last_error"] = f"Boot failed on slot {pending_slot}; rolled back to slot {state['rollback_slot']}"
        else:
            previous_slot = state["active_slot"]
            state["slots"][pending_slot]["boot_status"] = "confirmed"
            state["active_slot"] = pending_slot
            state["rollback_slot"] = previous_slot
            state["pending_upgrade"] = None
            state["ota_state"] = "boot_confirmed"
            state["last_error"] = None

        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def _fail(self, state, message, ota_state):
        state["last_error"] = message
        state["ota_state"] = ota_state
        self._save_raw(state)
        return {"ok": False, "state": self.status()}

    def _load_raw(self):
        return self._read_json(self.state_path)

    def _save_raw(self, state):
        state = self._with_derived_fields(dict(state))
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _with_derived_fields(state):
        active_slot = state["active_slot"]
        state["current_version"] = state["slots"][active_slot]["version"]
        state["active_version"] = state["current_version"]
        state["slot_versions"] = {
            slot: slot_state["version"]
            for slot, slot_state in state["slots"].items()
        }
        return state

    @staticmethod
    def _read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def _hash_file(path, algorithm):
        digest = hashlib.new(algorithm)
        with Path(path).open("rb") as firmware:
            for chunk in iter(lambda: firmware.read(1024 * 64), b""):
                digest.update(chunk)
        return digest.hexdigest()
