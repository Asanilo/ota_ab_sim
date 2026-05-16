# OTA A/B Engineering Roadmap

This document is the next-step implementation brief for improving the OTA A/B simulator while keeping the assignment scope small, reviewable, and standard-library friendly.

The current project already implements the required CLI + HTTP server OTA flow. The changes below are intended to make the simulation closer to common embedded Linux OTA concepts without turning it into a full bootloader, partition-table, or fleet-management system.

## External References To Borrow From

Use these projects as design references. Do not vendor their code and do not add their runtime dependencies.

### Mender

Reference: https://docs.mender.io/operating-system-updates-yocto-project/overview

Concepts to borrow:

- Active/inactive A/B root filesystem slots.
- Write the update to the inactive slot.
- Keep a persistent data area that survives rootfs updates.
- Reboot into the updated slot, then commit it as good.
- Roll back to the previously working slot if the new slot does not boot.

Optional simulated fields inspired by Mender/U-Boot integration:

- `upgrade_available`
- `boot_count`
- `boot_limit`
- `boot_once_slot`
- `committed`

Do not implement real U-Boot integration. These fields should remain JSON state fields for the simulator.

### RAUC

Reference: https://rauc.readthedocs.io/en/stable/basic.html

Concepts to borrow:

- A firmware package should contain a manifest plus one or more payload files.
- A manifest should describe payload metadata, compatibility, checksums, and target slot class.
- Installation should map payloads only to inactive slots.
- Slot configuration should include the slot name, path, class, and state.

This is the strongest reference for the package-directory and manifest redesign.

### SWUpdate

Reference: https://swupdate.org/features

Concepts to borrow:

- Atomic update language: an update either reaches a valid pending boot state or leaves the current active slot usable.
- Local update and OTA update can share the same install pipeline after the package reaches staging.
- Bootloader handoff and rollback can be represented as simulator state transitions.

Do not implement SWU parsing or handlers. Keep the simulator JSON based.

### Eclipse hawkBit

Reference: https://eclipse.dev/hawkbit/

Concepts to borrow:

- Update packages can contain more than one file.
- A server can expose package metadata through HTTP.
- Rollout/deployment concepts exist, but they are out of scope for this assignment.

Do not add fleet management, users, groups, rollout scheduling, a database, or a web UI.

## Accepted Scope

Implement a more realistic local OTA package pipeline:

```text
firmware/<package_id>/
  manifest.json
  firmware.bin
    |
    | stage/download simulation
    v
data/staging/<package_id>/
  manifest.json
  firmware.bin
    |
    | verify MD5/SHA256 from staged contents
    v
data/slots/<inactive_slot>/firmware.bin
    |
    | reboot simulation
    v
commit updated slot or roll back to previous good slot
```

Keep these constraints:

- Keep Python standard library only.
- Keep C/S separation: the client must call HTTP APIs only.
- The client must not read firmware package files, staging files, slot files, or state files.
- The server owns package discovery, staging, checksum verification, slot writes, reboot simulation, rollback, and persistent state.
- Do not add Docker, authentication, database storage, a frontend framework, real bootloader integration, or real partition writes.

## Target Firmware Repository Layout

Replace the flat firmware files with package directories:

```text
firmware/
  v2_success/
    manifest.json
    firmware.bin
  v2_bad_md5/
    manifest.json
    firmware.bin
  v2_bad_sha256/
    manifest.json
    firmware.bin
```

Keep `firmware_repo/` only if backward compatibility is needed. New implementation and docs should use `firmware/`.

### Manifest Schema

Each package must contain `manifest.json`:

```json
{
  "package_id": "v2_success",
  "version": "2.0.0",
  "compatible_model": "demo-board",
  "slot_class": "rootfs",
  "payload": {
    "filename": "firmware.bin",
    "size": 19,
    "md5": "abcb832ece223c927088c63fc7fcf16d",
    "sha256": "926a83d8db81b8cf37ff750b9450ae9c908588975148c6266b32015dbdbcc621"
  }
}
```

Validation rules:

- `package_id` must match the directory name.
- `payload.filename` must be `firmware.bin` for this assignment.
- `payload.size`, `payload.md5`, and `payload.sha256` must be checked against the staged payload file, not the repository source file.
- `compatible_model` must match the simulated device model in server state, for example `demo-board`.
- `slot_class` should be `rootfs`.

