"""Small standard-library image loader for controlled vision fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

RGB = tuple[int, int, int]


class VisionImageError(ValueError):
    """Structured image loading error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PixelImage:
    """Immutable RGB pixel image used by deterministic vision helpers."""

    width: int
    height: int
    pixels: tuple[RGB, ...]
    source_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or isinstance(self.width, bool) or self.width <= 0:
            raise VisionImageError("invalid_dimensions", "image width must be a positive integer")
        if not isinstance(self.height, int) or isinstance(self.height, bool) or self.height <= 0:
            raise VisionImageError("invalid_dimensions", "image height must be a positive integer")
        if len(self.pixels) != self.width * self.height:
            raise VisionImageError("invalid_pixel_count", "pixel count does not match image dimensions")
        for pixel in self.pixels:
            if (
                not isinstance(pixel, tuple)
                or len(pixel) != 3
                or any(not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel <= 255 for channel in pixel)
            ):
                raise VisionImageError("invalid_pixel", "pixels must be RGB integer triples in range 0..255")

    def pixel_at(self, x: int, y: int) -> RGB:
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise VisionImageError("pixel_out_of_bounds", "pixel coordinates are outside image bounds")
        return self.pixels[y * self.width + x]

    def colors(self) -> set[RGB]:
        return set(self.pixels)


def load_ppm(path: str | Path) -> PixelImage:
    """Load a PPM P3 or P6 image without optional dependencies."""

    source = Path(path)
    try:
        with source.open("rb") as handle:
            image = _load_ppm_stream(handle)
    except FileNotFoundError as exc:
        raise VisionImageError("image_not_found", f"image not found: {source}") from exc
    except OSError as exc:
        raise VisionImageError("image_read_error", f"could not read image: {source}") from exc
    return PixelImage(image.width, image.height, image.pixels, source.as_posix())


def load_image(path: str | Path) -> PixelImage:
    """Load supported image formats; currently PPM P3/P6 only."""

    return load_ppm(path)


def _load_ppm_stream(handle: BinaryIO) -> PixelImage:
    magic = _read_token(handle)
    if magic not in (b"P3", b"P6"):
        raise VisionImageError("unsupported_image_format", "only PPM P3 and P6 images are supported")

    width = _parse_positive_int(_read_token(handle), "width")
    height = _parse_positive_int(_read_token(handle), "height")
    max_value = _parse_positive_int(_read_token(handle), "max_value")
    if max_value != 255:
        raise VisionImageError("unsupported_ppm_max_value", "only max value 255 is supported")

    pixel_count = width * height
    if magic == b"P3":
        channels = [_parse_channel(_read_token(handle)) for _ in range(pixel_count * 3)]
        pixels = tuple((channels[index], channels[index + 1], channels[index + 2]) for index in range(0, len(channels), 3))
    else:
        raw = handle.read(pixel_count * 3)
        if len(raw) != pixel_count * 3:
            raise VisionImageError("truncated_image", "P6 pixel data is shorter than expected")
        pixels = tuple((raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3))

    return PixelImage(width, height, pixels)


def _parse_positive_int(token: bytes, field: str) -> int:
    try:
        value = int(token.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VisionImageError("invalid_ppm_header", f"invalid PPM {field}") from exc
    if value <= 0:
        raise VisionImageError("invalid_ppm_header", f"PPM {field} must be positive")
    return value


def _parse_channel(token: bytes) -> int:
    value = _parse_positive_or_zero_int(token, "channel")
    if value > 255:
        raise VisionImageError("invalid_ppm_channel", "PPM channel value must be in range 0..255")
    return value


def _parse_positive_or_zero_int(token: bytes, field: str) -> int:
    try:
        value = int(token.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VisionImageError("invalid_ppm_data", f"invalid PPM {field}") from exc
    if value < 0:
        raise VisionImageError("invalid_ppm_data", f"PPM {field} must be non-negative")
    return value


def _read_token(handle: BinaryIO) -> bytes:
    token = bytearray()
    while True:
        char = handle.read(1)
        if not char:
            if token:
                return bytes(token)
            raise VisionImageError("truncated_image", "unexpected end of PPM data")
        if char == b"#":
            handle.readline()
            if token:
                return bytes(token)
            continue
        if char in b" \t\r\n":
            if token:
                return bytes(token)
            continue
        token.extend(char)
