"""
Unit tests for copilot_usage.py

Run with:  python3 -m pytest tests/ -v
"""

import io
import json
import sys
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock

import importlib

# Make the script importable without executing main()
sys.path.insert(0, str(Path(__file__).parent.parent))


def _import_fresh():
    """Import (or re-import) copilot_usage so each test gets a clean state."""
    if "copilot_usage" in sys.modules:
        del sys.modules["copilot_usage"]
    return importlib.import_module("copilot_usage")


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


class TestComputeStats:
    def setup_method(self):
        self.cu = _import_fresh()

    def test_basic_calculation(self):
        data = {
            "usageItems": [
                {"grossQuantity": 500},
                {"grossQuantity": 323.4},
            ]
        }
        result = self.cu.compute_stats(data, 1500)
        assert result["used"] == 823.4
        assert result["limit"] == 1500
        assert result["percentage"] == 54.9
        assert result["remaining"] == 676.6

    def test_zero_usage(self):
        result = self.cu.compute_stats({"usageItems": []}, 1500)
        assert result["used"] == 0.0
        assert result["percentage"] == 0.0
        assert result["remaining"] == 1500

    def test_exceeds_limit_caps_at_100(self):
        data = {"usageItems": [{"grossQuantity": 2000}]}
        result = self.cu.compute_stats(data, 1500)
        assert result["percentage"] == 100.0
        assert result["remaining"] == 0.0

    def test_missing_gross_quantity_defaults_to_zero(self):
        data = {"usageItems": [{"model": "GPT-5"}]}
        result = self.cu.compute_stats(data, 1000)
        assert result["used"] == 0.0

    def test_no_usage_items_key(self):
        result = self.cu.compute_stats({}, 1000)
        assert result["used"] == 0.0

    def test_zero_limit_returns_zero_percentage(self):
        data = {"usageItems": [{"grossQuantity": 100}]}
        result = self.cu.compute_stats(data, 0)
        assert result["percentage"] == 0.0


class TestComputePageStats:
    def setup_method(self):
        self.cu = _import_fresh()

    def test_parses_used_and_limit_from_page(self):
        result = self.cu.compute_page_stats(
            "Premium requests: 3,042 of 12,000 premium requests", 1500
        )
        assert result == {
            "used": 3042.0,
            "limit": 12000.0,
            "percentage": 25.4,
            "remaining": 8958.0,
        }

    def test_parses_ai_credits_from_copilot_settings_page(self):
        result = self.cu.compute_page_stats(
            "Usage this cycle\n3,685 / 9,900 AI credits", 1500
        )
        assert result == {
            "used": 3685.0,
            "limit": 9900.0,
            "percentage": 37.2,
            "remaining": 6215.0,
        }

    def test_parses_remaining_requests_from_page(self):
        result = self.cu.compute_page_stats(
            "You have 9,900 premium requests remaining", 12000
        )
        assert result["used"] == 2100.0
        assert result["remaining"] == 9900.0

    def test_fails_when_page_has_no_usage(self):
        import pytest

        with pytest.raises(RuntimeError, match="Could not find"):
            self.cu.compute_page_stats("Welcome to GitHub", 12000)


# ---------------------------------------------------------------------------
# add_pace_stats
# ---------------------------------------------------------------------------


class TestAddPaceStats:
    def setup_method(self):
        self.cu = _import_fresh()

    def test_over_budget_pace(self):
        # 15 Jan (31 days): expected budget by now is 1500/31*15 ~= 725.8
        now = datetime(2026, 1, 15)
        stats = {"used": 900.0, "limit": 1500.0}
        result = self.cu.add_pace_stats(stats, now=now)
        assert result["pace"]["status"] == "over"
        assert result["pace"]["days_in_month"] == 31
        assert result["pace"]["day_of_month"] == 15

    def test_under_budget_pace(self):
        now = datetime(2026, 1, 15)
        stats = {"used": 400.0, "limit": 1500.0}
        result = self.cu.add_pace_stats(stats, now=now)
        assert result["pace"]["status"] == "under"

    def test_on_track_pace(self):
        now = datetime(2026, 1, 15)
        # expected_used_by_now == 1500/31*15 ~= 725.8 -> use that exactly
        expected = 1500.0 / 31 * 15
        stats = {"used": expected, "limit": 1500.0}
        result = self.cu.add_pace_stats(stats, now=now)
        assert result["pace"]["status"] == "on_track"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def setup_method(self):
        self.cu = _import_fresh()

    def test_defaults_when_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.cu, "__file__", str(tmp_path / "copilot_usage.py"))
        config = self.cu.load_config()
        assert config["ai_credit_limit"] == 1500
        assert config["keychain_service"] == "github-copilot-widget"
        assert config["auto_login"] is False

    def test_overrides_from_config_file(self, tmp_path, monkeypatch):
        cfg = {"github_user": "alice", "ai_credit_limit": 7000, "auto_login": True}
        (tmp_path / "config.json").write_text(json.dumps(cfg))
        monkeypatch.setattr(self.cu, "__file__", str(tmp_path / "copilot_usage.py"))
        config = self.cu.load_config()
        assert config["github_user"] == "alice"
        assert config["ai_credit_limit"] == 7000
        assert config["auto_login"] is True
        # defaults still present
        assert config["api_version"] == "2026-03-10"

    def test_invalid_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        (tmp_path / "config.json").write_text("NOT JSON")
        monkeypatch.setattr(self.cu, "__file__", str(tmp_path / "copilot_usage.py"))
        config = self.cu.load_config()
        assert config["ai_credit_limit"] == 1500


# ---------------------------------------------------------------------------
# get_usage (mocked network)
# ---------------------------------------------------------------------------


class TestGetUsage:
    def setup_method(self):
        self.cu = _import_fresh()

    def _make_response(self, payload: dict):
        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

        return FakeResponse(json.dumps(payload).encode())

    def test_constructs_correct_url(self):
        fake_response = {"usageItems": [{"grossQuantity": 100}]}
        response_obj = self._make_response(fake_response)

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            return response_obj

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.cu.get_usage("alice", "tok123", "2026-03-10")

        assert "alice" in captured["url"]
        assert "ai_credit/usage" in captured["url"]
        assert result == fake_response

    def test_bearer_token_in_auth_header(self):
        fake_response = {"usageItems": []}
        response_obj = self._make_response(fake_response)
        captured = {}

        def fake_urlopen(req):
            captured["headers"] = dict(req.headers)
            return response_obj

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.cu.get_usage("alice", "mytoken", "2026-03-10")

        auth = captured["headers"].get("Authorization", "")
        assert auth.startswith("Bearer ")
        assert "mytoken" in auth

    def test_http_error_raises_runtime_error(self):
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url=None, code=401, msg="Unauthorized", hdrs=None, fp=None
            ),
        ):
            import pytest
            with pytest.raises(RuntimeError, match="401"):
                self.cu.get_usage("alice", "bad_token", "2026-03-10")
