# OTA A/B Simulator Demo Script

This is the recommended recording flow for the package-based OTA simulator.

## 1. Start Server

Terminal 1:

```bash
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8000
```

Show that this is a real HTTP server process.

Optional architecture proof in another terminal:

```bash
curl -s http://127.0.0.1:8000/status
```

Point out:

- The server responds over HTTP.
- The CLI will use `--server http://127.0.0.1:8000`.
- State, firmware packages, staging, slot writes, reboot, and rollback are server-owned.

Optional static boundary check:

```bash
rg -n "OtaService|state\.json|firmware/|data/staging|data/slots|copytree|copyfile|shutil" ota_ab_sim/client.py
```

Expected output:

- No matches.
- This shows the client does not import server state logic or access firmware/staging/slot files directly.

## 2. Reset And Inspect Initial State

Terminal 2:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- Default CLI output is human-readable and color-highlighted for recording.
- `active_slot: B`
- `current_version: 1.0.0`
- `target_slot: A`
- `pending_slot: null`
- `slots.B.status: good`
- `slots.A.status: empty`

Show full JSON once for evaluator-visible state fields:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 --json status
```

## 3. Show Firmware Packages

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 firmware
```

Point out:

- Packages live under `firmware/<package_id>/`.
- Each package contains `manifest.json` and `firmware.bin`.
- Manifest shows compatible model, slot class, size, MD5, and SHA256.

## 4. Step-By-Step Successful Upgrade

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 stage v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 verify
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 install
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- Stage creates `data/staging/v2_success/manifest.json`.
- Stage creates `data/staging/v2_success/firmware.bin`.
- Verify reads the staged manifest and staged payload.
- Install writes only inactive slot `A`.
- Slot file exists at `data/slots/A/firmware.bin`.
- Events include `package_staged`, `manifest_loaded`, `verified`, `written_to_A`, `pending_reboot`.

Then reboot:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- `active_slot: A`
- `slots.A.status: good`
- `pending_slot: null`
- next `target_slot: B`

## 5. One-Shot Upgrade Demo

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- `POST /upgrade` internally runs stage, verify, and install.
- It keeps the demo short while still exposing events.

## 6. Checksum Failure Blocks Slot Write

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_bad_md5
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- `ota_state: verification_failed`
- `last_error` mentions `MD5 mismatch`
- `staged_package.verified: false`
- `slots.A.status: empty`
- `data/slots/A/firmware.bin` is absent or unchanged

## 7. Boot Failure Rolls Back To B

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-fail
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Point out:

- Boot failure is simulated during reboot.
- Attempted slot `A.status` becomes `failed`.
- `active_slot` remains or returns to `B`.
- `rollback_reason: boot_failed`
- Events include `reboot_started`, `boot_failed`, `rolled_back`.

## 8. Prove Rollback Persistence

Stop and restart the server, then run:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected output still shows:

- `active_slot: B`
- `ota_state: rolled_back`
- `slots.A.status: failed`

## 9. Show AI-Assisted Development Evidence

```bash
sed -n '1,260p' docs/AI_LOG.md
```

Point out:

- Prompts and implementation turns are recorded.
- Verification commands and results are recorded.

## 10. Show Verification Evidence

```bash
python3 -m unittest discover -s tests -v
git status --short --ignored
```

Point out:

- Tests cover package staging, staged-file verification, checksum failure, inactive slot writes, rollback, path traversal rejection, and HTTP/CLI separation.
- `data/` is runtime state and is not committed.
- Only ignored Python cache directories should appear in git status.
