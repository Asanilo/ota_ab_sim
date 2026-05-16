# SPEC.md

# OTA A/B Simulator Specification

## Product Scope

This project is a CLI plus HTTP server simulation of an OTA A/B partition upgrade flow.

It provides:

- A real HTTP server process.
- A CLI client that talks to the server only through HTTP.
- Local package-based dummy firmware under `firmware/<package_id>/`.
- Server-owned staging under `data/staging/<package_id>/`.
- Simulated slot files under `data/slots/<slot>/firmware.bin`.
- Persistent JSON OTA state.

It does not provide:

- Real bootloader integration.
- Real flash partition writes.
- Real network download.
- Authentication, database, Docker, or frontend framework.

## Acceptance Criteria

### AC1: Current State And Version Are Queryable

Command:

```bash
python3 -m ota_ab_sim.client status
```

Expected observable fields:

- `device_model`
- `active_slot`
- `current_version`
- `slot_versions`
- `target_slot`
- `pending_slot`
- `pending_upgrade`
- `staged_package`
- `slots.A.status`
- `slots.B.status`
- `ota_state`
- `last_error`

Initial expected state:

- `active_slot` is `B`
- `current_version` is `1.0.0`
- `target_slot` is `A`
- `pending_slot` is `null`
- slot `B.status` is `good`
- slot `A.status` is `empty`

### AC2: Firmware Uses Package Directory Layout

Firmware packages live under:

```text
firmware/<package_id>/
  manifest.json
  firmware.bin
```

The manifest includes:

- `package_id`
- `version`
- `compatible_model`
- `slot_class`
- `payload.filename`
- `payload.size`
- `payload.md5`
- `payload.sha256`

Command:

```bash
python3 -m ota_ab_sim.client firmware
```

Expected result:

- Server lists package ids and manifest metadata.
- Client does not read `firmware/` directly.

### AC3: Staging Copies The Whole Package Directory

Command:

```bash
python3 -m ota_ab_sim.client stage v2_success
```

Expected result:

- Server creates `data/staging/v2_success/manifest.json`.
- Server creates `data/staging/v2_success/firmware.bin`.
- State records `staged_package`.
- Events include `package_staged` and `manifest_loaded`.
- No slot is written during stage.

Security requirement:

- Package ids containing `..`, `/`, `\`, or absolute path syntax are rejected.

### AC4: Verification Reads Staged Manifest And Staged Firmware

Command:

```bash
python3 -m ota_ab_sim.client verify
```

Expected behavior:

- Server reads `data/staging/<package_id>/manifest.json`.
- Server hashes `data/staging/<package_id>/firmware.bin`.
- MD5, SHA256, and size must match the manifest payload.
- On success, `staged_package.verified` is `true`.
- On failure, `ota_state` is `verification_failed` and inactive slot file is absent or unchanged.

### AC5: Install Writes Only The Inactive Slot

Command:

```bash
python3 -m ota_ab_sim.client install
```

Expected behavior:

- If active slot is `B`, install writes `data/slots/A/firmware.bin`.
- If active slot is `A`, install writes `data/slots/B/firmware.bin`.
- Slot metadata records file path, size, MD5, SHA256, version, package id, and `status: pending`.
- State sets `pending_slot` and compatibility alias `pending_upgrade`.
- Bootloader fields set `upgrade_available: true` and `boot_once_slot`.

### AC6: One-Shot Upgrade Is Preserved

Command:

```bash
python3 -m ota_ab_sim.client upgrade v2_success
```

Expected behavior:

- Internally runs stage, verify, and install.
- Response includes events proving `package_staged`, `manifest_loaded`, `verified`, `written_to_A`, and `pending_reboot`.

### AC7: Reboot Success Commits Pending Slot

Command:

```bash
python3 -m ota_ab_sim.client reboot --boot-ok
```

Expected behavior:

- `active_slot` becomes `pending_slot`.
- New active slot `status` becomes `good`.
- Previous active slot remains `good`.
- `pending_slot` and `pending_upgrade` become `null`.
- Bootloader upgrade flags are cleared.
- After booting into `A`, the next inactive target is `B`.

### AC8: Boot Failure Rolls Back

Command:

```bash
python3 -m ota_ab_sim.client reboot --boot-fail
```

Expected behavior:

- Active slot returns to `rollback_slot`.
- Failed slot `status` becomes `failed`.
- Previous slot remains `good`.
- `pending_slot` and `pending_upgrade` become `null`.
- `rollback_reason` is `boot_failed`.
- Events include `reboot_started`, `boot_failed`, and `rolled_back`.
- Rollback state persists after reloading `data/state.json`.

### AC9: Client/Server Separation Is Real

Expected proof:

- Server starts as a separate HTTP process.
- Client accepts `--server http://127.0.0.1:8000`.
- Client does not import server state classes.
- Client does not read or write `firmware/`, `data/staging/`, `data/slots/`, or `data/state.json`.

## Definition Of Done

- `python3 -m unittest discover -s tests -v` passes.
- Tests cover package staging, checksum failure, successful upgrade, failed boot rollback, path traversal rejection, and HTTP/CLI execution.
- README and demo script show package-based one-shot and step-by-step flows.
- `data/` does not enter git.
