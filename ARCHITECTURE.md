# ARCHITECTURE.md

# OTA A/B Simulator Architecture

## Overview

This project is a small Python simulation of an OTA control plane and A/B state machine.

It does not implement a real bootloader, flash driver, or device firmware update agent. The embedded concepts are represented with filesystem files and persistent JSON state:

- Firmware repository: `firmware_repo/`
- Staging area: `data/staging/`
- Simulated slots: `data/slots/A/firmware.bin` and `data/slots/B/firmware.bin`
- Persistent state: `data/state.json`

The initial active slot is `B`; the initial upgrade target slot is `A`.

## Client/Server Boundary

### Server Responsibilities

The server owns all OTA behavior:

- HTTP API endpoints.
- Persistent state initialization and mutation.
- Firmware repository index validation.
- Local firmware staging from `firmware_repo/` to `data/staging/`.
- MD5 and SHA256 calculation from actual file contents.
- Slot file writes under `data/slots/`.
- Pending boot state.
- Boot success/failure simulation.
- Rollback state.
- OTA event log.

### Client Responsibilities

The CLI client only:

- Parses user commands.
- Sends HTTP requests to the server.
- Prints JSON responses.

The client must not import `OtaService`, read/write `data/state.json`, copy firmware, inspect `firmware_repo/`, or mutate slot files directly.

## Current File Layout

```text
ota_ab_sim/
  __init__.py
  client.py
  ota.py
  server.py
tests/
  test_http_api.py
  test_ota_flow.py
firmware_repo/
  index.json
  firmware_v2.bin
  firmware_v2.bin.json
  firmware_bad_checksum.bin
  firmware_bad_checksum.bin.json
  firmware_bad_sha256.bin
  firmware_bad_sha256.bin.json
data/                 # runtime only, ignored by git
  state.json
  staging/
  slots/
    A/firmware.bin
    B/firmware.bin
```

## HTTP API

### `GET /status`

Returns the complete OTA state, including derived fields.

Important response fields:

- `active_slot`
- `current_version`
- `active_version`
- `slot_versions`
- `target_slot`
- `pending_upgrade`
- `ota_state`
- `events`
- `slots`
- `staged_firmware`
- `boot_attempts`
- `max_boot_attempts`
- `rollback_reason`
- `boot_failed_at_reboot`
- `last_error`

### `GET /firmware`

Returns the server-side firmware repository index.

The server reads `firmware_repo/index.json`; the client does not inspect the folder directly.

Index entry shape:

```json
{
  "version": "2.0.0",
  "filename": "firmware_v2.bin",
  "size": 19,
  "md5": "...",
  "sha256": "...",
  "target_slot": "A",
  "compatible_model": "demo-board"
}
```

### `POST /upgrade`

Stages, verifies, and writes firmware to the current target slot.

Request:

```json
{
  "firmware": "firmware_v2.bin"
}
```

Server-side behavior:

1. Check that the firmware filename is listed in `firmware_repo/index.json`.
2. Check that the firmware file and metadata file exist under `firmware_repo/`.
3. Copy the firmware to `data/staging/<filename>`.
4. Calculate actual MD5 and SHA256 from the staged file.
5. Compare actual hashes with metadata.
6. If either hash fails, set `ota_state` to `verification_failed` and do not write the target slot.
7. If both hashes pass, copy staged firmware to `data/slots/<target_slot>/firmware.bin`.
8. Record slot file path, size, MD5, SHA256, version, firmware name, and pending boot status.
9. Set `pending_upgrade` to the target slot and `ota_state` to `pending_reboot`.

Successful upgrade events:

```text
staged
verified
written_to_A
pending_reboot
```

If the current target slot is `B`, the write event is `written_to_B`.

### `POST /reboot`

Simulates rebooting into the pending slot.

Request:

```json
{
  "simulate_boot_failure": false
}
```

Success behavior:

- Increment `boot_attempts`.
- Record `reboot_started`.
- Mark pending slot as `confirmed`.
- Set `active_slot` to the pending slot.
- Set `rollback_slot` to the previous active slot.
- Set `target_slot` to the previous active slot, enabling the next upgrade to use the inactive slot.
- Clear `pending_upgrade`.
- Set `ota_state` to `boot_confirmed`.
- Record `boot_confirmed`.

Failure behavior:

- Increment `boot_attempts`.
- Record `reboot_started`.
- Mark pending slot as `failed`.
- Keep or restore `active_slot` to `rollback_slot`.
- Clear `pending_upgrade`.
- Set `ota_state` to `rolled_back`.
- Set `rollback_reason` to `boot_failed`.
- Set `boot_failed_at_reboot` to `true`.
- Record `boot_failed` and `rolled_back`.

### `POST /reset`

Restores a deterministic initial state for demos and tests.

Reset behavior:

- Clears runtime staging and slot directories.
- Recreates `data/slots/B/firmware.bin` as the factory firmware.
- Leaves `data/slots/A/firmware.bin` absent until a successful upgrade writes it.
- Sets active slot to `B`.
- Sets target slot to `A`.
- Clears pending upgrade and rollback error state.

## Persistent State Model

Example state:

```json
{
  "active_slot": "B",
  "current_version": "1.0.0",
  "target_slot": "A",
  "rollback_slot": "B",
  "pending_upgrade": null,
  "ota_state": "idle",
  "events": ["reset"],
  "boot_attempts": 0,
  "max_boot_attempts": 1,
  "rollback_reason": null,
  "boot_failed_at_reboot": false,
  "slots": {
    "A": {
      "version": null,
      "firmware_name": null,
      "file_path": "data/slots/A/firmware.bin",
      "size": null,
      "checksum_md5": null,
      "checksum_sha256": null,
      "boot_status": "empty"
    },
    "B": {
      "version": "1.0.0",
      "firmware_name": "factory_v1.bin",
      "file_path": "data/slots/B/firmware.bin",
      "size": 20,
      "checksum_md5": "...",
      "checksum_sha256": "...",
      "boot_status": "confirmed"
    }
  },
  "staged_firmware": null,
  "last_error": null
}
```

## State Machine

```text
idle
  -> staged
  -> verification_failed

idle
  -> staged
  -> verified
  -> written_to_<target_slot>
  -> pending_reboot
  -> boot_confirmed

pending_reboot
  -> reboot_started
  -> boot_failed
  -> rolled_back
```

The event log records intermediate steps even though `POST /upgrade` remains a single API call.

## Control-Flow Invariants

- Firmware must be listed in `firmware_repo/index.json` before upgrade.
- MD5 and SHA256 are calculated from actual staged file contents.
- Slot file writes happen only after both hashes pass.
- Checksum failure must leave the target slot file absent or unchanged.
- Writing a slot does not immediately change `active_slot`.
- Boot failure is simulated during `POST /reboot`, after the target slot has been written and marked pending.
- Rollback clears `pending_upgrade` and persists `active_slot` as the rollback slot.
- After a successful boot into `A`, the next `target_slot` becomes `B`.
- `data/` is runtime state and must not be committed.

