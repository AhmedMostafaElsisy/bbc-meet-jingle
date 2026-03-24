import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config


class TestConfig:
    def test_app_dir_is_absolute(self):
        assert os.path.isabs(config.APP_DIR)

    def test_credentials_file_path(self):
        assert config.CREDENTIALS_FILE.endswith("credentials.json")
        assert os.path.isabs(config.CREDENTIALS_FILE)

    def test_token_file_path(self):
        assert config.TOKEN_FILE.endswith("token.json")

    def test_prefs_file_path(self):
        assert config.PREFS_FILE.endswith("prefs.json")

    def test_jingle_file_path(self):
        path = os.path.join(config.ASSETS_DIR, config.BUILTIN_JINGLES["BBC News"])
        assert path.endswith(os.path.join("assets", "bbc_news_theme.mp3"))

    def test_custom_jingles_dir(self):
        assert config.CUSTOM_JINGLES_DIR.endswith(os.path.join("assets", "custom"))

    def test_scopes_is_readonly_calendar(self):
        assert len(config.SCOPES) == 1
        assert "calendar.readonly" in config.SCOPES[0]

    def test_poll_interval(self):
        assert config.POLL_INTERVAL_SECONDS == 30

    def test_default_jingle_duration(self):
        assert config.DEFAULT_JINGLE_DURATION == 16.8
        assert isinstance(config.DEFAULT_JINGLE_DURATION, float)

    def test_builtin_jingles(self):
        assert "BBC News" in config.BUILTIN_JINGLES
        assert "Netflix" in config.BUILTIN_JINGLES
        assert config.BUILTIN_JINGLES["BBC News"] == "bbc_news_theme.mp3"
        assert config.BUILTIN_JINGLES["Netflix"] == "netflix.mp3"

    def test_default_jingle(self):
        assert config.DEFAULT_JINGLE == "BBC News"
        assert config.DEFAULT_JINGLE in config.BUILTIN_JINGLES

    def test_volume_presets(self):
        assert "Low" in config.VOLUME_PRESETS
        assert "Medium" in config.VOLUME_PRESETS
        assert "Full" in config.VOLUME_PRESETS
        assert config.VOLUME_PRESETS["Low"] == 0.3
        assert config.VOLUME_PRESETS["Medium"] == 0.6
        assert config.VOLUME_PRESETS["Full"] == 1.0

    def test_volume_presets_values_in_range(self):
        for label, vol in config.VOLUME_PRESETS.items():
            assert 0.0 <= vol <= 1.0, f"Volume '{label}' out of range: {vol}"

    def test_allowed_audio_extensions(self):
        assert ".mp3" in config.ALLOWED_AUDIO_EXTENSIONS
        assert ".wav" in config.ALLOWED_AUDIO_EXTENSIONS
        assert ".ogg" in config.ALLOWED_AUDIO_EXTENSIONS
        assert ".m4a" in config.ALLOWED_AUDIO_EXTENSIONS

    def test_urgent_seconds(self):
        assert config.URGENT_SECONDS == 10

    def test_live_timeout_seconds(self):
        assert config.LIVE_TIMEOUT_SECONDS == 120

    def test_default_work_schedule(self):
        assert config.DEFAULT_WORK_START == "09:00"
        assert config.DEFAULT_WORK_END == "18:00"
        assert config.DEFAULT_WORK_DAYS == [0, 1, 2, 3, 4]

    def test_snooze_options(self):
        assert "30 minutes" in config.SNOOZE_OPTIONS
        assert "1 hour" in config.SNOOZE_OPTIONS
        assert "2 hours" in config.SNOOZE_OPTIONS
        assert "Until tomorrow" in config.SNOOZE_OPTIONS
