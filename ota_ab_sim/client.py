import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="OTA A/B simulator client")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
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

    print_json(payload)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
