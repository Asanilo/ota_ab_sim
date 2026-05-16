import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


COLORS = {
    "title": "\033[36m",
    "ok": "\033[32m",
    "error": "\033[31m",
    "reset": "\033[0m",
}


def request_json(server, method, path, payload=None):
    url = server.rstrip("/") + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def print_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def color(text, name):
    return f"{COLORS[name]}{text}{COLORS['reset']}"


def dash(value):
    return "-" if value is None else value


def state_from_response(payload):
    return payload.get("state", payload)


def short_path(path):
    if not path:
        return "-"
    marker = "/data/"
    if marker in path:
        return "data/" + path.split(marker, 1)[1]
    return path


def package_from_payload(payload, fallback="-"):
    state = state_from_response(payload)
    staged = state.get("staged_package") or {}
    return staged.get("package_id") or fallback


def format_status(payload):
    state = state_from_response(payload)
    lines = [
        color("Device status", "title"),
        f"  active slot     : {dash(state.get('active_slot'))}",
        f"  current version : {dash(state.get('current_version'))}",
        f"  next target     : {dash(state.get('target_slot'))}",
        f"  ota state       : {dash(state.get('ota_state'))}",
        f"  pending slot    : {dash(state.get('pending_slot'))}",
        f"  rollback slot   : {dash(state.get('rollback_slot'))}",
        "",
        color("Slots", "title"),
    ]
    for slot in ("A", "B"):
        slot_state = state.get("slots", {}).get(slot, {})
        lines.append(
            f"  {slot} : {dash(slot_state.get('status')):<8} version={dash(slot_state.get('version'))}"
        )
    staged = state.get("staged_package")
    if staged:
        lines.extend(
            [
                "",
                color("Staged package", "title"),
                f"  package id : {dash(staged.get('package_id'))}",
                f"  version    : {dash(staged.get('version'))}",
                f"  verified   : {str(bool(staged.get('verified'))).lower()}",
            ]
        )
    return "\n".join(lines)


def format_firmware(payload):
    lines = [color("Available firmware packages", "title")]
    for package in payload.get("firmware", []):
        lines.append(
            "  "
            f"{package.get('package_id', '-'):<16} "
            f"version={dash(package.get('version'))}  "
            f"model={dash(package.get('compatible_model'))}  "
            f"slot={dash(package.get('slot_class'))}"
        )
    return "\n".join(lines)


def format_stage(payload, requested_package):
    state = state_from_response(payload)
    if not payload.get("ok", True):
        return "\n".join(
            [
                color("Stage failed", "error"),
                f"  error : {dash(state.get('last_error'))}",
                f"  state : {dash(state.get('ota_state'))}",
            ]
        )
    staged = state.get("staged_package") or {}
    package_id = staged.get("package_id") or requested_package
    return "\n".join(
        [
            color("Package staged", "ok"),
            f"  package id : {package_id}",
            f"  source     : {'firmware' + '/' + package_id}",
            f"  staging    : {short_path(staged.get('path'))}",
            f"  state      : {dash(state.get('ota_state'))}",
        ]
    )


def format_verify(payload):
    state = state_from_response(payload)
    staged = state.get("staged_package") or {}
    if not payload.get("ok", True):
        return "\n".join(
            [
                color("Verification failed", "error"),
                f"  package id : {dash(staged.get('package_id'))}",
                f"  error      : {dash(state.get('last_error'))}",
                "  slot write : blocked",
            ]
        )
    return "\n".join(
        [
            color("Verification passed", "ok"),
            f"  package id : {dash(staged.get('package_id'))}",
            "  size       : ok",
            "  md5        : ok",
            "  sha256     : ok",
            f"  state      : {dash(state.get('ota_state'))}",
        ]
    )


def format_install(payload):
    state = state_from_response(payload)
    if not payload.get("ok", True):
        return "\n".join(
            [
                color("Install failed", "error"),
                f"  error : {dash(state.get('last_error'))}",
                f"  state : {dash(state.get('ota_state'))}",
            ]
        )
    slot = state.get("pending_slot")
    slot_state = state.get("slots", {}).get(slot, {})
    return "\n".join(
        [
            color("Installed to inactive slot", "ok"),
            f"  slot       : {dash(slot)}",
            f"  version    : {dash(slot_state.get('version'))}",
            f"  file       : {short_path(slot_state.get('file_path'))}",
            f"  state      : {dash(state.get('ota_state'))}",
        ]
    )


