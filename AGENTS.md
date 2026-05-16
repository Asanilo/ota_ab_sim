# AGENTS.md

Project rules for AI-assisted development on the OTA A/B simulator.

## Assignment Goal

Build a CLI or simple Web client plus a real HTTP server to simulate an OTA A/B partition upgrade flow.

The required flow is:

1. Check current version.
2. Stage firmware by copying it from a local dummy firmware repository.
3. Verify MD5 and SHA256.
4. Write the verified firmware to slot A.
5. Reboot and switch the active slot.
6. If the upgraded boot fails, automatically roll back to slot B.

Initial state must be:

- Active slot: `B`
- Upgrade target slot: `A`

## Hard Boundaries

- Use C/S architecture.
- The server must be a real running process exposing HTTP APIs.
- The client must call the server over HTTP.
- The client must not directly read, write, or mutate server state files.
- The client must not copy firmware into staging directly.
- The server owns all persistent state, staging, checksum verification, slot writes, reboot simulation, and rollback.
- Do not add a database, Docker, authentication, frontend framework, or extra infrastructure unless explicitly required.

## Implementation Bias

- Prefer a small Python implementation using only the standard library where practical.
- Keep modules small and obvious.
- Make all assignment requirements verifiable through CLI commands, HTTP responses, tests, or status fields.
- Use persistent JSON files for state so rollback can be verified after process restart.
- Treat "download" as staging/copying from a local folder such as `firmware_repo/` into a server-owned staging folder.

## Required Documentation

Before implementation, keep these documents current:

- `SPEC.md`: acceptance criteria and evaluator-visible behavior.
- `ARCHITECTURE.md`: C/S boundaries, APIs, data model, and state machine.
- `docs/TODO.md`: implementation tasks.
- `docs/AI_LOG.md`: AI-assisted development log.
- `demo_script.md`: screen recording or demo flow.

## Testing Rules

- Test checksum success and failure.
- Test that checksum failure prevents writing to slot A.
- Test that boot failure happens during reboot after slot A is written and pending.
- Test that rollback updates persistent state to active slot `B`.
- Test that the client uses HTTP APIs and does not mutate state files directly.

## AI-Assisted Development Rules

- Record meaningful AI prompts, decisions, and generated artifacts in `docs/AI_LOG.md`.
- Keep AI usage honest and specific.
- Do not claim a requirement is complete until there is a command, test, or status field proving it.
