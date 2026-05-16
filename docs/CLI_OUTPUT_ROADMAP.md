# CLI Output Roadmap

This document is the implementation prompt for improving the CLI presentation while preserving the existing HTTP APIs and testability.

## Current Problem

The CLI currently prints the full server JSON response for every command. This is useful for evaluator-visible state fields, but it is noisy for a screen recording and does not resemble a normal OTA command-line tool.

Keep full JSON available, but make the default CLI output concise and human-readable.

## Existing One-Shot Upgrade

The project already has a one-shot upgrade command:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
```

It calls `POST /upgrade`, and the server internally runs:

```text
stage -> verify -> install
```

The CLI should make this obvious in the default output.

## Required Behavior

### Add `--json`

Add a global CLI flag:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 --json status
```

Rules:

- Default output is human-readable text.
- `--json` prints the current full JSON response exactly like the current CLI.
- Existing tests that parse JSON should pass `--json`.
- The client must still only call HTTP APIs and must not read local server-owned files.

## Default Output Requirements

Use plain ASCII text. Do not use emoji or terminal color libraries.

### `status`

Example:

```text
Device status
  active slot     : B
  current version : 1.0.0
  next target     : A
  ota state       : idle
  pending slot    : -
  rollback slot   : -

Slots
  A : empty    version=-
  B : good     version=1.0.0
```

If a package is staged, include:

```text
Staged package
  package id : v2_success
  version    : 2.0.0
  verified   : false
```

### `firmware`

Example:

```text
Available firmware packages
  v2_success      version=2.0.0  model=demo-board  slot=rootfs
  v2_bad_md5      version=9.9.9  model=demo-board  slot=rootfs
  v2_bad_sha256   version=9.9.8  model=demo-board  slot=rootfs
```

### `stage <package>`

Success:

```text
Package staged
  package id : v2_success
  source     : firmware/v2_success
  staging    : data/staging/v2_success
  state      : staged
```

Failure:

```text
Stage failed
  error : Invalid package id: ../v2_success
  state : invalid_package
```

### `verify`

Success:

```text
Verification passed
  package id : v2_success
  size       : ok
  md5        : ok
  sha256     : ok
  state      : verified
```

Failure:

```text
Verification failed
  package id : v2_bad_md5
  error      : MD5 mismatch
  slot write : blocked
```

### `install`

Success:

```text
Installed to inactive slot
  slot       : A
  version    : 2.0.0
  file       : data/slots/A/firmware.bin
  state      : pending_reboot
```

Failure:

```text
Install failed
  error : No verified package to install
  state : idle
```

### `upgrade <package>`

Success:

```text
Upgrade staged, verified, and installed
  package id : v2_success
  version    : 2.0.0
  wrote slot : A
  active slot: B
  next step  : reboot

Run:
  python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-ok
  python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 reboot --boot-fail
```

Checksum failure:

```text
Upgrade failed
  package id : v2_bad_md5
  error      : MD5 mismatch
  slot write : blocked
  active slot: B
```

Invalid package id:

```text
Upgrade failed
  package id : ../v2_success
  error      : Invalid package id: ../v2_success
  state      : invalid_package
```

### `reboot --boot-ok`

Success:

```text
Boot confirmed
  active slot     : A
  current version : 2.0.0
  slot A          : good
  next target     : B
```

### `reboot --boot-fail`

Failure rollback:

```text
Boot failed, rolled back
  failed slot   : A
  active slot   : B
  rollback slot : B
  reason        : boot_failed
```

### `reset`

Success:

```text
Simulator reset
  active slot     : B
  current version : 1.0.0
  next target     : A
  ota state       : idle
```

## Implementation Guidance

Recommended structure in `ota_ab_sim/client.py`:

- Keep `request_json()` unchanged.
- Keep `print_json()` for `--json`.
- Add small formatter functions:
  - `format_status(payload)`
  - `format_firmware(payload)`
  - `format_stage(payload)`
  - `format_verify(payload)`
  - `format_install(payload)`
  - `format_upgrade(payload)`
  - `format_reboot(payload, boot_failed_requested)`
  - `format_reset(payload)`
- Add helper functions:
  - `dash(value)` returns `-` for `None`.
  - `state_from_response(payload)` returns `payload["state"]` for mutating commands or `payload` for `status`.

Avoid overengineering. Keep formatting simple and deterministic.

## Testing Requirements

Update tests so both output modes are covered.

### JSON Mode

- Existing HTTP/CLI subprocess tests should call `--json` before the command and continue parsing JSON.
- Example:

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 --json status
```

### Human Output Mode

Add focused tests that do not parse JSON:

- `status` default output contains:
  - `Device status`
  - `active slot`
  - `current version`
- `upgrade v2_success` default output contains:
  - `Upgrade staged, verified, and installed`
  - `wrote slot : A`
  - `next step  : reboot`
- `upgrade v2_bad_md5` default output exits non-zero and contains:
  - `Upgrade failed`
  - `MD5 mismatch`
  - `slot write : blocked`
- `reboot --boot-ok` default output contains:
  - `Boot confirmed`
  - `active slot`
- `reboot --boot-fail` default output contains:
  - `Boot failed, rolled back`
  - `reason        : boot_failed`

## Documentation Updates

After implementation, update:

- `README.md`
  - State that default CLI output is human-readable.
  - State that `--json` is available for evaluator-visible full state.
- `demo_script.md`
  - Use default human-readable output for the recording.
  - Add one `--json status` command to show the full state fields.
- `AI_LOG.md`
  - Record the prompt, implementation decision, and verification output.

## Acceptance Checklist

- One-shot `upgrade v2_success` remains available.
- Human-readable output is the default.
- Full JSON output remains available through `--json`.
- Successful upgrade clearly says that the package was staged, verified, and installed.
- Failed upgrade clearly says why it failed and that slot write was blocked.
- Reboot success and boot failure rollback have clear default messages.
- Existing C/S boundary remains intact.
- `python3 -m unittest discover -s tests -v` passes.
