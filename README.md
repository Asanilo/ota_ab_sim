# OTA A/B Simulator

Small CLI plus HTTP server that simulates an OTA A/B partition upgrade flow.

This project simulates the OTA control plane and A/B state machine. It does not implement a real bootloader or flash driver. A/B slots, package staging, checksum verification, boot result, and rollback are simulated with filesystem files and persistent JSON state.

The initial active slot is `B`; the first inactive upgrade slot is `A`.

## Run The Server

```bash
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

By default, the CLI prints concise human-readable output with ANSI color prompts. Use `--json` for the full evaluator-visible server response:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 --json status
```

## Firmware Packages

Firmware packages live under `firmware/<package_id>/`:

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

Each `manifest.json` describes `package_id`, `version`, `compatible_model`, `slot_class`, and payload `filename`, `size`, `md5`, and `sha256`.

List packages through the server:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 firmware
```

## One-Shot Demo

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

`upgrade v2_success` internally runs:

```text
stage -> read staged manifest -> verify staged firmware.bin -> write inactive slot -> pending boot
```

Expected highlights:

- `data/staging/v2_success/manifest.json` and `firmware.bin` are created.
- Verification reads the staged manifest and staged `firmware.bin`.
- Slot `A` is written at `data/slots/A/firmware.bin`.
- `pending_slot` and compatibility alias `pending_upgrade` are `A`.
- Events include `package_staged`, `manifest_loaded`, `verified`, `written_to_A`, and `pending_reboot`.
- After reboot success, `active_slot` is `A`, slot `A.status` is `good`, and the next inactive target is `B`.
- Use `--json status` any time you need the full state fields.

## Step-By-Step Demo

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 firmware
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 stage v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 verify
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 install
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
```

## Failure Demos

Checksum failure:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_bad_md5
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- `ota_state` is `verification_failed`.
- `last_error` mentions `MD5`.
- `data/slots/A/firmware.bin` is absent or unchanged.

Boot failure rollback:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-fail
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 status
```

Expected highlights:

- `active_slot` is restored to `B`.
- Attempted slot `A.status` is `failed`.
- `pending_slot` is `null`.
- `rollback_reason` is `boot_failed`.
- Events include `reboot_started`, `boot_failed`, and `rolled_back`.

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

## Tests

This project uses standard-library `unittest`.

```bash
python3 -m unittest discover -s tests -v
```

The suite includes package staging, staged-file verification, checksum failures, inactive slot writes, reboot rollback, path traversal rejection, static client/server separation, and HTTP/CLI subprocess tests.
