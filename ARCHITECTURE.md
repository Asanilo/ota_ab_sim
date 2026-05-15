# ARCHITECTURE.md

# OTA A/B Simulator Architecture

## Overview

The project uses a simple client/server architecture.

- Server: owns firmware repository access, staging, checksum verification, partition simulation, reboot simulation, rollback, and persistent state.
- Client: provides user commands and calls the server through HTTP only.

The design intentionally avoids a database, Docker, authentication, frontend framework, or background worker.

## Proposed File Layout

```text
ota_ab_sim/
  server.py
  client.py
  api.py
  state_store.py
  checksum.py
  firmware.py
  ota_flow.py
tests/
  test_ota_flow.py
  test_http_api.py
firmware_repo/
  firmware_v2.bin
  firmware_v2.json
data/
  state.json
  staging/
```

This layout is a target for implementation, not code that already exists.

## Server Responsibilities

The server must:

- Expose HTTP APIs.
- Initialize persistent state with active slot `B`.
- Read dummy firmware from `firmware_repo/`.
- Stage firmware by copying it into `data/staging/`.
- Calculate and verify MD5 and SHA256.
- Reject writes if verification fails.
- Simulate writing verified firmware to slot `A`.
- Mark slot `A` as pending.
- Simulate reboot and boot result.
- Persist successful slot switch or rollback.

## Client Responsibilities

The client must:

- Parse CLI arguments.
- Send HTTP requests to the server.
- Print server responses clearly.
- Never directly mutate server state files.
- Never stage firmware by copying files itself.

The client may display fields from server responses, but the server remains the source of truth.

## HTTP API List

The implemented server exposes both simple paths (`/status`) and `/api/...` aliases for compatibility. The README uses the simple paths.

### `GET /status`

Returns full OTA state.

Response includes:

- `active_slot`
- `current_version`
- `slot_versions`
- `target_slot`
- `rollback_slot`
- `ota_state`
- `pending_upgrade`
- `slots`
- `staged_firmware`
- `last_error`

### `GET /firmware`

Lists available dummy firmware files from the server-side firmware repository.

### `POST /upgrade`

Stages firmware, verifies MD5 and SHA256, writes verified firmware to target slot `A`, and marks slot A pending.

```json
{
  "firmware": "firmware_v2.bin"
}
```

Server-side work:

- Copy firmware from `firmware_repo/` to `data/staging/`.
- Read expected `md5`, `sha256`, and `version` from the firmware metadata JSON.
- Calculate actual MD5 and SHA256 from staged file contents.
- Reject the upgrade if either checksum mismatches.
- Write slot A only after both checks pass.

Success result:

- slot A version is updated.
- slot A boot status is `pending`.
- active slot remains `B`.
- `pending_upgrade` becomes `A`.
- `ota_state` becomes `pending_reboot`.

Failure result:

- `ota_state` becomes `verification_failed`.
- `staged_firmware.verified` is `false`.
- slot A remains unchanged.

### `POST /reboot`

Simulates reboot into pending slot `A`.

Request:

```json
{
  "simulate_boot_failure": true
}
```

Success path:

- `simulate_boot_failure` is `false`.
- active slot changes to `A`.
- slot A boot status becomes `confirmed`.
- `ota_state` becomes `boot_confirmed`.

Failure path:

- `simulate_boot_failure` is `true`.
- boot failure is applied during reboot after slot A is already pending.
- active slot rolls back to `B`.
- slot A boot status becomes `failed`.
- `ota_state` becomes `rolled_back`.
- state is persisted.

### `POST /reset`

Development and demo helper to restore the initial state.

Expected result:

- active slot is `B`.
- target slot is `A`.
- slot B contains version `1.0.0`.
- slot A is empty or inactive.
- `ota_state` is `idle`.

## Data Model

Persistent state should be stored as JSON, for example `data/state.json`.

```json
{
  "active_slot": "B",
  "target_slot": "A",
  "rollback_slot": "B",
  "ota_state": "idle",
  "pending_upgrade": null,
  "slots": {
    "A": {
      "version": null,
      "firmware_name": null,
      "checksum_md5": null,
      "checksum_sha256": null,
      "boot_status": "empty"
    },
    "B": {
      "version": "1.0.0",
      "firmware_name": "factory_v1.bin",
      "checksum_md5": null,
      "checksum_sha256": null,
      "boot_status": "confirmed"
    }
  },
  "staged_firmware": null,
  "last_error": null
}
```

`staged_firmware` shape:

```json
{
  "name": "firmware_v2.bin",
  "version": "2.0.0",
  "staged_path": "data/staging/firmware_v2.bin",
  "expected_md5": "...",
  "actual_md5": "...",
  "expected_sha256": "...",
  "actual_sha256": "...",
  "verified": true
}
```

## OTA State Machine

```text
idle
  -> pending_reboot
  -> boot_confirmed

idle
  -> verification_failed

pending_reboot
  -> rolled_back
```

Detailed transition rules:

- `idle -> pending_reboot`: `POST /upgrade` copies firmware from local repository to staging, verifies MD5 and SHA256, writes slot A, and marks it pending.
- `idle -> verification_failed`: `POST /upgrade` finds an MD5 or SHA256 mismatch and leaves slot A unchanged.
- `pending_reboot -> boot_confirmed`: reboot succeeds and active slot becomes A.
- `pending_reboot -> rolled_back`: reboot simulates boot failure and active slot returns to B.

## Control-Flow Invariants

- Slot A cannot be written before successful checksum verification.
- Slot A write does not immediately change active slot.
- Boot failure can only be simulated from `pending_reboot`.
- Rollback must update persistent state.
- The client cannot bypass the server state machine.
