#!/usr/bin/env python3
"""Build helper to generate a Windows .ico from the existing SVG favicon.

Source of truth icon asset in this repo:

- frontend/public/favicon.svg

We intentionally do NOT invent a new icon. This script rasterizes that SVG into
standard icon sizes and writes a multi-resolution `CommandDeck.ico`.

Implementation notes:
- Uses PySide6's SVG renderer (QtSvg) to avoid external Cairo/InkScape deps.
- Uses Pillow to write a multi-size .ico.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"


def _first_path_only_svg(svg_bytes: bytes) -> bytes:
    """Reduce the repo SVG to a minimal subset that QtSvg reliably renders.

    The current favicon uses masks/filters and CSS color spaces (display-p3)
    that QtSvg often parses as "valid" but renders as fully transparent.

    For Windows icons we only need a simple, high-contrast mark. We extract the
    first <path> element and build a clean SVG containing only that path.
    """

    root = ET.fromstring(svg_bytes)

    # Preserve the original viewBox when present, otherwise fall back to a
    # generic square.
    view_box = root.attrib.get("viewBox", "0 0 48 48")

    # Find the first SVG <path> with a 'd' attribute.
    path_el = None
    for el in root.iter():
        tag = el.tag
        if tag.endswith("path") and el.attrib.get("d"):
            path_el = el
            break
    if path_el is None:
        raise RuntimeError("Could not find a <path d=...> element in favicon.svg")

    d = path_el.attrib["d"]
    fill = path_el.attrib.get("fill") or "#863bff"

    minimal = (
        f'<svg xmlns="{SVG_NS}" viewBox="{view_box}">'  # no width/height needed
        f'<path d="{d}" fill="{fill}"/>'
        "</svg>"
    )
    return minimal.encode("utf-8")


def _qimage_has_any_alpha(image) -> bool:
    """Return True if any pixel in the QImage has alpha > 0."""

    # Avoid importing Qt types at module import time.
    from PySide6.QtGui import QImage

    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    ptr = rgba.bits()
    raw = ptr.tobytes() if hasattr(ptr, "tobytes") else bytes(ptr)

    # Alpha is the 4th byte for each pixel in RGBA8888.
    return any(raw[3::4])


def build_ico(
    *,
    svg_path: Path,
    out_ico: Path,
    sizes: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 128, 256),
) -> Path:
    from PIL import Image
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    if not svg_path.exists():
        raise FileNotFoundError(f"SVG icon not found at: {svg_path}")

    # QGuiApplication is required for many Qt GUI classes even when rendering
    # offscreen.
    app = QGuiApplication.instance() or QGuiApplication([])

    raw_svg_bytes = svg_path.read_bytes()

    # Use a "first path only" SVG because the original favicon uses
    # features that can result in fully transparent rendering under QtSvg.
    svg_bytes = _first_path_only_svg(raw_svg_bytes)
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        raise RuntimeError(
            "Qt SVG renderer could not parse the simplified icon SVG derived from: "
            f"{svg_path}"
        )

    # Pillow will only write multiple icon sizes if the source image is at
    # least the largest requested size. Render once at max size then let Pillow
    # downscale for each icon entry.
    max_size = max(sizes)
    image = QImage(max_size, max_size, QImage.Format_ARGB32)
    image.fill(0)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, float(max_size), float(max_size)))
    painter.end()

    if not _qimage_has_any_alpha(image):
        raise RuntimeError(
            "QtSvg rendered a fully transparent image; cannot build a usable .ico. "
            "(The source SVG may use unsupported features.)"
        )

    # Convert QImage -> Pillow Image
    # Use an explicit RGBA pixel format to avoid channel-order surprises.
    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    ptr = rgba.bits()
    raw = ptr.tobytes() if hasattr(ptr, "tobytes") else bytes(ptr)
    pil = Image.frombytes("RGBA", (rgba.width(), rgba.height()), raw)

    out_ico.parent.mkdir(parents=True, exist_ok=True)
    pil.save(out_ico, format="ICO", sizes=[(s, s) for s in sizes])

    # Sanity-check: ensure the file actually contains multiple icon sizes.
    try:
        check = Image.open(out_ico)
        embedded_sizes = check.info.get("sizes")
        if not embedded_sizes or len(embedded_sizes) < 2:
            raise RuntimeError(
                f"Generated ICO appears invalid (embedded sizes: {embedded_sizes!r})."
            )
    except Exception as exc:
        raise RuntimeError(f"Generated ICO validation failed: {exc}") from exc

    return out_ico


def main() -> int:
    project_root = Path(__file__).resolve().parent
    svg = project_root / "frontend" / "public" / "favicon.svg"
    out_ico = project_root / "CommandDeck.ico"
    build_ico(svg_path=svg, out_ico=out_ico)
    print(f"[buildicon] Wrote: {out_ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

