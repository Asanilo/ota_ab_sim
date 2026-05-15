# OTA A/B Simulator Demo Script

This script is the intended recording flow for the assignment demo.

## 1. Start Server

Terminal 1:

```bash
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8000
```

Say or show:

- The server is a real HTTP process.
- The client will use `http://127.0.0.1:8000`.

## 2. Reset And Check Initial State

Terminal 2:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected output:

- `active_slot: B`
- `current_version: 1.0.0`
- `slot_versions` shows `A: null` and `B: 1.0.0`
- `target_slot: A`
- `pending_upgrade: null`
- `ota_state: idle`

## 3. Successful Upgrade From B To A

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 firmware
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- `POST /upgrade` is the server-side "download" step plus checksum verification and slot A write.
- The server copies from `firmware_repo/` into `data/staging/`.
- MD5 and SHA256 expected and actual values are shown in `staged_firmware`.
- Before reboot, `active_slot` is still `B`, `pending_upgrade` is `A`, and `slots.A.boot_status` is `pending`.
- After successful reboot, `active_slot` is `A` and `current_version` is `2.0.0`.

## 4. Checksum Failure Blocks Slot A Write

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_bad_checksum.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected output:

- `ota_state: verification_failed`
- `last_error` mentions `MD5 mismatch`.
- `staged_firmware.verified: false`
- `slots.A.version: null`
- `pending_upgrade: null`

## 5. Boot Failure Rolls Back To B

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-fail
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- Failure is simulated during reboot.
- Slot A had already been written and marked pending before reboot.
- The server automatically rolls back to slot B.
- Rollback updates persistent state.

Expected output:

- `active_slot: B`
- `current_version: 1.0.0`
- `rollback_slot: B`
- `pending_upgrade: null`
- `slots.A.boot_status: failed`
- `ota_state: rolled_back`

## 6. Prove Rollback Persistence

Stop and restart the server, then run:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected output:

- `active_slot: B`
- `ota_state: rolled_back`

## 7. Show AI-Assisted Development Evidence

```bash
sed -n '1,220p' AI_LOG.md
```

Point out:

- AI was used for planning, implementation support, and verification tracking.
- Human decisions and verification commands are recorded.
