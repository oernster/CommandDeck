#!/usr/bin/env python3
"""Windows icon helpers.

The installer/runtime build pipeline expects a *square*, multi-size `.ico`.

In practice, online converters sometimes produce non-square icon entries (e.g.
32x31) which can lead to missing/blank icons in Windows Shell (Start menu /
Desktop shortcuts).

This module provides a small normalizer that:
- pads to square with transparency
- writes standard icon sizes
"""

from __future__ import annotations

from pathlib import Path

STANDARD_ICO_SIZES: tuple[int, ...] = (16, 24, 32, 40, 48, 64, 128, 256)


def ensure_windows_ico(ico_path: Path) -> None:
    """Ensure `ico_path` is a square multi-size Windows `.ico`.

    This is intentionally tolerant: if the input icon is non-square or contains
    too few sizes, it will be rewritten in-place.
    """

    from PIL import Image, ImageOps

    if not ico_path.exists():
        raise FileNotFoundError(f"ICO not found at: {ico_path}")

    # Load the largest available representation.
    try:
        src = Image.open(ico_path).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to read .ico at {ico_path}: {exc}") from exc

    # Pad to square with transparency (Windows expects square icon entries).
    max_side = int(max(STANDARD_ICO_SIZES))
    target: tuple[int, int] = (max_side, max_side)
    contained = ImageOps.contain(src, target, method=Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    x = (target[0] - contained.size[0]) // 2
    y = (target[1] - contained.size[1]) // 2
    canvas.paste(contained, (x, y), contained)

    # Write standard sizes in one ICO.
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(ico_path, format="ICO", sizes=[(s, s) for s in STANDARD_ICO_SIZES])

    # Validate we now have multiple square sizes.
    check = Image.open(ico_path)
    sizes = check.info.get("sizes")
    if not sizes:
        raise RuntimeError(f"ICO validation failed; no embedded sizes in {ico_path}")
    if any(w != h for (w, h) in sizes):
        raise RuntimeError(
            f"ICO validation failed; non-square sizes {sizes} in {ico_path}"
        )
