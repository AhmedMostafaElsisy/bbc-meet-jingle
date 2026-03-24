import logging
import os
import shutil

logger = logging.getLogger(__name__)


def get_audio_duration(path: str) -> float:
    """Return duration of an audio file in seconds, or 0.0 on failure."""
    if not os.path.exists(path):
        return 0.0
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        sound = pygame.mixer.Sound(path)
        return sound.get_length()
    except Exception as e:
        logger.warning("Could not read duration for %s: %s", path, e)
        return 0.0


def import_custom_jingle(source_path: str, dest_dir: str) -> str | None:
    """Copy an audio file into the custom jingles directory.

    Returns the destination filename, or None on failure.
    """
    if not os.path.isfile(source_path):
        logger.warning("Source file not found: %s", source_path)
        return None

    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(source_path)
    dest_path = os.path.join(dest_dir, filename)

    # Avoid overwriting — add suffix if needed
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        filename = f"{base}_{counter}{ext}"
        counter += 1

    shutil.copy2(source_path, dest_path)
    return filename


class AudioPlayer:
    def __init__(self, jingle_path: str) -> None:
        self._jingle_path = jingle_path
        self._available = False
        self._duration = 0.0
        self._init_mixer()

    def _init_mixer(self) -> None:
        if not os.path.exists(self._jingle_path):
            logger.warning("Jingle file not found: %s", self._jingle_path)
            return

        try:
            import pygame
            pygame.mixer.init()
            sound = pygame.mixer.Sound(self._jingle_path)
            self._duration = sound.get_length()
            self._available = True
        except Exception as e:
            logger.error("Failed to initialize audio mixer: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def duration(self) -> float:
        """Jingle duration in seconds, or 0.0 if unavailable."""
        return self._duration

    def switch_jingle(self, new_path: str) -> None:
        """Switch to a different jingle file."""
        if not os.path.exists(new_path):
            logger.warning("Jingle file not found: %s", new_path)
            self._available = False
            self._duration = 0.0
            return

        self._jingle_path = new_path
        self._duration = get_audio_duration(new_path)
        self._available = self._duration > 0

    def play(self, volume: float = 1.0) -> None:
        if not self._available:
            logger.warning("Audio not available, skipping jingle playback")
            return

        try:
            import pygame
            pygame.mixer.music.load(self._jingle_path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play()
        except Exception as e:
            logger.error("Failed to play jingle: %s", e)

    def stop(self) -> None:
        if not self._available:
            return
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception as e:
            logger.error("Failed to stop jingle: %s", e)

    def is_playing(self) -> bool:
        if not self._available:
            return False
        try:
            import pygame
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    def test(self, volume: float = 1.0) -> None:
        self.play(volume)
