from __future__ import annotations

import os
import sys


def configure_stdio() -> None:
    """Prefer UTF-8 on Windows consoles so box art / glyphs don't crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def supports_color(*, force: bool | None = None) -> bool:
    if force is False:
        return False
    if force is True:
        return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


class Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _c(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def hue(
        self,
        code: str,
        text: str,
        *,
        dim: bool = False,
        bold: bool = False,
        bright: bool = False,
    ) -> str:
        """Apply color with optional bold / bright / dim in one SGR."""
        if not self.enabled:
            return text
        # Map standard 30-37 / 90-97 style: "32" -> "92" when bright
        color = code
        if bright and code.isdigit():
            n = int(code)
            if 30 <= n <= 37:
                color = str(n + 60)
        parts: list[str] = []
        if bold:
            parts.append("1")
        if dim:
            parts.append("2")
        parts.append(color)
        return f"\033[{';'.join(parts)}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._c("1", text)

    def dim(self, text: str) -> str:
        return self._c("2", text)

    def green(self, text: str) -> str:
        return self._c("32", text)

    def red(self, text: str) -> str:
        return self._c("31", text)

    def yellow(self, text: str) -> str:
        return self._c("33", text)

    def cyan(self, text: str) -> str:
        return self._c("36", text)

    def magenta(self, text: str) -> str:
        return self._c("35", text)

    def blue(self, text: str) -> str:
        return self._c("34", text)

    def pass_fail(self, ok: bool, text: str | None = None) -> str:
        label = text or ("PASS" if ok else "FAIL")
        return self.green(label) if ok else self.red(label)

    def rank(self, place: int, text: str) -> str:
        if place == 1:
            return self.green(self.bold(text))
        if place == 2:
            return self.cyan(text)
        if place == 3:
            return self.yellow(text)
        return text


def short_model(name: str, width: int = 36) -> str:
    if len(name) <= width:
        return name
    return name[: width - 3] + "..."


def pad(text: str, width: int, *, right: bool = False) -> str:
    # Visible length ignores ANSI (approx: strip known prefixes — use plain pad for data)
    if right:
        return text.rjust(width)
    return text.ljust(width)


def visible_len(text: str) -> int:
    out = []
    i = 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            i = j + 1 if j >= 0 else i + 1
            continue
        out.append(text[i])
        i += 1
    return len("".join(out))


def pad_ansi(text: str, width: int, *, right: bool = False) -> str:
    pad_n = max(0, width - visible_len(text))
    return (" " * pad_n + text) if right else (text + " " * pad_n)
