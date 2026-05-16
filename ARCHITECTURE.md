# ARCHITECTURE.md

# OTA A/B Simulator Architecture

## Overview

This is a Python simulation of an OTA control plane and A/B state machine. It does not implement a real bootloader, flash driver, or device firmware updater.

The simulation uses filesystem files and persistent JSON state:

- Firmware repository: `firmware/<package_id>/`
- Staging area: `data/staging/<package_id>/`
- Simulated slots: `data/slots/A/firmware.bin` and `data/slots/B/firmware.bin`
- State: `data/state.json`

Initial state:

- `active_slot`: `B`
- inactive install target: `A`
- `pending_slot`: `null`

## Firmware Package Model

Package layout:

```text
firmware/
  v2_success/
    manifest.json
    firmware.bin
```

Manifest shape:

```json
{
  "package_id": "v2_success",
  "version": "2.0.0",
  "compatible_model": "demo-board",
  "slot_class": "rootfs",
  "payload": {
    "filename": "firmware.bin",
    "size": 19,
    "md5": "...",
    "sha256": "..."
  }
}
```

Validation rules:

- Client sends only a package id, for example `v2_success`.
- Server rejects package ids containing path separators, absolute path syntax, or `..`.
- `manifest.package_id` must match the directory name.
- `payload.filename` must be `firmware.bin`.
- `compatible_model` must match `device_model`.
- `slot_class` must be `rootfs`.
- MD5, SHA256, and size are verified from the staged payload, not from the repository source.

## Client/Server Boundary

The server owns:

- Package discovery under `firmware/`.
- Package directory staging.
- Manifest loading.
- Checksum verification.
- Inactive slot selection.
- Slot file writes.
- Boot success/failure simulation.
- Rollback and persistent state.

The client only:

- Parses commands.
- Calls HTTP APIs.
- Prints JSON.

The client must not read package files, staging files, slot files, or `data/state.json`.

## HTTP API

```text
GET  /status
GET  /firmware
POST /stage    {"package": "v2_success"}
POST /verify   {}
POST /install  {}
POST /upgrade  {"package": "v2_success"}
POST /reboot   {"simulate_boot_failure": true}
POST /reset    {}
```

`POST /upgrade` is kept for demo speed. Internally it runs:

```text
stage -> verify -> install
```

## State Model

State is stored in `data/state.json`.

Important fields:

```json
{
  "device_model": "demo-board",
  "active_slot": "B",
  "target_slot": "A",
  "pending_slot": null,
  "pending_upgrade": null,
  "rollback_slot": null,
  "ota_state": "idle",
  "last_error": null,
  "events": ["reset"],
  "bootloader": {
    "upgrade_available": false,
    "boot_once_slot": null,
    "boot_count": 0,
    "boot_limit": 1
  },
  "slots": {
    "A": {
      "version": null,
      "status": "empty",
      "file_path": "data/slots/A/firmware.bin",
      "size": null,
      "md5": null,
      "sha256": null
    },
    "B": {
      "version": "1.0.0",
      "status": "good",
      "file_path": "data/slots/B/firmware.bin",
      "size": 20,
      "md5": "...",
      "sha256": "..."
    }
  },
  "staged_package": null
}
```

Compatibility aliases are retained for older demo checks:

- `pending_upgrade` mirrors `pending_slot`.
- slot `boot_status` mirrors slot `status`.
- slot `checksum_md5` and `checksum_sha256` mirror `md5` and `sha256`.
- `staged_firmware` mirrors `staged_package`.

## State Transitions

### Reset

- Clears `data/staging/` and `data/slots/`.
- Recreates slot `B` factory firmware.
- Leaves slot `A` empty.
- Sets `ota_state` to `idle`.

### Stage

```text
idle -> staged
```

Server behavior:

- Validates package id.
- Copies the whole package directory to `data/staging/<package_id>/`.
- Reads staged `manifest.json`.
- Records `staged_package`.
- Appends `package_staged` and `manifest_loaded`.
- Does not write any slot file.

### Verify

```text
staged -> verified
staged -> verification_failed
```

Server behavior:

- Reads staged manifest and staged `firmware.bin`.
- Calculates size, MD5, and SHA256 from staged payload.
- On mismatch, records `verification_failed` and leaves inactive slot absent or unchanged.
- On success, sets `staged_package.verified` to `true`.

### Install

```text
verified -> pending_reboot
```

Server behavior:

- Selects the inactive slot automatically.
- Copies staged `firmware.bin` to `data/slots/<inactive_slot>/firmware.bin`.
- Records slot path, size, MD5, SHA256, version, and package id.
- Sets slot `status` to `pending`.
- Sets `pending_slot` and `pending_upgrade`.
- Sets `rollback_slot` to the current active slot.
- Sets bootloader `upgrade_available` and `boot_once_slot`.
- Appends `written_to_A` or `written_to_B`, then `pending_reboot`.

### Reboot Success

```text
pending_reboot -> boot_confirmed
```

- `active_slot` becomes `pending_slot`.
- New active slot status becomes `good`.
- Previous slot remains `good`.
- `pending_slot` and `pending_upgrade` become `null`.
- `rollback_slot` remains the previous good slot for observability.
- `target_slot` becomes the inactive slot for the next upgrade.
- Bootloader upgrade flags are cleared.
- Events include `reboot_started` and `boot_confirmed`.

### Reboot Failure

```text
pending_reboot -> rolled_back
```

- Active slot becomes `rollback_slot`.
- Failed slot status becomes `failed`.
- Previous slot remains `good`.
- `pending_slot` and `pending_upgrade` become `null`.
- Bootloader upgrade flags are cleared.
- `bootloader.boot_count` increments.
- `rollback_reason` is `boot_failed`.
- Events include `reboot_started`, `boot_failed`, and `rolled_back`.

## Invariants

- The client cannot bypass the server state machine.
- Verification reads only staged files.
- Slot writes happen only after verification succeeds.
- Install writes only the inactive slot.
- Checksum failure prevents slot file writes.
- Reboot failure persists rollback state.
- `data/` is runtime state and must not be committed.
