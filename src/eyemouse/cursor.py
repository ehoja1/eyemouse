"""Operating-system cursor backends.

The rest of the application only talks to the :class:`CursorBackend` protocol, so the real
mouse (``pyautogui``) can be swapped for :class:`DryRunBackend` for development, tests and
demos without moving anything on screen.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Protocol

from .errors import EyeMouseError, MissingDependencyError

log = logging.getLogger(__name__)

DEFAULT_SCREEN = (1920, 1080)


class CursorBackend(Protocol):
    def screen_size(self) -> tuple[int, int]: ...

    def position(self) -> tuple[int, int]: ...

    def move_to(self, x: int, y: int) -> None: ...

    def click(self, button: str = "left") -> None: ...


class PyAutoGuiBackend:
    """Moves the real cursor using ``pyautogui``."""

    def __init__(self) -> None:
        try:
            import pyautogui
        except ImportError as exc:
            raise MissingDependencyError("pyautogui", "control") from exc
        except Exception as exc:  # e.g. no DISPLAY on Linux
            raise EyeMouseError(f"Cannot access the desktop for mouse control: {exc}") from exc
        # pyautogui's corner "fail-safe" would raise whenever the gaze reaches a screen
        # corner, and its built-in delay would make the cursor feel sluggish.
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.0
        self._pg: Any = pyautogui

    def screen_size(self) -> tuple[int, int]:
        size = self._pg.size()
        return int(size.width), int(size.height)

    def position(self) -> tuple[int, int]:
        pos = self._pg.position()
        return int(pos.x), int(pos.y)

    def move_to(self, x: int, y: int) -> None:
        self._pg.moveTo(x, y, _pause=False)

    def click(self, button: str = "left") -> None:
        self._pg.click(button=button, _pause=False)


class DryRunBackend:
    """Pretends to be a mouse: keeps a virtual cursor and logs clicks."""

    def __init__(self, screen: tuple[int, int] | None = None) -> None:
        self._screen = screen or self._detect_screen()
        self._pos = (self._screen[0] // 2, self._screen[1] // 2)
        self.clicks: list[tuple[int, int, str]] = []

    @staticmethod
    def _detect_screen() -> tuple[int, int]:
        try:
            import pyautogui

            size = pyautogui.size()
            return int(size.width), int(size.height)
        except Exception:
            return DEFAULT_SCREEN

    def screen_size(self) -> tuple[int, int]:
        return self._screen

    def position(self) -> tuple[int, int]:
        return self._pos

    def move_to(self, x: int, y: int) -> None:
        self._pos = (x, y)

    def click(self, button: str = "left") -> None:
        self.clicks.append((*self._pos, button))
        log.info("[dry-run] %s click at %s", button, self._pos)


class HardwareMouseWatcher:
    """Detects that a person moved the physical mouse, so we can stop fighting them."""

    def __init__(self, threshold_px: float) -> None:
        self.threshold_px = threshold_px
        self._last: tuple[int, int] | None = None

    def commanded(self, x: int, y: int) -> None:
        self._last = (x, y)

    def reset(self) -> None:
        self._last = None

    def hijacked(self, actual: tuple[int, int]) -> bool:
        if self._last is None:
            return False
        return math.dist(actual, self._last) > self.threshold_px
