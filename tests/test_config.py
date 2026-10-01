"""設定模型測試。"""

from __future__ import annotations

from app.config import THEME_DARK, THEME_LIGHT, AppConfig


def test_defaults():
    cfg = AppConfig()
    assert cfg.daily_time == "09:00"
    assert cfg.theme == THEME_DARK
    assert cfg.headless is True
    assert cfg.concurrent_accounts == 1


def test_normalize_clamps_and_fixes():
    cfg = AppConfig.from_dict(
        {
            "daily_time": "25:99",
            "theme": "rainbow",
            "browser_channel": "netscape",
            "jitter_minutes": 999,
            "timeout_seconds": 1,
            "concurrent_accounts": 99,
            "log_level": "TRACE",
            "unknown_key": "ignored",
        }
    )
    assert cfg.daily_time == "09:00"
    assert cfg.theme == THEME_DARK
    assert cfg.browser_channel == "chromium"
    assert cfg.jitter_minutes == 180
    assert cfg.timeout_seconds == 15
    assert cfg.concurrent_accounts == 3
    assert cfg.log_level == "INFO"
    assert not hasattr(cfg, "unknown_key")


def test_time_normalisation():
    cfg = AppConfig.from_dict({"daily_time": "7:5"})
    assert cfg.daily_time == "07:05"
    assert cfg.daily_time_obj.hour == 7
    assert cfg.daily_time_obj.minute == 5


def test_save_and_load_roundtrip(temp_root):
    cfg = AppConfig()
    cfg.daily_time = "21:30"
    cfg.theme = THEME_LIGHT
    cfg.jitter_minutes = 5
    cfg.save()

    loaded = AppConfig.load()
    assert loaded.daily_time == "21:30"
    assert loaded.theme == THEME_LIGHT
    assert loaded.jitter_minutes == 5


def test_jitter_is_stable_for_same_seed():
    cfg = AppConfig()
    cfg.jitter_minutes = 30
    first = cfg.daily_jitter_minutes("2026-09-28")
    second = cfg.daily_jitter_minutes("2026-09-28")
    assert first == second
    assert -30 <= first <= 30


def test_jitter_zero_when_disabled():
    cfg = AppConfig()
    cfg.jitter_minutes = 0
    assert cfg.daily_jitter_minutes("2026-09-28") == 0
