"""Client-local reference attachment store.

Absolute paths stay here. Only basename metadata crosses the wire via
context.extra.reference_image.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_BYTES = 8_388_608  # 8 MB
ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


class ReferenceStore:
    def __init__(self) -> None:
        self._path: Path | None = None
        self._meta: dict[str, Any] | None = None

    def clear(self) -> None:
        self._path = None
        self._meta = None

    def has_attachment(self) -> bool:
        return self._path is not None and self._meta is not None

    def metadata(self) -> dict[str, Any] | None:
        if self._meta is None:
            return None
        return dict(self._meta)

    def absolute_path(self) -> Path | None:
        return self._path

    def attach(self, path: str | Path) -> dict[str, Any]:
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file():
            raise RuntimeError(f"Reference file not found: {candidate.name}")
        suffix = candidate.suffix.lower()
        media_type = ALLOWED_EXTENSIONS.get(suffix)
        if media_type is None:
            allowed = ", ".join(sorted({ext.lstrip(".") for ext in ALLOWED_EXTENSIONS}))
            raise RuntimeError(f"Unsupported reference type; allowed: {allowed}")
        size = candidate.stat().st_size
        if size < 1:
            raise RuntimeError("Reference file is empty")
        if size > MAX_BYTES:
            raise RuntimeError(f"Reference file exceeds {MAX_BYTES} bytes")

        meta: dict[str, Any] = {
            "file_name": candidate.name,
            "media_type": media_type,
            "byte_size": int(size),
        }
        if media_type != "image/svg+xml":
            width, height = _raster_dims(candidate)
            if width is not None and height is not None:
                meta["width_px"] = width
                meta["height_px"] = height

        self._path = candidate
        self._meta = meta
        return dict(meta)

    def consume_svg_path(self) -> Path:
        if self._path is None or self._meta is None:
            raise RuntimeError("No SVG attached; attach a local SVG before import")
        if self._meta.get("media_type") != "image/svg+xml":
            raise RuntimeError(
                "Attached reference is not SVG; import_svg_sketch requires image/svg+xml"
            )
        if not self._path.is_file():
            raise RuntimeError(f"Attached SVG missing on disk: {self._path.name}")
        return self._path

    def pick_file(self) -> dict[str, Any] | None:
        """Open a GUI file dialog and attach. Returns None if cancelled."""
        try:
            from PySide6 import QtWidgets
        except ImportError:
            try:
                from PySide2 import QtWidgets  # type: ignore
            except ImportError as exc:
                raise RuntimeError("No GUI file dialog available") from exc

        filters = (
            "Reference images (*.png *.jpg *.jpeg *.webp *.bmp *.svg);;"
            "SVG (*.svg);;"
            "All files (*.*)"
        )
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Attach Fixture reference",
            "",
            filters,
        )
        if not path:
            return None
        return self.attach(path)


_STORE = ReferenceStore()


def get_store() -> ReferenceStore:
    return _STORE


def _raster_dims(path: Path) -> tuple[int | None, int | None]:
    try:
        from PySide6 import QtGui
    except ImportError:
        try:
            from PySide2 import QtGui  # type: ignore
        except ImportError:
            return None, None
    image = QtGui.QImage(str(path))
    if image.isNull():
        return None, None
    width = int(image.width())
    height = int(image.height())
    if width < 1 or height < 1:
        return None, None
    return min(width, 16384), min(height, 16384)
