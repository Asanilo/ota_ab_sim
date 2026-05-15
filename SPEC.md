# SPEC.md

# OTA A/B Simulator Specification

## Product Scope

This project is a 24-hour assignment implementation of an OTA A/B partition upgrade simulator.

It will provide:

- A real HTTP server process.
- A CLI client that talks to the server only through HTTP.
- A local dummy firmware repository.
- Persistent server-owned OTA state.
- A demo flow proving upgrade success and rollback behavior.

It will not provide:

- Real network firmware download.
- Real flash partition writes.
- Authentication.
- Database storage.
- Docker packaging.
- Frontend framework.

## Core Acceptance Criteria

### AC1: Current Version Is Queryable

The user can check current OTA state and version through the client.

Expected observable fields:

- `active_slot`
- `active_version`
- `current_version`
- `slot_versions`
- `pending_upgrade`
- `last_error`
- `slots.A.version`
- `slots.B.version`
- `ota_state`

Initial expected state:

- `active_slot` is `B`
- target upgrade slot is `A`

Example verification command:

```bash
python3 -m ota_ab_sim.client status
```

### AC2: Firmware Is Staged From Local Dummy Firmware Folder

The server stages firmware by copying a firmware file from a local server-side folder such as `firmware_repo/` into a server-owned staging folder such as `data/staging/`.

The client may request a firmware name through HTTP, but must not copy files directly. In the minimal implementation, staging is performed inside `POST /upgrade`.

Example verification command:

```bash
python3 -m ota_ab_sim.client upgrade firmware_v2.bin
```

Expected result:

- Server response shows staged firmware metadata.
- Persistent state records `staged_firmware`.
- The staged file exists in the server-owned staging area.

### AC3: MD5 And SHA256 Are Verified

The server verifies both MD5 and SHA256 during `POST /upgrade` before allowing a slot write.

Expected behavior:

- If MD5 mismatches, verification fails.
- If SHA256 mismatches, verification fails.
- If either checksum fails, the server must reject the upgrade and prevent writing to slot A.
- Checksum failure must affect control flow, not only print a warning.

Example failure verification command:

```bash
python3 -m ota_ab_sim.client upgrade firmware_bad_checksum.bin
```

Expected status field after success:

- `ota_state` is `pending_reboot`
- `staged_firmware.verified` is `true`

Expected status field after failure:

- `ota_state` is `verification_failed`
- `staged_firmware.verified` is `false`
- slot A remains unchanged

### AC4: Verified Firmware Can Be Written To Slot A

The server writes only verified staged firmware to target slot `A` as part of `POST /upgrade`.

Expected behavior:

- Slot A is not written unless both checksums match.
- Successful write updates slot A metadata.
- Slot A is marked `pending`.
- Active slot remains `B` until reboot succeeds.

Example verification command:

```bash
python3 -m ota_ab_sim.client upgrade firmware_v2.bin
python3 -m ota_ab_sim.client status
```

Expected status fields:

- `active_slot` is still `B`
- `target_slot` is `A`
- `pending_upgrade` is `A`
- `slots.A.boot_status` is `pending`
- `ota_state` is `pending_reboot`

### AC5: Reboot Switches Active Slot On Successful Boot

During reboot, the server simulates booting pending slot `A`.

Expected success behavior:

- Active slot changes from `B` to `A`.
- Slot A boot status becomes `confirmed`.
- Rollback slot remains `B`.
- Persistent state records successful upgrade.

Example verification command:

```bash
python3 -m ota_ab_sim.client reboot --boot-ok
```

Expected status fields:

- `active_slot` is `A`
- `active_version` matches the upgraded firmware version
- `ota_state` is `boot_confirmed`

### AC6: Boot Failure Rolls Back To Slot B

Boot failure must be simulated during reboot, after slot A has already been written and marked pending.

Expected failure behavior:

- The server attempts to boot pending slot `A`.
- The simulated boot fails.
- The server automatically rolls back active slot to `B`.
- Rollback is persisted to state storage.
- Slot A records a failed boot status.

Example verification command:

```bash
python3 -m ota_ab_sim.client reboot --boot-fail
```

Expected status fields:

- `active_slot` is `B`
- `rollback_slot` is `B`
- `slots.A.boot_status` is `failed`
- `ota_state` is `rolled_back`

### AC7: Client/Server Separation Is Real

The client must use HTTP APIs for all operations.

Expected proof:

- Server can be started as a separate process.
- Client accepts a base URL such as `--server http://127.0.0.1:8000`.
- Client implementation does not import server state storage modules for mutation.
- Client does not open or write `data/state.json`.

Example commands:

```bash
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8000
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

## Definition Of Done

- All 7 assignment requirements are implemented.
- All acceptance criteria above are demonstrable.
- Tests cover success path, checksum failure, and rollback path.
- Demo script shows initial slot `B`, target slot `A`, upgrade write to `A`, simulated boot failure, and persistent rollback to `B`.
