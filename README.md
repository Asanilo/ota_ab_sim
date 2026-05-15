# OTA A/B Simulator

Small CLI plus HTTP server that simulates an OTA A/B partition upgrade flow.

The initial active slot is `B`; the upgrade target slot is `A`.

## Run The Server

```bash
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8000
```

In another terminal, use the client:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

## Deterministic Demo Commands

### 1. Status Check

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- `active_slot` is `B`
- `current_version` is `1.0.0`
- `slot_versions` shows `A: null` and `B: 1.0.0`
- `target_slot` is `A`
- `pending_upgrade` is `null`

### 2. Successful Upgrade From B To A

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- Upgrade copies firmware from `firmware_repo/` to `data/staging/`.
- MD5 and SHA256 are calculated from actual staged file contents.
- Slot `A` is written only after both checks pass.
- Before reboot, `active_slot` remains `B` and `pending_upgrade` is `A`.
- After successful reboot, `active_slot` is `A` and `current_version` is `2.0.0`.

### 3. Checksum Failure

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_bad_checksum.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- `ota_state` is `verification_failed`
- `last_error` mentions `MD5`
- `slots.A.version` remains `null`
- `pending_upgrade` remains `null`

To show SHA256 failure specifically:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_bad_sha256.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- `ota_state` is `verification_failed`
- `last_error` mentions `SHA256`
- `slots.A.version` remains `null`
- `pending_upgrade` remains `null`

### 4. Boot Failure And Rollback To B

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-fail
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- Slot `A` was written and marked pending before reboot.
- Boot failure is simulated during `POST /reboot`.
- `active_slot` rolls back to `B`.
- `pending_upgrade` is cleared.
- `ota_state` is `rolled_back`.

## HTTP API

```bash
curl -s http://127.0.0.1:8000/status
curl -s -X POST http://127.0.0.1:8000/upgrade -H 'Content-Type: application/json' -d '{"firmware":"firmware_v2.bin"}'
curl -s -X POST http://127.0.0.1:8000/reboot -H 'Content-Type: application/json' -d '{"simulate_boot_failure":false}'
curl -s -X POST http://127.0.0.1:8000/reset -H 'Content-Type: application/json' -d '{}'
```

## Tests

This project uses standard-library `unittest`.

```bash
python3 -m unittest discover -s tests -v
```

The suite includes service-level persistence tests, a static client/server separation test, and an HTTP/CLI test that starts a real local server.
