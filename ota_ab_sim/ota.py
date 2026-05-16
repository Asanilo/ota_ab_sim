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
        self.slots_dir = self.data_dir / "slots"
        self.state_path = self.data_dir / "state.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.slots_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self.reset()

    def reset(self):
        shutil.rmtree(self.staging_dir, ignore_errors=True)
        shutil.rmtree(self.slots_dir, ignore_errors=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        (self.slots_dir / "A").mkdir(parents=True, exist_ok=True)
        (self.slots_dir / "B").mkdir(parents=True, exist_ok=True)
        b_slot_file = self.slots_dir / "B" / "firmware.bin"
        b_slot_file.write_bytes(b"factory firmware v1\n")
        b_size, b_md5, b_sha256 = self._file_metadata(b_slot_file)
        state = {
            "active_slot": "B",
            "target_slot": "A",
            "rollback_slot": "B",
            "ota_state": "idle",
            "pending_upgrade": None,
            "events": ["reset"],
            "boot_attempts": 0,
            "max_boot_attempts": 1,
            "rollback_reason": None,
            "boot_failed_at_reboot": False,
            "slots": {
                "A": {
                    "version": None,
                    "firmware_name": None,
                    "file_path": str(self.slots_dir / "A" / "firmware.bin"),
                    "size": None,
                    "checksum_md5": None,
                    "checksum_sha256": None,
                    "boot_status": "empty",
                },
                "B": {
                    "version": "1.0.0",
                    "firmware_name": "factory_v1.bin",
                    "file_path": str(b_slot_file),
                    "size": b_size,
                    "checksum_md5": b_md5,
                    "checksum_sha256": b_sha256,
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
        index_path = self.repo_dir / "index.json"
        if index_path.exists():
            return self._read_json(index_path)

        firmware = []
        for manifest_path in sorted(self.repo_dir.glob("*.json")):
            if manifest_path.name == "index.json":
                continue
            metadata = self._read_json(manifest_path)
            name = metadata.get("name") or manifest_path.name.removesuffix(".json")
            if (self.repo_dir / name).exists():
                size = (self.repo_dir / name).stat().st_size
                firmware.append(
                    {
                        "name": name,
                        "filename": name,
                        "version": metadata.get("version"),
                        "size": size,
                        "md5": metadata.get("md5"),
                        "sha256": metadata.get("sha256"),
                        "target_slot": metadata.get("target_slot", "A"),
                        "compatible_model": metadata.get("compatible_model", "demo-board"),
                    }
                )
        return {"firmware": firmware}

    def upgrade(self, firmware_name):
        state = self._load_raw()
        target_slot = state["target_slot"]
        source_path = self.repo_dir / firmware_name
        manifest_path = self.repo_dir / f"{firmware_name}.json"
        index_entry = self._firmware_index_entry(firmware_name)

        if not source_path.exists():
            return self._fail(state, f"Firmware not found: {firmware_name}", "download_failed")
        if not manifest_path.exists():
            return self._fail(state, f"Firmware metadata not found: {firmware_name}.json", "download_failed")
        if index_entry is None:
            return self._fail(state, f"Firmware not listed in firmware_repo/index.json: {firmware_name}", "index_rejected")

        metadata = self._read_json(manifest_path)
        metadata.update(index_entry)
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
            "size": staged_path.stat().st_size,
            "expected_md5": expected_md5,
            "actual_md5": actual_md5,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "verified": False,
        }
        state["staged_firmware"] = staged
        state["ota_state"] = "staged"
        state["last_error"] = None
        self._record_event(state, "staged")

        errors = []
        if expected_md5 != actual_md5:
            errors.append("MD5 mismatch")
        if expected_sha256 != actual_sha256:
            errors.append("SHA256 mismatch")
        if errors:
            staged["verified"] = False
            state["ota_state"] = "verification_failed"
            state["last_error"] = "; ".join(errors)
            self._record_event(state, "verification_failed")
            self._save_raw(state)
            return {"ok": False, "state": self.status()}

        staged["verified"] = True
        self._record_event(state, "verified")
        slot_file = self.slots_dir / target_slot / "firmware.bin"
        slot_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged_path, slot_file)
        slot_size, slot_md5, slot_sha256 = self._file_metadata(slot_file)
        self._record_event(state, f"written_to_{target_slot}")
        state["ota_state"] = "pending_reboot"
        state["pending_upgrade"] = target_slot
        state["boot_attempts"] = 0
        state["rollback_reason"] = None
        state["boot_failed_at_reboot"] = False
        state["slots"][target_slot] = {
            "version": metadata.get("version"),
            "firmware_name": firmware_name,
            "file_path": str(slot_file),
            "size": slot_size,
            "checksum_md5": slot_md5,
            "checksum_sha256": slot_sha256,
            "boot_status": "pending",
        }
        self._record_event(state, "pending_reboot")
        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def reboot(self, simulate_boot_failure=False):
        state = self._load_raw()
        pending_slot = state.get("pending_upgrade")
        if state.get("ota_state") != "pending_reboot" or not pending_slot:
            return self._fail(state, "No pending upgrade to boot", state.get("ota_state", "idle"))

        state["boot_attempts"] = state.get("boot_attempts", 0) + 1
        self._record_event(state, "reboot_started")
        if simulate_boot_failure:
            state["slots"][pending_slot]["boot_status"] = "failed"
            state["active_slot"] = state["rollback_slot"]
            state["pending_upgrade"] = None
            state["ota_state"] = "rolled_back"
            state["rollback_reason"] = "boot_failed"
            state["boot_failed_at_reboot"] = True
            state["last_error"] = f"Boot failed on slot {pending_slot}; rolled back to slot {state['rollback_slot']}"
            self._record_event(state, "boot_failed")
            self._record_event(state, "rolled_back")
        else:
            previous_slot = state["active_slot"]
            state["slots"][pending_slot]["boot_status"] = "confirmed"
            state["active_slot"] = pending_slot
            state["rollback_slot"] = previous_slot
            state["target_slot"] = previous_slot
            state["pending_upgrade"] = None
            state["ota_state"] = "boot_confirmed"
            state["rollback_reason"] = None
            state["boot_failed_at_reboot"] = False
            state["last_error"] = None
            self._record_event(state, "boot_confirmed")

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
        state.setdefault("events", [])
        state.setdefault("boot_attempts", 0)
        state.setdefault("max_boot_attempts", 1)
        state.setdefault("rollback_reason", None)
        state.setdefault("boot_failed_at_reboot", False)
        active_slot = state["active_slot"]
        state["current_version"] = state["slots"][active_slot]["version"]
        state["active_version"] = state["current_version"]
        state["slot_versions"] = {
            slot: slot_state["version"]
            for slot, slot_state in state["slots"].items()
        }
        return state

    @staticmethod
    def _record_event(state, event):
        state.setdefault("events", []).append(event)

    @staticmethod
    def _read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def _firmware_index_entry(self, firmware_name):
        index_path = self.repo_dir / "index.json"
        if not index_path.exists():
            return None
        index = self._read_json(index_path)
        for entry in index.get("firmware", []):
            if entry.get("filename") == firmware_name or entry.get("name") == firmware_name:
                return entry
        return None

    @classmethod
    def _file_metadata(cls, path):
        path = Path(path)
        return (
            path.stat().st_size,
            cls._hash_file(path, "md5"),
            cls._hash_file(path, "sha256"),
        )

    @staticmethod
    def _hash_file(path, algorithm):
        digest = hashlib.new(algorithm)
        with Path(path).open("rb") as firmware:
            for chunk in iter(lambda: firmware.read(1024 * 64), b""):
                digest.update(chunk)
        return digest.hexdigest()
