import hashlib
import json
import shutil
from pathlib import Path


class OtaService:
    """Server-owned OTA package pipeline, A/B slot state, and persistence."""

    DEVICE_MODEL = "demo-board"

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.firmware_dir = self.base_dir / "firmware"
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
            "device_model": self.DEVICE_MODEL,
            "active_slot": "B",
            "target_slot": "A",
            "pending_slot": None,
            "pending_upgrade": None,
            "rollback_slot": None,
            "ota_state": "idle",
            "last_error": None,
            "events": ["reset"],
            "bootloader": {
                "upgrade_available": False,
                "boot_once_slot": None,
                "boot_count": 0,
                "boot_limit": 1,
            },
            "boot_attempts": 0,
            "max_boot_attempts": 1,
            "rollback_reason": None,
            "boot_failed_at_reboot": False,
            "slots": {
                "A": self._slot_state(
                    version=None,
                    status="empty",
                    file_path=self.slots_dir / "A" / "firmware.bin",
                    size=None,
                    md5=None,
                    sha256=None,
                    package_id=None,
                ),
                "B": self._slot_state(
                    version="1.0.0",
                    status="good",
                    file_path=b_slot_file,
                    size=b_size,
                    md5=b_md5,
                    sha256=b_sha256,
                    package_id="factory_v1",
                ),
            },
            "staged_package": None,
            "staged_firmware": None,
        }
        self._save_raw(state)
        return self.status()

    def status(self):
        return self._with_derived_fields(self._load_raw())

    def list_firmware(self):
        packages = []
        if not self.firmware_dir.exists():
            return {"firmware": packages}

        for package_dir in sorted(path for path in self.firmware_dir.iterdir() if path.is_dir()):
            manifest_path = package_dir / "manifest.json"
            payload_path = package_dir / "firmware.bin"
            if not manifest_path.exists() or not payload_path.exists():
                continue
            manifest = self._read_json(manifest_path)
            packages.append(
                {
                    "package_id": manifest.get("package_id"),
                    "version": manifest.get("version"),
                    "compatible_model": manifest.get("compatible_model"),
                    "slot_class": manifest.get("slot_class"),
                    "payload": manifest.get("payload", {}),
                }
            )
        return {"firmware": packages}

    def stage(self, package_id):
        state = self._load_raw()
        if not self._is_safe_package_id(package_id):
            return self._fail(state, f"Invalid package id: {package_id}", "invalid_package")

        source_dir = self.firmware_dir / package_id
        source_manifest = source_dir / "manifest.json"
        source_payload = source_dir / "firmware.bin"
        if not source_dir.is_dir() or not source_manifest.exists() or not source_payload.exists():
            return self._fail(state, f"Package not found: {package_id}", "package_not_found")

        staged_dir = self.staging_dir / package_id
        shutil.rmtree(staged_dir, ignore_errors=True)
        shutil.copytree(source_dir, staged_dir)

        staged_manifest = staged_dir / "manifest.json"
        staged_payload = staged_dir / "firmware.bin"
        manifest = self._read_json(staged_manifest)
        manifest_error = self._validate_manifest(manifest, package_id)
        if manifest_error:
            return self._fail(state, manifest_error, "manifest_invalid")

        state["staged_package"] = {
            "package_id": package_id,
            "path": str(staged_dir),
            "manifest_path": str(staged_manifest),
            "payload_path": str(staged_payload),
            "version": manifest.get("version"),
            "compatible_model": manifest.get("compatible_model"),
            "slot_class": manifest.get("slot_class"),
            "payload": manifest.get("payload", {}),
            "verified": False,
        }
        state["staged_firmware"] = state["staged_package"]
        state["ota_state"] = "staged"
        state["last_error"] = None
        self._record_event(state, "package_staged")
        self._record_event(state, "manifest_loaded")
        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def verify(self):
        state = self._load_raw()
        staged_package = state.get("staged_package")
        if state.get("ota_state") != "staged" or not staged_package:
            return self._fail(state, "No staged package to verify", state.get("ota_state", "idle"))

        manifest = self._read_json(staged_package["manifest_path"])
        payload = manifest["payload"]
        payload_path = Path(staged_package["payload_path"])
        actual_size, actual_md5, actual_sha256 = self._file_metadata(payload_path)

        errors = []
        if payload.get("size") != actual_size:
            errors.append("size mismatch")
        if payload.get("md5") != actual_md5:
            errors.append("MD5 mismatch")
        if payload.get("sha256") != actual_sha256:
            errors.append("SHA256 mismatch")

        staged_package.update(
            {
                "expected_size": payload.get("size"),
                "actual_size": actual_size,
                "expected_md5": payload.get("md5"),
                "actual_md5": actual_md5,
                "expected_sha256": payload.get("sha256"),
                "actual_sha256": actual_sha256,
                "verified": not errors,
            }
        )
        state["staged_package"] = staged_package
        state["staged_firmware"] = staged_package

        if errors:
            state["ota_state"] = "verification_failed"
            state["last_error"] = "; ".join(errors)
            self._record_event(state, "verification_failed")
            self._save_raw(state)
            return {"ok": False, "state": self.status()}

        state["ota_state"] = "verified"
        state["last_error"] = None
        self._record_event(state, "verified")
        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def install(self):
        state = self._load_raw()
        staged_package = state.get("staged_package")
        if state.get("ota_state") != "verified" or not staged_package or not staged_package.get("verified"):
            return self._fail(state, "No verified package to install", state.get("ota_state", "idle"))

        inactive_slot = self._inactive_slot(state["active_slot"])
        slot_file = self.slots_dir / inactive_slot / "firmware.bin"
        slot_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged_package["payload_path"], slot_file)
        slot_size, slot_md5, slot_sha256 = self._file_metadata(slot_file)

        state["slots"][inactive_slot] = self._slot_state(
            version=staged_package["version"],
            status="pending",
            file_path=slot_file,
            size=slot_size,
            md5=slot_md5,
            sha256=slot_sha256,
            package_id=staged_package["package_id"],
        )
        state["pending_slot"] = inactive_slot
        state["pending_upgrade"] = inactive_slot
        state["target_slot"] = inactive_slot
        state["rollback_slot"] = state["active_slot"]
        state["ota_state"] = "pending_reboot"
        state["bootloader"]["upgrade_available"] = True
        state["bootloader"]["boot_once_slot"] = inactive_slot
        state["rollback_reason"] = None
        state["boot_failed_at_reboot"] = False
        state["last_error"] = None
        self._record_event(state, f"written_to_{inactive_slot}")
        self._record_event(state, "pending_reboot")
        self._save_raw(state)
        return {"ok": True, "state": self.status()}

    def upgrade(self, package_id):
        staged = self.stage(package_id)
        if not staged["ok"]:
            return staged
        verified = self.verify()
        if not verified["ok"]:
            return verified
        return self.install()

    def reboot(self, simulate_boot_failure=False):
        state = self._load_raw()
        pending_slot = state.get("pending_slot") or state.get("pending_upgrade")
        if state.get("ota_state") != "pending_reboot" or not pending_slot:
            return self._fail(state, "No pending upgrade to boot", state.get("ota_state", "idle"))

        rollback_slot = state.get("rollback_slot") or self._inactive_slot(pending_slot)
        state["boot_attempts"] = state.get("boot_attempts", 0) + 1
        state["bootloader"]["boot_count"] = state["bootloader"].get("boot_count", 0) + 1
        self._record_event(state, "reboot_started")

        if simulate_boot_failure:
            state["slots"][pending_slot]["status"] = "failed"
            state["slots"][pending_slot]["boot_status"] = "failed"
            state["slots"][rollback_slot]["status"] = "good"
            state["slots"][rollback_slot]["boot_status"] = "confirmed"
            state["active_slot"] = rollback_slot
            state["pending_slot"] = None
            state["pending_upgrade"] = None
            state["ota_state"] = "rolled_back"
            state["bootloader"]["upgrade_available"] = False
            state["bootloader"]["boot_once_slot"] = None
            state["rollback_reason"] = "boot_failed"
            state["boot_failed_at_reboot"] = True
            state["last_error"] = f"boot failed on slot {pending_slot}, rolled back to {rollback_slot}"
            self._record_event(state, "boot_failed")
            self._record_event(state, "rolled_back")
        else:
            state["slots"][pending_slot]["status"] = "good"
            state["slots"][pending_slot]["boot_status"] = "confirmed"
            state["slots"][rollback_slot]["status"] = "good"
            state["slots"][rollback_slot]["boot_status"] = "confirmed"
            state["active_slot"] = pending_slot
            state["target_slot"] = rollback_slot
            state["rollback_slot"] = rollback_slot
            state["pending_slot"] = None
            state["pending_upgrade"] = None
            state["ota_state"] = "boot_confirmed"
            state["bootloader"]["upgrade_available"] = False
            state["bootloader"]["boot_once_slot"] = None
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

    def _validate_manifest(self, manifest, package_id):
        payload = manifest.get("payload", {})
        if manifest.get("package_id") != package_id:
            return "manifest package_id does not match directory"
        if manifest.get("compatible_model") != self.DEVICE_MODEL:
            return "manifest compatible_model does not match device"
        if manifest.get("slot_class") != "rootfs":
            return "manifest slot_class must be rootfs"
        if payload.get("filename") != "firmware.bin":
            return "manifest payload filename must be firmware.bin"
        return None

    @staticmethod
    def _with_derived_fields(state):
        state.setdefault("device_model", OtaService.DEVICE_MODEL)
        state.setdefault("events", [])
        state.setdefault(
            "bootloader",
            {
                "upgrade_available": False,
                "boot_once_slot": None,
                "boot_count": 0,
                "boot_limit": 1,
            },
        )
        state["boot_attempts"] = state["bootloader"].get("boot_count", state.get("boot_attempts", 0))
        state["max_boot_attempts"] = state["bootloader"].get("boot_limit", state.get("max_boot_attempts", 1))
        state.setdefault("rollback_reason", None)
        state.setdefault("boot_failed_at_reboot", False)
        state["pending_upgrade"] = state.get("pending_slot")
        active_slot = state["active_slot"]
        state["target_slot"] = state.get("target_slot") or OtaService._inactive_slot(active_slot)
        state["current_version"] = state["slots"][active_slot]["version"]
        state["active_version"] = state["current_version"]
        state["slot_versions"] = {
            slot: slot_state["version"]
            for slot, slot_state in state["slots"].items()
        }
        return state

    @staticmethod
    def _slot_state(version, status, file_path, size, md5, sha256, package_id):
        return {
            "version": version,
            "status": status,
            "boot_status": "confirmed" if status == "good" else status,
            "file_path": str(file_path),
            "size": size,
            "md5": md5,
            "sha256": sha256,
            "checksum_md5": md5,
            "checksum_sha256": sha256,
            "package_id": package_id,
            "firmware_name": package_id,
        }

    @staticmethod
    def _record_event(state, event):
        state.setdefault("events", []).append(event)

    @staticmethod
    def _read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def _is_safe_package_id(package_id):
        if not package_id or package_id in {".", ".."}:
            return False
        if "/" in package_id or "\\" in package_id:
            return False
        if Path(package_id).is_absolute():
            return False
        if ".." in package_id:
            return False
        return True

    @staticmethod
    def _inactive_slot(active_slot):
        return "A" if active_slot == "B" else "B"

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
