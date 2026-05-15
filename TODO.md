# TODO.md

# OTA A/B Simulator Implementation TODO

## Phase 0: Project Setup

- [x] Create Python package layout for `ota_ab_sim`.
- [x] Add a minimal standard-library `unittest` setup.
- [x] Create `firmware_repo/` with dummy firmware and manifest files.
- [x] Create initial persistent state under `data/state.json` through server initialization, not by client mutation.

## Phase 1: State And Firmware Core

- [x] Implement state loading and saving.
- [x] Implement initial state with active slot `B` and target slot `A`.
- [x] Implement firmware listing from `firmware_repo/`.
- [x] Implement local staging copy from `firmware_repo/` to `data/staging/`.
- [x] Implement MD5 and SHA256 calculation.
- [x] Implement manifest-based checksum verification.

## Phase 2: OTA Flow Logic

- [x] Implement `POST /upgrade`: stage, verify, write slot A, and mark pending.
- [x] Implement verification failure transition: `staged -> verification_failed`.
- [x] Ensure verification failure prevents slot A writes.
- [x] Ensure active slot remains `B` after writing slot A.
- [x] Implement reboot success: active slot switches to `A`.
- [x] Implement reboot failure: slot A fails and active slot rolls back to `B`.
- [x] Persist rollback state to `data/state.json`.

## Phase 3: HTTP Server

- [x] Implement `GET /status`.
- [x] Implement `GET /firmware`.
- [x] Implement `POST /upgrade`.
- [x] Implement `POST /reboot`.
- [x] Implement `POST /reset` for demo and tests.
- [x] Return clear JSON errors for invalid transitions.

## Phase 4: CLI Client

- [x] Implement `status` command through `GET /status`.
- [x] Implement `firmware` command through `GET /firmware`.
- [x] Implement `upgrade <name>` command through `POST /upgrade`.
- [x] Implement `reboot --boot-ok` command through `POST /reboot`.
- [x] Implement `reboot --boot-fail` command through `POST /reboot`.
- [x] Implement `reset` command through `POST /reset`.
- [x] Ensure client never opens or writes `data/state.json`.

## Phase 5: Tests

- [x] Test initial active slot is `B`.
- [x] Test MD5 and SHA256 success through successful upgrade.
- [x] Test MD5 failure rejects verification.
- [x] Test SHA256 failure rejects verification.
- [x] Test checksum failure prevents writing to slot A.
- [x] Test write to slot A marks it pending while active slot remains `B`.
- [x] Test reboot success switches active slot to `A`.
- [x] Test reboot failure rolls back active slot to `B`.
- [x] Test rollback state remains after reloading state from disk.
- [x] Test CLI talks to a real HTTP server.
- [x] Test client source does not import or mutate server state files.

## Phase 6: Demo And Evidence

- [x] Update `AI_LOG.md` with prompts, decisions, and verification evidence.
- [x] Add deterministic demo commands to `README.md`.
- [x] Run the README demo script from a clean reset state.
- [x] Capture outputs showing active slot `B`, target slot `A`, pending slot `A`, and rollback to `B`.
- [x] Run all tests.
- [x] Confirm every assignment requirement maps to a command, test, or status field.
