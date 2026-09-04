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

import calendar
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
    "usage_source": "api",
    "copilot_page_url": "https://github.com/settings/copilot",
    "auto_login": False,
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

# Pace is considered "on track" when actual usage is within this fraction
# of the expected usage-to-date (e.g. 0.05 == +/-5%).
PACE_TOLERANCE = 0.05


def add_pace_stats(stats: dict, now: datetime | None = None) -> dict:
    """Add day-of-month pace information (are we on track to hit the limit)."""
    now = now or datetime.now()
    used = float(stats.get("used", 0))
    limit = float(stats.get("limit", 0))

    day_of_month = now.day
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    daily_budget = limit / days_in_month if days_in_month else 0.0
    expected_used_by_now = daily_budget * day_of_month
    actual_daily_average = used / day_of_month if day_of_month else 0.0
    projected_total = actual_daily_average * days_in_month

    if expected_used_by_now > 0:
        pace_ratio = used / expected_used_by_now
    else:
        pace_ratio = 0.0

    if pace_ratio > 1 + PACE_TOLERANCE:
        status = "over"
        message = (
            f"Pacing above budget — projected {round(projected_total, 1)} "
            f"of {limit} by month end"
        )
    elif pace_ratio < 1 - PACE_TOLERANCE:
        status = "under"
        message = (
            f"Pacing below budget — projected {round(projected_total, 1)} "
            f"of {limit} by month end"
        )
    else:
        status = "on_track"
        message = f"On track — projected {round(projected_total, 1)} of {limit}"

    stats["pace"] = {
        "status": status,
        "message": message,
        "day_of_month": day_of_month,
        "days_in_month": days_in_month,
        "daily_budget": round(daily_budget, 2),
        "actual_daily_average": round(actual_daily_average, 2),
        "expected_used_by_now": round(expected_used_by_now, 1),
        "projected_total": round(projected_total, 1),
    }
    return stats



def compute_page_stats(page_text: str, configured_limit: float) -> dict:
    """Extract visible Copilot usage from an authenticated GitHub page."""
    number = r"([\d,]+(?:\.\d+)?)"
    usage_pattern = re.compile(
        rf"{number}\s*(?:/|of)\s*{number}\s+"
        r"(?:(?:premium|AI)\s+)?(?:requests|credits)",
        re.IGNORECASE,
    )
    remaining_patterns = (
        re.compile(
            rf"{number}\s+(?:premium\s+)?(?:requests|credits)\s+remaining",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:premium\s+)?(?:requests|credits)\s+remaining\s*[:\-]?\s*{number}",
            re.IGNORECASE,
        ),
    )

    match = usage_pattern.search(page_text)
    if match:
        used, limit = (float(value.replace(",", "")) for value in match.groups())
        return compute_stats({"usageItems": [{"grossQuantity": used}]}, limit)

    for pattern in remaining_patterns:
        match = pattern.search(page_text)
        if match:
            remaining = float(match.group(1).replace(",", ""))
            used = max(configured_limit - remaining, 0)
            return compute_stats({"usageItems": [{"grossQuantity": used}]}, configured_limit)

    raise RuntimeError(
        "Could not find Copilot usage on the page. The GitHub page may have changed."
    )


_GITHUB_AUTH_PATH_MARKERS = (
    "/login",
    "/session",
    "/sessions",
    "/two_factor",
    "/two-factor",
    "/account_recovery",
    "/webauthn",
    "/sudo",
)


def _is_github_auth_url(url: str) -> bool:
    """Return True if url is part of the GitHub sign-in flow (login, 2FA, etc.)."""
    path = urllib.parse.urlparse(url).path
    return any(marker in path for marker in _GITHUB_AUTH_PATH_MARKERS)


def launch_login() -> None:
    """Open a visible persistent browser for the user to complete login."""
    subprocess.Popen(
        [sys.executable, str(Path(__file__)), "--login"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_browser_usage(
    page_url: str,
    limit: float,
    show_browser: bool = False,
    auto_login: bool = False,
) -> dict:
    """Read visible Copilot usage from an authenticated persistent browser profile."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Browser mode requires Playwright. Install it with: "
            "python3 -m pip install playwright && python3 -m playwright install chromium"
        ) from exc

    profile_dir = Path(__file__).parent / ".copilot-browser-profile"
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=not show_browser,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(page_url, wait_until="domcontentloaded")
            if _is_github_auth_url(page.url):
                if show_browser:
                    deadline = time.monotonic() + 600
                    while _is_github_auth_url(page.url) and time.monotonic() < deadline:
                        page.wait_for_timeout(1000)
                    if _is_github_auth_url(page.url):
                        raise RuntimeError("Timed out waiting for GitHub login")
                    page.goto(page_url, wait_until="domcontentloaded")
                elif auto_login:
                    launch_login()
                    raise RuntimeError(
                        "GitHub login required. A browser was opened for sign-in."
                    )
                else:
                    raise RuntimeError(
                        "GitHub login is required. Run: "
                        "../.venv/bin/python copilot_usage.py --login"
                    )
            page.wait_for_timeout(1000)
            return compute_page_stats(page.locator("body").inner_text(), limit)
        finally:
            context.close()


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
    usage_source = config.get("usage_source", _DEFAULT_CONFIG["usage_source"])

    try:
        if usage_source == "browser":
            stats = get_browser_usage(
                config.get("copilot_page_url", _DEFAULT_CONFIG["copilot_page_url"]),
                limit,
                show_browser="--login" in sys.argv,
                auto_login=bool(config.get("auto_login", _DEFAULT_CONFIG["auto_login"])),
            )
        elif usage_source == "api":
            token = get_token(keychain_service)
            data = get_usage(github_user, token, api_version)
            stats = compute_stats(data, limit)
        else:
            raise RuntimeError("usage_source must be either 'api' or 'browser'")
        stats = add_pace_stats(stats)
        print(json.dumps(stats))
    except Exception as exc:  # noqa: BLE001
        # Print to stdout so the Übersicht widget can display the error message.
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