def format_upgrade(payload, requested_package, server):
    state = state_from_response(payload)
    if not payload.get("ok", True):
        return "\n".join(
            [
                color("Upgrade failed", "error"),
                f"  package id : {package_from_payload(payload, requested_package)}",
                f"  error      : {dash(state.get('last_error'))}",
                "  slot write : blocked",
                f"  active slot: {dash(state.get('active_slot'))}",
                f"  state      : {dash(state.get('ota_state'))}",
            ]
        )
    slot = state.get("pending_slot")
    slot_state = state.get("slots", {}).get(slot, {})
    return "\n".join(
        [
            color("Upgrade staged, verified, and installed", "ok"),
            f"  package id : {package_from_payload(payload, requested_package)}",
            f"  version    : {dash(slot_state.get('version'))}",
            f"  wrote slot : {dash(slot)}",
            f"  active slot: {dash(state.get('active_slot'))}",
            "  next step  : reboot",
            "",
            "Run:",
            f"  python3 -m ota_ab_sim.client --server {server} reboot --boot-ok",
            f"  python3 -m ota_ab_sim.client --server {server} reboot --boot-fail",
        ]
    )


def format_reboot(payload, boot_failed_requested):
    state = state_from_response(payload)
    if boot_failed_requested:
        failed_slot = "-"
        for slot, slot_state in state.get("slots", {}).items():
            if slot_state.get("status") == "failed":
                failed_slot = slot
                break
        return "\n".join(
            [
                color("Boot failed, rolled back", "error"),
                f"  failed slot   : {dash(failed_slot)}",
                f"  active slot   : {dash(state.get('active_slot'))}",
                f"  rollback slot : {dash(state.get('rollback_slot'))}",
                f"  reason        : {dash(state.get('rollback_reason'))}",
            ]
        )
    return "\n".join(
        [
            color("Boot confirmed", "ok"),
            f"  active slot     : {dash(state.get('active_slot'))}",
            f"  current version : {dash(state.get('current_version'))}",
            f"  slot {state.get('active_slot')}          : {dash(state.get('slots', {}).get(state.get('active_slot'), {}).get('status'))}",
            f"  next target     : {dash(state.get('target_slot'))}",
        ]
    )


def format_reset(payload):
    state = state_from_response(payload)
    return "\n".join(
        [
            color("Simulator reset", "ok"),
            f"  active slot     : {dash(state.get('active_slot'))}",
            f"  current version : {dash(state.get('current_version'))}",
            f"  next target     : {dash(state.get('target_slot'))}",
            f"  ota state       : {dash(state.get('ota_state'))}",
        ]
    )


def format_payload(args, payload):
    if args.command == "status":
        return format_status(payload)
    if args.command == "firmware":
        return format_firmware(payload)
    if args.command == "reset":
        return format_reset(payload)
    if args.command == "stage":
        return format_stage(payload, args.package)
    if args.command == "verify":
        return format_verify(payload)
    if args.command == "install":
        return format_install(payload)
    if args.command == "upgrade":
        return format_upgrade(payload, args.package, args.server)
    if args.command == "reboot":
        return format_reboot(payload, bool(args.boot_fail))
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="OTA A/B simulator client")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--json", action="store_true", help="print full JSON response")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("firmware")
    subparsers.add_parser("reset")

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("package")

    subparsers.add_parser("verify")
    subparsers.add_parser("install")

    upgrade_parser = subparsers.add_parser("upgrade")
    upgrade_parser.add_argument("package")

    reboot_parser = subparsers.add_parser("reboot")
    boot_group = reboot_parser.add_mutually_exclusive_group(required=True)
    boot_group.add_argument("--boot-ok", action="store_true")
    boot_group.add_argument("--boot-fail", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "status":
        status, payload = request_json(args.server, "GET", "/status")
    elif args.command == "firmware":
        status, payload = request_json(args.server, "GET", "/firmware")
    elif args.command == "reset":
        status, payload = request_json(args.server, "POST", "/reset", {})
    elif args.command == "stage":
        status, payload = request_json(args.server, "POST", "/stage", {"package": args.package})
    elif args.command == "verify":
        status, payload = request_json(args.server, "POST", "/verify", {})
    elif args.command == "install":
        status, payload = request_json(args.server, "POST", "/install", {})
    elif args.command == "upgrade":
        status, payload = request_json(args.server, "POST", "/upgrade", {"package": args.package})
    elif args.command == "reboot":
        status, payload = request_json(
            args.server,
            "POST",
            "/reboot",
            {"simulate_boot_failure": bool(args.boot_fail)},
        )
    else:
        parser.error("unknown command")

    if args.json:
        print_json(payload)
    else:
        print(format_payload(args, payload))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