Do not accept arbitrary path strings from the client. The client should pass a package id such as `v2_success`; the server resolves it under `firmware/<package_id>/`.

## Target Staging Behavior

Staging should simulate the download step.

Input:

```bash
python3 -m ota_ab_sim.client stage v2_success
```

Server behavior:

1. Resolve `firmware/v2_success`.
2. Reject the request if the package id contains path separators, `..`, or absolute-path syntax.
3. Copy the entire package directory to `data/staging/v2_success`.
4. Read `data/staging/v2_success/manifest.json`.
5. Record `staged_package` in `data/state.json`.
6. Append `package_staged` and `manifest_loaded` to `events`.

Expected staged layout:

```text
data/staging/v2_success/
  manifest.json
  firmware.bin
```

Verification must always read from `data/staging/<package_id>/firmware.bin`.

## Target State Model

The state should be easy to inspect in a terminal. Use names that match OTA A/B concepts.

Recommended state shape:

```json
{
  "device_model": "demo-board",
  "active_slot": "B",
  "pending_slot": null,
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

Slot status values:

- `empty`: no payload installed in this slot.
- `good`: slot is bootable and accepted.
- `pending`: slot has been written and is the next boot target, but has not been confirmed.
- `failed`: slot failed during simulated boot.

Keep compatibility aliases only if useful for existing tests, for example `pending_upgrade` as an alias of `pending_slot`. New docs and tests should prefer `pending_slot`.

## Target State Transitions

### Reset

Initial state:

```json
{
  "active_slot": "B",
  "pending_slot": null,
  "rollback_slot": null,
  "slots": {
    "A": { "version": null, "status": "empty" },
    "B": { "version": "1.0.0", "status": "good" }
  },
  "last_error": null
}
```

### Stage

Transition:

```text
idle -> staged
```

State requirements:

- `staged_package.package_id` is set.
- `staged_package.path` points to `data/staging/<package_id>`.
- `events` includes `package_staged` and `manifest_loaded`.
- No slot is written during stage.

### Verify

Transition on success:

```text
staged -> verified
```

Transition on checksum failure:

```text
staged -> verification_failed
```

State requirements:

- On success, `staged_package.verified` is `true`.
- On failure, `staged_package.verified` is `false`.
- On failure, inactive slot file must not be created or modified.
- `last_error` must mention whether MD5 or SHA256 failed.

### Install

Transition:

```text
verified -> pending_reboot
```

Server behavior:

1. Select the inactive slot automatically:
   - if `active_slot` is `B`, target `A`;
   - if `active_slot` is `A`, target `B`.
2. Copy `data/staging/<package_id>/firmware.bin` to `data/slots/<inactive_slot>/firmware.bin`.
3. Update target slot metadata from the verified staged payload.
4. Set target slot `status` to `pending`.
5. Set `pending_slot` to target slot.
6. Set `rollback_slot` to the current active slot.
7. Set `bootloader.upgrade_available` to `true`.
8. Set `bootloader.boot_once_slot` to target slot.
9. Append `written_to_A` or `written_to_B`, then `pending_reboot`.

### Reboot Success

Transition:

```text
pending_reboot -> boot_confirmed
```

State requirements:

- `active_slot` becomes `pending_slot`.
- New active slot `status` becomes `good`.
- Previous active slot remains `good`.
- `pending_slot` becomes `null`.
- `rollback_slot` should remain as the previous good slot for observability.
- `bootloader.upgrade_available` becomes `false`.
- `bootloader.boot_once_slot` becomes `null`.
- `events` includes `reboot_started` and `boot_confirmed`.

### Reboot Failure

Transition:

```text
pending_reboot -> rolled_back
```

State requirements:

- `active_slot` becomes `rollback_slot`.
- Failed slot `status` becomes `failed`.
- Previous slot remains `good`.
- `pending_slot` becomes `null`.
- `last_error` should be exactly clear, for example:
  - `boot failed on slot A, rolled back to B`
- `bootloader.upgrade_available` becomes `false`.
- `bootloader.boot_once_slot` becomes `null`.
- `bootloader.boot_count` increments.
- `events` includes `reboot_started`, `boot_failed`, and `rolled_back`.

## API And CLI Target

Keep the existing one-shot upgrade path for demo speed:

```bash
python3 -m ota_ab_sim.client upgrade v2_success
```

Internally this should run:

```text
stage -> verify -> install
```

Add optional step-by-step commands for clearer screen recording:

```bash
python3 -m ota_ab_sim.client firmware
python3 -m ota_ab_sim.client status
python3 -m ota_ab_sim.client stage v2_success
python3 -m ota_ab_sim.client verify
python3 -m ota_ab_sim.client install
python3 -m ota_ab_sim.client reboot --boot-ok
python3 -m ota_ab_sim.client reboot --boot-fail
python3 -m ota_ab_sim.client reset
```

HTTP API target:

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

Response requirements:

- Every mutating endpoint returns `{ "ok": true|false, "state": ... }`.
- Error responses use HTTP 400 for invalid transitions or invalid package ids.
- `status` returns enough fields to prove current version, active slot, pending slot, staged package, slot files, events, and rollback state.

## Test Requirements

Add or update tests to prove the following.

### Package Layout

- `firmware/v2_success/manifest.json` and `firmware/v2_success/firmware.bin` exist in test fixtures.
- `firmware` command lists package ids, versions, compatible model, slot class, size, MD5, and SHA256.

### Staging

- `stage v2_success` creates `data/staging/v2_success/manifest.json`.
- `stage v2_success` creates `data/staging/v2_success/firmware.bin`.
- Client tests still prove the client does not read package or state files directly.

### Verification

- MD5 failure sets `ota_state` to `verification_failed`.
- SHA256 failure sets `ota_state` to `verification_failed`.
- Checksum failure leaves `data/slots/A/firmware.bin` absent or unchanged.
- Verification reads the staged copy, not the repository source file.

### Install

- Successful install writes the inactive slot file.
- Slot file size, MD5, and SHA256 match the staged payload.
- Install from active `B` writes `A`.
- After successful boot into `A`, a second upgrade writes `B`.

### Reboot And Rollback

- Successful reboot marks the new slot `good`.
- Failed reboot marks the attempted slot `failed`.
- Failed reboot keeps or restores the old slot as active and `good`.
- Rollback state persists after reloading `data/state.json`.

### HTTP And CLI

- Start a real HTTP handler in tests and call the CLI through subprocess.
- Keep at least one test for the one-shot `upgrade v2_success`.
- Add one test for the step-by-step `stage -> verify -> install -> reboot`.

## Documentation Updates Required

Update these files after implementation:

- `README.md`
  - Show the new package layout.
  - Explain that `upgrade v2_success` stages the package directory first.
  - Show both one-shot and step-by-step demo commands.
- `ARCHITECTURE.md`
  - Replace the old flat firmware model with package + manifest.
  - Update the data model to include `pending_slot`, slot `status`, `staged_package`, and `bootloader`.
  - Document inactive slot selection.
- `SPEC.md`
  - Keep assignment acceptance criteria.
  - Add evaluator-visible fields for package staging and slot status.
- `TODO.md`
  - Add a new phase for package-directory refactor and step-by-step API.
- `demo_script.md`
  - Record the recommended screen recording flow:
    - reset/status
    - firmware
    - stage
    - verify
    - install
    - reboot success
    - checksum failure
    - reboot failure rollback
- `AI_LOG.md`
  - Add a new turn that records this roadmap and the implementation prompt sent to the coder.

## Acceptance Checklist

The refactor is complete only when all items below are true:

- The client never reads `firmware/`, `data/staging/`, `data/slots/`, or `data/state.json`.
- The server rejects package ids with path traversal.
- Staging copies an entire package directory into `data/staging/<package_id>`.
- Verification reads only the staged manifest and staged payload.
- Checksum failure prevents slot file writes.
- Install writes only the inactive slot.
- Reboot success marks the updated slot `good`.
- Reboot failure marks the attempted slot `failed` and restores the rollback slot as active.
- A second successful upgrade after booting into `A` writes slot `B`.
- `python3 -m unittest discover -s tests -v` passes.
- README and demo script show the updated package-based flow.
