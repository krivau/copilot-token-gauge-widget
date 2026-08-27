#!/usr/bin/env python3
"""
Fetch GitHub Copilot AI Credits usage for the current month and print JSON.

The GitHub personal access token is read from the macOS Keychain so that it
is never stored in source code.  Add it once with:

    security add-generic-password \
      -a "$USER" \
      -s "github-copilot-widget" \
      -w "github_pat_YOUR_TOKEN"

Output (stdout):
    {
      "used": 823.4,
      "limit": 1500,
      "percentage": 54.9,
      "remaining": 676.6
    }
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — override via config.json that lives next to this script
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "github_user": "",
    "ai_credit_limit": 1500,
    "api_version": "2026-03-10",
    "keychain_service": "github-copilot-widget",
}


def load_config() -> dict:
    """Load config.json from the same directory as this script (if present)."""
    config_path = Path(__file__).parent / "config.json"
    config = dict(_DEFAULT_CONFIG)
    if config_path.exists():
        try:
            with config_path.open() as fh:
                overrides = json.load(fh)
            config.update(overrides)
        except (json.JSONDecodeError, OSError):
            pass
    return config


# ---------------------------------------------------------------------------
# Token retrieval
# ---------------------------------------------------------------------------


def get_token(keychain_service: str) -> str:
    """Read the GitHub PAT from the macOS Keychain."""
    username = subprocess.check_output(["whoami"], text=True).strip()
    token = subprocess.check_output(
        [
            "security",
            "find-generic-password",
            "-a", username,
            "-s", keychain_service,
            "-w",
        ],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    if not token:
        raise RuntimeError(
            f"No token found in Keychain for service '{keychain_service}'. "
            "Run: security add-generic-password "
            f"-a \"$USER\" -s \"{keychain_service}\" -w \"YOUR_PAT\""
        )
    return token


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------


def get_usage(github_user: str, token: str, api_version: str) -> dict:
    """Return the raw JSON response from the GitHub billing API."""
    now = datetime.now()
    url = (
        f"https://api.github.com/users/{github_user}"
        f"/settings/billing/ai_credit/usage"
        f"?year={now.year}&month={now.month}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": api_version,
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"GitHub API returned HTTP {exc.code}: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def compute_stats(data: dict, limit: float) -> dict:
    """Summarise raw API data into the four numbers the widget needs."""
    used = sum(
        float(item.get("grossQuantity", 0))
        for item in data.get("usageItems", [])
    )
    percentage = min(used / limit * 100, 100) if limit > 0 else 0.0
    return {
        "used": round(used, 1),
        "limit": limit,
        "percentage": round(percentage, 1),
        "remaining": round(max(limit - used, 0), 1),
    }


def main() -> None:
    config = load_config()

    github_user = config.get("github_user", "").strip()
    if not github_user:
        # Print to stdout so the Übersicht widget can display the message.
        print(json.dumps({"error": "github_user is not set in config.json"}))
        sys.exit(1)

    limit = float(config.get("ai_credit_limit", _DEFAULT_CONFIG["ai_credit_limit"]))
    api_version = config.get("api_version", _DEFAULT_CONFIG["api_version"])
    keychain_service = config.get(
        "keychain_service", _DEFAULT_CONFIG["keychain_service"]
    )

    try:
        token = get_token(keychain_service)
        data = get_usage(github_user, token, api_version)
        stats = compute_stats(data, limit)
        print(json.dumps(stats))
    except Exception as exc:  # noqa: BLE001
        # Print to stdout so the Übersicht widget can display the error message.
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
