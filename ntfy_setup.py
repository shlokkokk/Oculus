#!/usr/bin/env python3
"""Interactive ntfy setup wizard for Oculus.

This helper is intentionally CLI-only. It skips prompts when stdin/stdout are
not interactive so the web backend can import or ignore it safely.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

DEFAULT_NTFY = {
    "enabled": True,
    "url": "",
    "server": "https://ntfy.sh",
    "topic": "",
    "token": "",
    "username": "",
    "password": "",
    "priority": "default",
    "tags": "rocket",
    "send_scan_start": True,
    "send_scan_complete": True,
    "send_module_start": False,
    "send_module_complete": True,
    "send_findings": True,
    "send_errors": True,
    "send_skips": False,
    "timeout": 8,
    "dedupe_window": 20,
}

EXAMPLE_NTFY = {
    "server": "https://ntfy.sh",
    "topic": "oculus",
    "url": "https://ntfy.sh/oculus",
    "priority": "default",
    "tags": "rocket",
}


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _config_candidates() -> list[Path]:
    return [
        Path.home() / ".config" / "oculus" / "config.yaml",
        Path.home() / ".config" / "oculus" / "config.yml",
        Path("config.yaml"),
    ]


def _load_config_file() -> tuple[Path, dict[str, Any]]:
    for path in _config_candidates():
        if path.exists():
            if YAML_AVAILABLE:
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh) or {}
                    if isinstance(data, dict):
                        return path, data
                except Exception:
                    pass
            return path, {}
    default_path = _config_candidates()[0]
    default_path.parent.mkdir(parents=True, exist_ok=True)
    return default_path, {}


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def _ask_bool(prompt: str, default: bool) -> bool:
    default_hint = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({default_hint}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true", "on"}


def _ask_int(prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            parsed = int(value)
            if parsed < minimum:
                raise ValueError
            return parsed
        except ValueError:
            print(f"Please enter an integer >= {minimum}.")


def _merge_ntfy(existing: dict[str, Any]) -> dict[str, Any]:
    ntfy = dict(DEFAULT_NTFY)
    if isinstance(existing.get("ntfy"), dict):
        ntfy.update(existing["ntfy"])

    print("\nOculus ntfy setup")
    print("This writes the ntfy block into your Oculus config and is safe to skip in non-interactive runs.")
    print("Normal setup is just one URL like https://ntfy.sh/oculus.\n")

    ntfy["enabled"] = _ask_bool("Enable ntfy notifications", bool(ntfy.get("enabled", True)))
    if not ntfy["enabled"]:
        return ntfy

    ntfy["url"] = _ask("ntfy URL (example: https://ntfy.sh/oculus)", str(ntfy.get("url", "")))

    advanced = _ask_bool("Configure advanced ntfy options too", False)
    if advanced:
        print("\nAdvanced ntfy options (optional):")
        print("  - Use server + topic instead of a full URL if you prefer")
        print("  - Add token or username/password only for private ntfy servers")
        print("  - priority and tags just control how the notification looks")
        print("  - leave any field blank to keep the default\n")
        ntfy["server"] = _ask("ntfy server/base URL", str(ntfy.get("server", "https://ntfy.sh")))
        ntfy["topic"] = _ask("ntfy topic", str(ntfy.get("topic", "")))
        ntfy["token"] = _ask("ntfy token / Bearer auth", str(ntfy.get("token", "")))
        ntfy["username"] = _ask("ntfy username for basic auth", str(ntfy.get("username", "")))
        ntfy["password"] = _ask("ntfy password for basic auth", str(ntfy.get("password", "")))
        ntfy["priority"] = _ask("Default ntfy priority", str(ntfy.get("priority", "default")))
        ntfy["tags"] = _ask("Default ntfy tags, comma-separated", str(ntfy.get("tags", "rocket")))
        ntfy["send_scan_start"] = _ask_bool("Notify when a scan starts", bool(ntfy.get("send_scan_start", True)))
        ntfy["send_scan_complete"] = _ask_bool("Notify when a scan completes", bool(ntfy.get("send_scan_complete", True)))
        ntfy["send_module_start"] = _ask_bool("Notify when a module starts", bool(ntfy.get("send_module_start", True)))
        ntfy["send_module_complete"] = _ask_bool("Notify when a module completes", bool(ntfy.get("send_module_complete", True)))
        ntfy["send_findings"] = _ask_bool("Notify when findings update on save", bool(ntfy.get("send_findings", True)))
        ntfy["send_errors"] = _ask_bool("Notify on errors", bool(ntfy.get("send_errors", True)))
        ntfy["send_skips"] = _ask_bool("Notify on skipped steps", bool(ntfy.get("send_skips", True)))
        ntfy["timeout"] = _ask_int("HTTP timeout seconds", int(ntfy.get("timeout", 8)), minimum=1)
        ntfy["dedupe_window"] = _ask_int("Dedupe window seconds", int(ntfy.get("dedupe_window", 20)), minimum=0)
    else:
        ntfy["server"] = "https://ntfy.sh"
        ntfy["topic"] = ""
        ntfy["token"] = ""
        ntfy["username"] = ""
        ntfy["password"] = ""
        ntfy["priority"] = "default"
        ntfy["tags"] = "rocket"
        ntfy["send_scan_start"] = True
        ntfy["send_scan_complete"] = True
        ntfy["send_module_start"] = True
        ntfy["send_module_complete"] = True
        ntfy["send_findings"] = True
        ntfy["send_errors"] = True
        ntfy["send_skips"] = True
        ntfy["timeout"] = 8
        ntfy["dedupe_window"] = 20
    return ntfy


def _write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not YAML_AVAILABLE:
        raise RuntimeError("pyyaml is not installed")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False)


def setup_ntfy(interactive: bool | None = None) -> bool:
    """Run the ntfy wizard and write the config if possible.

    Returns True when the config was updated, False when skipped or unavailable.
    """
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print("[ntfy] Non-interactive environment detected; skipping prompt.")
        return False

    config_path, config = _load_config_file()
    updated = dict(config)
    updated["ntfy"] = _merge_ntfy(config)

    try:
        _write_config(config_path, updated)
        print(f"\n[ntfy] Saved ntfy settings to {config_path}")
        return True
    except Exception as e:
        print(f"\n[ntfy] Could not write config automatically: {e}")
        print("[ntfy] Paste this block into your Oculus config under ntfy:\n")
        if YAML_AVAILABLE:
            print(yaml.safe_dump({"ntfy": updated["ntfy"]}, sort_keys=False).rstrip())
        else:
            for key, value in updated["ntfy"].items():
                print(f"  {key}: {value}")
        return False


def main() -> int:
    try:
        return 0 if setup_ntfy() else 1
    except KeyboardInterrupt:
        print("\n\n[ntfy] Setup cancelled by user.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
