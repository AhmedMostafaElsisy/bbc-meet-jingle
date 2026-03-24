import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from audio_player import AudioPlayer, get_audio_duration, import_custom_jingle


@pytest.fixture
def mock_player():
    """Create an AudioPlayer with pygame fully mocked."""
    with (
        patch("audio_player.os.path.exists", return_value=True),
        patch("pygame.mixer.init"),
        patch("pygame.mixer.Sound") as mock_sound_cls,
    ):
        mock_sound = MagicMock()
        mock_sound.get_length.return_value = 16.8
        mock_sound_cls.return_value = mock_sound
        player = AudioPlayer("/fake/jingle.mp3")
        yield player


# ------------------------------------------------------------------
# AudioPlayer init
# ------------------------------------------------------------------


class TestAudioPlayerInit:
    def test_not_available_when_file_missing(self, tmp_path):
        player = AudioPlayer(str(tmp_path / "nonexistent.mp3"))
        assert player.available is False
        assert player.duration == 0.0

    @patch("audio_player.os.path.exists", return_value=True)
    @patch("pygame.mixer.init")
    @patch("pygame.mixer.Sound")
    def test_available_when_file_exists_and_mixer_ok(self, mock_sound_cls, mock_init, mock_exists):
        mock_sound = MagicMock()
        mock_sound.get_length.return_value = 16.8
        mock_sound_cls.return_value = mock_sound

        player = AudioPlayer("/fake/jingle.mp3")
        assert player.available is True
        assert player.duration == 16.8
        mock_init.assert_called_once()

    @patch("audio_player.os.path.exists", return_value=True)
    @patch("pygame.mixer.init", side_effect=RuntimeError("no audio device"))
    def test_not_available_when_mixer_fails(self, mock_init, mock_exists):
        player = AudioPlayer("/fake/jingle.mp3")
        assert player.available is False
        assert player.duration == 0.0


# ------------------------------------------------------------------
# Duration
# ------------------------------------------------------------------


class TestAudioPlayerDuration:
    def test_duration_zero_when_not_available(self, tmp_path):
        player = AudioPlayer(str(tmp_path / "nonexistent.mp3"))
        assert player.duration == 0.0

    def test_duration_from_sound(self, mock_player):
        assert mock_player.duration == 16.8


# ------------------------------------------------------------------
# switch_jingle
# ------------------------------------------------------------------


class TestSwitchJingle:
    def test_switch_to_valid_file(self, mock_player):
        with (
            patch("audio_player.os.path.exists", return_value=True),
            patch("audio_player.get_audio_duration", return_value=2.5),
        ):
            mock_player.switch_jingle("/fake/netflix.mp3")
            assert mock_player.available is True
            assert mock_player.duration == 2.5

    def test_switch_to_missing_file(self, mock_player):
        with patch("audio_player.os.path.exists", return_value=False):
            mock_player.switch_jingle("/fake/missing.mp3")
            assert mock_player.available is False
            assert mock_player.duration == 0.0

    def test_switch_to_unreadable_file(self, mock_player):
        with (
            patch("audio_player.os.path.exists", return_value=True),
            patch("audio_player.get_audio_duration", return_value=0.0),
        ):
            mock_player.switch_jingle("/fake/corrupt.mp3")
            assert mock_player.available is False


# ------------------------------------------------------------------
# Play / Stop / IsPlaying / Test
# ------------------------------------------------------------------


class TestAudioPlayerPlay:
    def test_play_does_nothing_when_not_available(self, tmp_path):
        player = AudioPlayer(str(tmp_path / "nonexistent.mp3"))
        player.play(volume=0.5)

    def test_play_loads_and_plays(self, mock_player):
        with (
            patch("pygame.mixer.music.load") as mock_load,
            patch("pygame.mixer.music.set_volume") as mock_vol,
            patch("pygame.mixer.music.play") as mock_play,
        ):
            mock_player.play(volume=0.7)
            mock_load.assert_called_once_with("/fake/jingle.mp3")
            mock_vol.assert_called_once_with(0.7)
            mock_play.assert_called_once()

    def test_play_clamps_volume(self, mock_player):
        with (
            patch("pygame.mixer.music.load"),
            patch("pygame.mixer.music.set_volume") as mock_vol,
            patch("pygame.mixer.music.play"),
        ):
            mock_player.play(volume=1.5)
            mock_vol.assert_called_with(1.0)

            mock_player.play(volume=-0.5)
            mock_vol.assert_called_with(0.0)


