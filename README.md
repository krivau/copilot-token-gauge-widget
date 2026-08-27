# copilot-token-gauge-widget

A macOS **Übersicht** desktop widget that live-tracks your monthly GitHub
Copilot AI-Credit usage and renders it as a classic half-gauge with a dial.

```
       ╭────────────╮
  │  GGGYYYRRR │
  │     ╱      │
  │   54.9%    │
       │            │
       │ 823 / 1500 │
       │ AI Credits │
       ╰────────────╯
```

The gauge refreshes every 5 minutes, shows fixed green, yellow, and red
60-degree bands, and needs no running daemon — Übersicht handles everything.

---

## Architecture

```
GitHub Billing API
       │
       │  every 5 min
       ▼
copilot_usage.py   ← reads PAT from macOS Keychain
       │
       │  JSON
       ▼
copilot-gauge.jsx  ← Übersicht widget (SVG gauge)
       │
       ▼
   macOS desktop
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| [Übersicht](https://tracesof.net/uebersicht/) | `brew install --cask ubersicht` |
| Python 3 | Ships with macOS / `brew install python` |

---

## Installation

### 1 — Clone into your Übersicht widgets folder

```bash
cd ~/Library/Application\ Support/Übersicht/widgets
git clone https://github.com/krivau/copilot-token-gauge-widget.git
```

### 2 — Choose a usage source

For a personal Copilot plan, use the billing API. Store a fine-grained
Personal Access Token with **Billing → Plan Read** permission in the macOS
Keychain:

Create a fine-grained Personal Access Token with **Billing → Plan Read**
permission, then add it once:

```bash
security add-generic-password \
  -a "$USER" \
  -s "github-copilot-widget" \
  -w "github_pat_YOUR_TOKEN"
```

The Python script reads the PAT at runtime; it is **never** stored in source
code or on disk.

For a company-managed Copilot seat, use `"usage_source": "browser"` instead.
Create a virtual environment beside the widget, then install Playwright:

```bash
cd ~/Library/Application\ Support/Übersicht/widgets
python3 -m venv .venv
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
```

Then sign in once in a visible local browser window:

```bash
../.venv/bin/python copilot_usage.py --login
```

The session stays in `.copilot-browser-profile/` beside the script and is not
committed. GitHub login, including MFA, happens in the browser; no cookies are
read or exported by the widget.

### 3 — Create your local `config.json`

`config.json` and `local.config.json` hold machine-specific values (your GitHub
username, absolute paths) and are **gitignored** — they are never committed,
so the repo can safely be public.

```bash
cp config.example.json config.json
```

Then edit `config.json`:

```json
{
  "github_user": "YOUR_GITHUB_USERNAME",
  "ai_credit_limit": 1500,
  "api_version": "2026-03-10",
  "keychain_service": "github-copilot-widget",
  "usage_source": "browser",
  "copilot_page_url": "https://github.com/settings/copilot",
  "widget_top": "40px",
  "widget_right": "40px",
  "refresh_frequency_ms": 300000
}
```

| Key | Description |
|-----|-------------|
| `github_user` | Your GitHub username |
| `ai_credit_limit` | Monthly credit cap (Pro = 1 500, Pro+ = 7 000, Max = 20 000) |
| `api_version` | GitHub API version header |
| `keychain_service` | Name of the Keychain entry created in step 2 |
| `usage_source` | `api` for personal billing API usage, or `browser` for visible Copilot plan usage |
| `copilot_page_url` | Authenticated GitHub page that displays the Copilot allowance |
| `widget_top` / `widget_right` | CSS position on your desktop |
| `refresh_frequency_ms` | Refresh interval in milliseconds (default 5 min) |

### 4 — Create your local widget path override

`copilot-gauge.jsx` imports `WIDGET_DIR` from `local.config.json`, which is
also gitignored so your local macOS username/path never ends up in the repo.
A plain JSON file is used (rather than `.js`) because Übersicht's widget
scanner tries to parse every top-level `.js`/`.jsx` file as its own widget.

```bash
cp local.config.example.json local.config.json
```

Then edit `local.config.json`:

```json
{
  "WIDGET_DIR": "/Users/YOUR_USER/Library/Application Support/Übersicht/widgets/copilot-token-gauge-widget"
}
```

Übersicht will pick up the widget automatically once it is placed in the
widgets folder.

---

## Manual test

Run the Python script directly to verify your token and API access:

```bash
python3 copilot_usage.py
```

Expected output:

```json
{
  "used": 823.4,
  "limit": 1500,
  "percentage": 54.9,
  "remaining": 676.6
}
```

---

## Running the tests

```bash
python3 -m pytest tests/ -v
```

---

## Notes

* This widget uses the **AI Credits** billing endpoint introduced on
  1 June 2026.  If you are on a grandfathered annual plan that still counts
  *premium requests*, change the URL in `copilot_usage.py` to
  `/settings/billing/premium_request/usage`.
* The billing API only exposes **personal** Copilot usage.  Organisation- or
  enterprise-managed seats are not surfaced by this endpoint.
* `ai_credit_limit` is intentionally configurable because GitHub's flex
  allotment may vary; keep it up-to-date with your plan.

---
