#!/usr/bin/env python3
"""
Turns a photo into the ASCII portrait shown on the left of the profile card.

Run this ONLY when you want to change the photo:
    pip install pillow numpy rembg onnxruntime
    python photo_to_ascii.py my_photo.jpg

It writes portrait.txt, which generate_profile.py reads. The daily GitHub
Action never runs this file, so the workflow stays dependency-free.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageFilter, ImageOps
from rembg import remove

LOGGER = logging.getLogger(__name__)

RAMP: Final = "@%#*+=-:. "  # darkest -> lightest
CROP_PADDING_PX: Final = 8
ALPHA_SUBJECT_THRESHOLD: Final = 60  # 0-255, minimum alpha to count as "subject"
ALPHA_KEEP_THRESHOLD: Final = 110  # 0-255, minimum alpha to render a character
CONTRAST_PERCENTILE: Final = (2, 98)

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Config:
    source: Path
    cols: int = 96
    aspect: float = 1.72  # svg line-height / char-width
    bust: float = 0.62  # how far down the body to keep, as a fraction of subject height
    detail: float = 2.3  # local-contrast gain (raise if the shirt looks like a blob)
    weight: float = 0.45  # how much overall light/dark shape to keep (0 = pure edges)


def parse_args(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=Path, help="source photo (jpg/png)")
    parser.add_argument("--cols", type=int, default=96, help="characters across")
    parser.add_argument(
        "--bust", type=float, default=0.62, help="fraction of subject height to keep"
    )
    parser.add_argument("--detail", type=float, default=2.3, help="local-contrast gain")
    parser.add_argument(
        "--weight", type=float, default=0.45, help="overall light/dark shape weight"
    )
    args = parser.parse_args(argv)
    return Config(
        source=args.source,
        cols=args.cols,
        bust=args.bust,
        detail=args.detail,
        weight=args.weight,
    )


def crop_to_subject(cut: Image.Image, bust: float) -> Image.Image:
    """Crop to the subject's alpha bounding box, keeping only head + torso."""
    alpha = np.asarray(cut)[:, :, 3]
    ys, xs = np.nonzero(alpha > ALPHA_SUBJECT_THRESHOLD)
    if ys.size == 0:
        raise ValueError("rembg found no subject in the image (empty alpha mask)")

    x0, x1 = int(xs.min()), int(xs.max())
    y0 = int(ys.min())
    y1 = int(y0 + (int(ys.max()) - y0) * bust)
    box = (
        max(0, x0 - CROP_PADDING_PX),
        max(0, y0 - CROP_PADDING_PX),
        min(cut.width, x1 + CROP_PADDING_PX),
        min(cut.height, y1),
    )
    return cut.crop(box)


def compute_ink(cut: Image.Image, detail: float, weight: float) -> tuple[FloatArray, FloatArray]:
    """Return a (ink, alpha) pair: per-pixel brightness ramp index source and opacity mask."""
    alpha = np.asarray(cut)[:, :, 3].astype(np.float64) / 255.0
    gray = np.asarray(ImageOps.autocontrast(cut.convert("L"), cutoff=1), dtype=np.int16)
    width = gray.shape[1]

    # local contrast: pulls folds/edges out of an otherwise flat dark shirt
    blur_radius = max(2, width // 55)
    blur = np.asarray(
        Image.fromarray(gray.astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur_radius)),
        dtype=np.int16,
    )
    ink = np.clip(150 + (gray - blur) * detail + (gray - 128) * weight, 0, 255)

    inside = alpha > 0.5
    if not inside.any():
        raise ValueError("subject mask is empty after cropping")
    lo, hi = np.percentile(ink[inside], CONTRAST_PERCENTILE)
    ink = np.clip((ink - lo) * 255.0 / max(1, hi - lo), 0, 255)
    return ink, alpha


def rasterize(ink: FloatArray, alpha: FloatArray, cols: int, aspect: float) -> list[str]:
    """Downsample ink/alpha to a cols x rows character grid and map to the RAMP."""
    height, width = ink.shape
    rows = max(1, round(cols * (height / width) / aspect))

    small = np.asarray(
        Image.fromarray(ink.astype(np.uint8)).resize((cols, rows), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )
    mask = np.asarray(
        Image.fromarray((alpha * 255).astype(np.uint8)).resize((cols, rows), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )

    steps = len(RAMP) - 1
    lines = []
    for y in range(rows):
        line = "".join(
            RAMP[round(small[y, x] / 255 * steps)] if mask[y, x] > ALPHA_KEEP_THRESHOLD else " "
            for x in range(cols)
        )
        lines.append(line.rstrip())
    return lines


def photo_to_ascii(config: Config) -> list[str]:
    if not config.source.exists():
        raise FileNotFoundError(f"source photo not found: {config.source}")

    image = ImageOps.exif_transpose(Image.open(config.source))
    cut = remove(image)  # cut the subject out of the background
    cut = crop_to_subject(cut, config.bust)
    ink, alpha = compute_ink(cut, config.detail, config.weight)
    return rasterize(ink, alpha, config.cols, config.aspect)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = parse_args(argv)

    try:
        lines = photo_to_ascii(config)
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("error: %s", exc)
        return 1

    art = "\n".join(lines)
    out_path = Path(__file__).parent / "portrait.txt"
    out_path.write_text(art, encoding="utf-8")

    LOGGER.info(art)
    LOGGER.info("\nwrote %s  (%d cols x %d rows)", out_path.name, config.cols, len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