class TestAudioPlayerStop:
    def test_stop_does_nothing_when_not_available(self, tmp_path):
        player = AudioPlayer(str(tmp_path / "nonexistent.mp3"))
        player.stop()

    def test_stop_calls_mixer(self, mock_player):
        with patch("pygame.mixer.music.stop") as mock_stop:
            mock_player.stop()
            mock_stop.assert_called_once()


class TestAudioPlayerIsPlaying:
    def test_is_playing_false_when_not_available(self, tmp_path):
        player = AudioPlayer(str(tmp_path / "nonexistent.mp3"))
        assert player.is_playing() is False

    def test_is_playing_delegates_to_mixer(self, mock_player):
        with patch("pygame.mixer.music.get_busy", return_value=True):
            assert mock_player.is_playing() is True


class TestAudioPlayerTest:
    def test_test_calls_play(self, mock_player):
        with (
            patch("pygame.mixer.music.load"),
            patch("pygame.mixer.music.set_volume") as mock_vol,
            patch("pygame.mixer.music.play") as mock_play,
        ):
            mock_player.test(volume=0.6)
            mock_play.assert_called_once()
            mock_vol.assert_called_once_with(0.6)


# ------------------------------------------------------------------
# get_audio_duration
# ------------------------------------------------------------------


class TestGetAudioDuration:
    def test_returns_zero_for_missing_file(self):
        assert get_audio_duration("/nonexistent/file.mp3") == 0.0

    @patch("audio_player.os.path.exists", return_value=True)
    @patch("pygame.mixer.get_init", return_value=True)
    @patch("pygame.mixer.Sound")
    def test_returns_duration_for_valid_file(self, mock_sound_cls, mock_get_init, mock_exists):
        mock_sound = MagicMock()
        mock_sound.get_length.return_value = 5.0
        mock_sound_cls.return_value = mock_sound
        assert get_audio_duration("/fake/file.mp3") == 5.0

    @patch("audio_player.os.path.exists", return_value=True)
    @patch("pygame.mixer.get_init", return_value=False)
    @patch("pygame.mixer.init")
    @patch("pygame.mixer.Sound")
    def test_inits_mixer_if_not_initialized(self, mock_sound_cls, mock_init, mock_get_init, mock_exists):
        mock_sound = MagicMock()
        mock_sound.get_length.return_value = 3.0
        mock_sound_cls.return_value = mock_sound
        result = get_audio_duration("/fake/file.mp3")
        mock_init.assert_called_once()
        assert result == 3.0


# ------------------------------------------------------------------
# import_custom_jingle
# ------------------------------------------------------------------


class TestImportCustomJingle:
    def test_returns_none_for_missing_source(self, tmp_path):
        result = import_custom_jingle(
            str(tmp_path / "nonexistent.mp3"),
            str(tmp_path / "custom"),
        )
        assert result is None

    def test_copies_file_to_dest(self, tmp_path):
        source = tmp_path / "my_jingle.mp3"
        source.write_bytes(b"fake audio data")
        dest_dir = tmp_path / "custom"

        result = import_custom_jingle(str(source), str(dest_dir))

        assert result == "my_jingle.mp3"
        assert (dest_dir / "my_jingle.mp3").exists()
        assert (dest_dir / "my_jingle.mp3").read_bytes() == b"fake audio data"

    def test_avoids_overwriting_existing_file(self, tmp_path):
        source = tmp_path / "my_jingle.mp3"
        source.write_bytes(b"new data")
        dest_dir = tmp_path / "custom"
        dest_dir.mkdir()
        (dest_dir / "my_jingle.mp3").write_bytes(b"old data")

        result = import_custom_jingle(str(source), str(dest_dir))

        assert result == "my_jingle_1.mp3"
        assert (dest_dir / "my_jingle_1.mp3").read_bytes() == b"new data"
        assert (dest_dir / "my_jingle.mp3").read_bytes() == b"old data"

    def test_creates_dest_dir_if_missing(self, tmp_path):
        source = tmp_path / "sound.wav"
        source.write_bytes(b"wav data")
        dest_dir = tmp_path / "deep" / "nested" / "custom"

        result = import_custom_jingle(str(source), str(dest_dir))

        assert result == "sound.wav"
        assert (dest_dir / "sound.wav").exists()
