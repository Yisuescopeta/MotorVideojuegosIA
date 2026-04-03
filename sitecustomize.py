from __future__ import annotations

import struct
import sys
import time
import types
import zlib
from pathlib import Path
from typing import Any


def _install_pyray_stub(*, force: bool = False) -> None:
    if not force and "pyray" in sys.modules and sys.modules["pyray"] is not None:
        return

    module = types.ModuleType("pyray")

    class Vector2:
        __slots__ = ("x", "y")

        def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
            self.x = float(x)
            self.y = float(y)

        def __iter__(self):
            yield self.x
            yield self.y

        def __repr__(self) -> str:
            return f"Vector2({self.x}, {self.y})"

    class Rectangle:
        __slots__ = ("x", "y", "width", "height")

        def __init__(self, x: float = 0.0, y: float = 0.0, width: float = 0.0, height: float = 0.0) -> None:
            self.x = float(x)
            self.y = float(y)
            self.width = float(width)
            self.height = float(height)

        def __repr__(self) -> str:
            return f"Rectangle({self.x}, {self.y}, {self.width}, {self.height})"

    class Color:
        __slots__ = ("r", "g", "b", "a")

        def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: int = 255) -> None:
            self.r = int(r)
            self.g = int(g)
            self.b = int(b)
            self.a = int(a)

        def __iter__(self):
            yield self.r
            yield self.g
            yield self.b
            yield self.a

        def __repr__(self) -> str:
            return f"Color({self.r}, {self.g}, {self.b}, {self.a})"

    class Camera2D:
        __slots__ = ("offset", "target", "rotation", "zoom")

        def __init__(
            self,
            offset: Vector2 | None = None,
            target: Vector2 | None = None,
            rotation: float = 0.0,
            zoom: float = 1.0,
        ) -> None:
            self.offset = offset if offset is not None else Vector2()
            self.target = target if target is not None else Vector2()
            self.rotation = float(rotation)
            self.zoom = float(zoom)

    class Texture:
        __slots__ = ("id", "width", "height", "mipmaps", "format", "texture")

        def __init__(self, *, texture_id: int = 0, width: int = 0, height: int = 0) -> None:
            self.id = int(texture_id)
            self.width = int(width)
            self.height = int(height)
            self.mipmaps = 1
            self.format = 0
            self.texture = self

    class Image:
        __slots__ = ("width", "height", "mipmaps", "format", "_pixels")

        def __init__(self, width: int = 0, height: int = 0, pixels: list[Color] | None = None) -> None:
            self.width = int(width)
            self.height = int(height)
            self.mipmaps = 1
            self.format = 7
            self._pixels = list(pixels) if pixels is not None else [Color(0, 0, 0, 0) for _ in range(max(0, width * height))]

    class _FFI:
        def new(self, cdecl: str, init: Any = None) -> list[Any]:
            del cdecl
            return [init]

    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def _noop(*args: Any, **kwargs: Any) -> Any:
        return None

    def _false(*args: Any, **kwargs: Any) -> bool:
        return False

    def _zero(*args: Any, **kwargs: Any) -> int:
        return 0

    def _vector2(*args: Any, **kwargs: Any) -> Vector2:
        return Vector2()

    def _color_from_any(value: Any) -> Color:
        if isinstance(value, Color):
            return Color(value.r, value.g, value.b, value.a)
        if isinstance(value, (list, tuple)):
            items = list(value) + [255, 255, 255, 255]
            return Color(items[0], items[1], items[2], items[3])
        return Color(0, 0, 0, 255)

    def _image_pixels(image: Image) -> list[Color]:
        if not isinstance(image, Image):
            raise TypeError("expected Image")
        if len(image._pixels) != max(0, image.width * image.height):
            image._pixels = [Color(0, 0, 0, 0) for _ in range(max(0, image.width * image.height))]
        return image._pixels

    def gen_image_color(width: int, height: int, color: Any) -> Image:
        fill = _color_from_any(color)
        return Image(int(width), int(height), [fill for _ in range(max(0, int(width) * int(height)))])

    def image_draw_rectangle(image: Image, x: int, y: int, width: int, height: int, color: Any) -> None:
        pixels = _image_pixels(image)
        fill = _color_from_any(color)
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(image.width, x0 + max(0, int(width)))
        y1 = min(image.height, y0 + max(0, int(height)))
        for py in range(y0, y1):
            row = py * image.width
            for px in range(x0, x1):
                pixels[row + px] = fill

    def _encode_png_rgba(width: int, height: int, pixels: list[Color]) -> bytes:
        rows = bytearray()
        for py in range(height):
            rows.append(0)
            row_offset = py * width
            for px in range(width):
                color = pixels[row_offset + px] if row_offset + px < len(pixels) else Color(0, 0, 0, 0)
                rows.extend(bytes((color.r & 0xFF, color.g & 0xFF, color.b & 0xFF, color.a & 0xFF)))

        def chunk(name: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return (
            PNG_SIGNATURE
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
            + chunk(b"IEND", b"")
        )

    def export_image(image: Image, path: str) -> bool:
        if not isinstance(image, Image) or image.width <= 0 or image.height <= 0:
            return False
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_encode_png_rgba(image.width, image.height, _image_pixels(image)))
        return True

    def _decode_png_rgba(data: bytes) -> Image:
        if not data.startswith(PNG_SIGNATURE):
            return Image()
        position = len(PNG_SIGNATURE)
        width = height = 0
        color_type = 6
        bit_depth = 8
        compressed = bytearray()
        while position + 8 <= len(data):
            length = struct.unpack(">I", data[position : position + 4])[0]
            position += 4
            chunk_type = data[position : position + 4]
            position += 4
            payload = data[position : position + length]
            position += length
            position += 4
            if chunk_type == b"IHDR":
                width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload)
            elif chunk_type == b"IDAT":
                compressed.extend(payload)
            elif chunk_type == b"IEND":
                break
        if width <= 0 or height <= 0 or bit_depth != 8:
            return Image()
        try:
            raw = zlib.decompress(bytes(compressed))
        except Exception:
            return Image()
        if color_type not in {0, 2, 4, 6}:
            return Image()

        def channels() -> int:
            return {0: 1, 2: 3, 4: 2, 6: 4}[color_type]

        def unfilter(filter_type: int, row: bytearray, prev: bytearray, bpp: int) -> bytearray:
            if filter_type == 0:
                return row
            result = bytearray(len(row))
            if filter_type == 1:
                for i, value in enumerate(row):
                    left = result[i - bpp] if i >= bpp else 0
                    result[i] = (value + left) & 0xFF
                return result
            if filter_type == 2:
                for i, value in enumerate(row):
                    up = prev[i] if i < len(prev) else 0
                    result[i] = (value + up) & 0xFF
                return result
            if filter_type == 3:
                for i, value in enumerate(row):
                    left = result[i - bpp] if i >= bpp else 0
                    up = prev[i] if i < len(prev) else 0
                    result[i] = (value + ((left + up) // 2)) & 0xFF
                return result
            if filter_type == 4:
                def paeth(a: int, b: int, c: int) -> int:
                    p = a + b - c
                    pa = abs(p - a)
                    pb = abs(p - b)
                    pc = abs(p - c)
                    if pa <= pb and pa <= pc:
                        return a
                    if pb <= pc:
                        return b
                    return c

                for i, value in enumerate(row):
                    left = result[i - bpp] if i >= bpp else 0
                    up = prev[i] if i < len(prev) else 0
                    up_left = prev[i - bpp] if i >= bpp and i - bpp < len(prev) else 0
                    result[i] = (value + paeth(left, up, up_left)) & 0xFF
                return result
            return row

        bpp = channels()
        stride = width * bpp
        expected = (stride + 1) * height
        if len(raw) < expected:
            return Image()
        pixels: list[Color] = []
        cursor = 0
        previous_row = bytearray(stride)
        for _ in range(height):
            filter_type = raw[cursor]
            cursor += 1
            row = bytearray(raw[cursor : cursor + stride])
            cursor += stride
            row = unfilter(filter_type, row, previous_row, bpp)
            previous_row = row
            for offset in range(0, stride, bpp):
                if color_type == 6:
                    pixels.append(Color(row[offset], row[offset + 1], row[offset + 2], row[offset + 3]))
                elif color_type == 2:
                    pixels.append(Color(row[offset], row[offset + 1], row[offset + 2], 255))
                elif color_type == 4:
                    gray = row[offset]
                    pixels.append(Color(gray, gray, gray, row[offset + 1]))
                else:
                    gray = row[offset]
                    pixels.append(Color(gray, gray, gray, 255))
        return Image(width, height, pixels)

    def load_image(path: str) -> Image:
        try:
            return _decode_png_rgba(Path(path).read_bytes())
        except Exception:
            return Image()

    def is_image_valid(image: Any) -> bool:
        return isinstance(image, Image) and image.width > 0 and image.height > 0

    def load_image_colors(image: Image) -> list[Color]:
        if not is_image_valid(image):
            return []
        return [_color_from_any(color) for color in _image_pixels(image)]

    def unload_image_colors(colors: Any) -> None:
        del colors

    def unload_image(image: Any) -> None:
        del image

    def load_texture(path: str) -> Texture:
        image = load_image(path)
        return Texture(texture_id=1 if is_image_valid(image) else 0, width=image.width, height=image.height)

    def load_texture_from_image(image: Image) -> Texture:
        return Texture(texture_id=1 if is_image_valid(image) else 0, width=image.width, height=image.height)

    def load_render_texture(width: int, height: int) -> Texture:
        return Texture(texture_id=1, width=int(width), height=int(height))

    def load_image_from_texture(texture: Any) -> Image:
        return Image(int(getattr(texture, "width", 0)), int(getattr(texture, "height", 0)))

    def image_flip_vertical(image: Any) -> Any:
        return image

    def unload_texture(texture: Any) -> None:
        del texture

    def unload_render_texture(texture: Any) -> None:
        del texture

    def measure_text_ex(*args: Any, **kwargs: Any) -> Vector2:
        text = ""
        font_size = 16.0
        if len(args) >= 2:
            text = str(args[1])
        if len(args) >= 3:
            font_size = float(args[2])
        text = str(kwargs.get("text", text))
        font_size = float(kwargs.get("font_size", font_size))
        return Vector2(max(0.0, len(text) * font_size * 0.5), font_size)

    def check_collision_point_rec(point: Any, rect: Any) -> bool:
        px = float(getattr(point, "x", 0.0))
        py = float(getattr(point, "y", 0.0))
        rx = float(getattr(rect, "x", 0.0))
        ry = float(getattr(rect, "y", 0.0))
        rw = float(getattr(rect, "width", 0.0))
        rh = float(getattr(rect, "height", 0.0))
        return rx <= px <= rx + rw and ry <= py <= ry + rh

    def gui_toggle(*args: Any, **kwargs: Any) -> bool:
        return bool(kwargs.get("state", False))

    def gui_text_box(*args: Any, **kwargs: Any) -> bool:
        return False

    def gui_text_box_multi(*args: Any, **kwargs: Any) -> bool:
        return False

    def get_mouse_position() -> Vector2:
        return Vector2()

    def get_mouse_wheel_move() -> float:
        return 0.0

    def is_window_ready() -> bool:
        return False

    def is_window_fullscreen() -> bool:
        return False

    def get_current_monitor() -> int:
        return 0

    def get_monitor_width(monitor: int) -> int:
        del monitor
        return 800

    def get_monitor_height(monitor: int) -> int:
        del monitor
        return 600

    def get_screen_width() -> int:
        return 800

    def get_screen_height() -> int:
        return 600

    def get_render_width() -> int:
        return 800

    def get_render_height() -> int:
        return 600

    def get_fps() -> int:
        return 60

    def get_time() -> float:
        return time.time()

    def get_screen_to_world_2d(position: Any, camera: Any) -> Vector2:
        px = float(getattr(position, "x", 0.0))
        py = float(getattr(position, "y", 0.0))
        offset = getattr(camera, "offset", Vector2())
        target = getattr(camera, "target", Vector2())
        zoom = float(getattr(camera, "zoom", 1.0) or 1.0)
        if zoom == 0:
            zoom = 1.0
        return Vector2(
            (px - float(getattr(offset, "x", 0.0))) / zoom + float(getattr(target, "x", 0.0)),
            (py - float(getattr(offset, "y", 0.0))) / zoom + float(getattr(target, "y", 0.0)),
        )

    def get_glyph_index(*args: Any, **kwargs: Any) -> int:
        return 0

    def get_codepoint(*args: Any, **kwargs: Any) -> int:
        return 0

    def get_codepoints(text: str) -> list[int]:
        return [ord(char) for char in text]

    def text_length(text: str) -> int:
        return len(text)

    def begin_mode_2d(*args: Any, **kwargs: Any) -> None:
        return None

    def end_mode_2d(*args: Any, **kwargs: Any) -> None:
        return None

    def begin_texture_mode(*args: Any, **kwargs: Any) -> None:
        return None

    def end_texture_mode(*args: Any, **kwargs: Any) -> None:
        return None

    def begin_drawing(*args: Any, **kwargs: Any) -> None:
        return None

    def end_drawing(*args: Any, **kwargs: Any) -> None:
        return None

    def clear_background(*args: Any, **kwargs: Any) -> None:
        return None

    def set_window_size(*args: Any, **kwargs: Any) -> None:
        return None

    def toggle_fullscreen(*args: Any, **kwargs: Any) -> None:
        return None

    def close_window(*args: Any, **kwargs: Any) -> None:
        return None

    def init_window(*args: Any, **kwargs: Any) -> None:
        return None

    def set_config_flags(*args: Any, **kwargs: Any) -> None:
        return None

    def set_target_fps(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_text(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_line(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_line_ex(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_circle(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_circle_lines(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_rectangle(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_rectangle_rec(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_rectangle_lines(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_rectangle_lines_ex(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_triangle(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_texture(*args: Any, **kwargs: Any) -> None:
        return None

    def draw_texture_pro(*args: Any, **kwargs: Any) -> None:
        return None

    def begin_scissor_mode(*args: Any, **kwargs: Any) -> None:
        return None

    def end_scissor_mode(*args: Any, **kwargs: Any) -> None:
        return None

    def is_mouse_button_pressed(*args: Any, **kwargs: Any) -> bool:
        return False

    def is_mouse_button_down(*args: Any, **kwargs: Any) -> bool:
        return False

    def is_mouse_button_released(*args: Any, **kwargs: Any) -> bool:
        return False

    def is_key_pressed(*args: Any, **kwargs: Any) -> bool:
        return False

    def is_key_down(*args: Any, **kwargs: Any) -> bool:
        return False

    def gui_button(*args: Any, **kwargs: Any) -> bool:
        return False

    def get_window_position() -> Vector2:
        return Vector2()

    def load_font_default() -> object:
        return object()

    for name, value in {
        "Vector2": Vector2,
        "Rectangle": Rectangle,
        "Color": Color,
        "Camera2D": Camera2D,
        "Texture": Texture,
        "Image": Image,
        "ffi": _FFI(),
        "gen_image_color": gen_image_color,
        "image_draw_rectangle": image_draw_rectangle,
        "export_image": export_image,
        "load_image": load_image,
        "load_render_texture": load_render_texture,
        "is_image_valid": is_image_valid,
        "load_image_colors": load_image_colors,
        "unload_image_colors": unload_image_colors,
        "unload_image": unload_image,
        "load_texture": load_texture,
        "load_texture_from_image": load_texture_from_image,
        "get_screen_to_world_2d": get_screen_to_world_2d,
        "unload_texture": unload_texture,
        "measure_text_ex": measure_text_ex,
        "check_collision_point_rec": check_collision_point_rec,
        "gui_toggle": gui_toggle,
        "gui_text_box": gui_text_box,
        "gui_text_box_multi": gui_text_box_multi,
        "get_mouse_position": get_mouse_position,
        "get_mouse_wheel_move": get_mouse_wheel_move,
        "is_window_ready": is_window_ready,
        "is_window_fullscreen": is_window_fullscreen,
        "get_current_monitor": get_current_monitor,
        "get_monitor_width": get_monitor_width,
        "get_monitor_height": get_monitor_height,
        "get_screen_width": get_screen_width,
        "get_screen_height": get_screen_height,
        "get_render_width": get_render_width,
        "get_render_height": get_render_height,
        "get_fps": get_fps,
        "get_time": get_time,
        "get_glyph_index": get_glyph_index,
        "get_codepoint": get_codepoint,
        "get_codepoints": get_codepoints,
        "text_length": text_length,
        "begin_mode_2d": begin_mode_2d,
        "end_mode_2d": end_mode_2d,
        "begin_texture_mode": begin_texture_mode,
        "end_texture_mode": end_texture_mode,
        "begin_drawing": begin_drawing,
        "end_drawing": end_drawing,
        "clear_background": clear_background,
        "set_window_size": set_window_size,
        "set_config_flags": set_config_flags,
        "init_window": init_window,
        "toggle_fullscreen": toggle_fullscreen,
        "close_window": close_window,
        "set_target_fps": set_target_fps,
        "draw_text": draw_text,
        "draw_line": draw_line,
        "draw_line_ex": draw_line_ex,
        "draw_circle": draw_circle,
        "draw_circle_lines": draw_circle_lines,
        "draw_rectangle": draw_rectangle,
        "draw_rectangle_rec": draw_rectangle_rec,
        "draw_rectangle_lines": draw_rectangle_lines,
        "draw_rectangle_lines_ex": draw_rectangle_lines_ex,
        "draw_triangle": draw_triangle,
        "draw_texture": draw_texture,
        "draw_texture_pro": draw_texture_pro,
        "begin_scissor_mode": begin_scissor_mode,
        "end_scissor_mode": end_scissor_mode,
        "is_mouse_button_pressed": is_mouse_button_pressed,
        "is_mouse_button_down": is_mouse_button_down,
        "is_mouse_button_released": is_mouse_button_released,
        "is_key_pressed": is_key_pressed,
        "is_key_down": is_key_down,
        "gui_button": gui_button,
        "get_window_position": get_window_position,
        "load_font_default": load_font_default,
        "load_image_from_texture": load_image_from_texture,
        "image_flip_vertical": image_flip_vertical,
        "unload_render_texture": unload_render_texture,
        "WHITE": Color(255, 255, 255, 255),
        "BLACK": Color(0, 0, 0, 255),
        "BLANK": Color(0, 0, 0, 0),
        "RED": Color(230, 41, 55, 255),
        "GREEN": Color(0, 228, 48, 255),
        "BLUE": Color(0, 121, 241, 255),
        "YELLOW": Color(253, 249, 0, 255),
        "ORANGE": Color(255, 161, 0, 255),
        "SKYBLUE": Color(102, 191, 255, 255),
        "GRAY": Color(130, 130, 130, 255),
        "LIGHTGRAY": Color(200, 200, 200, 255),
        "DARKGRAY": Color(80, 80, 80, 255),
        "PINK": Color(255, 109, 194, 255),
        "PURPLE": Color(200, 122, 255, 255),
        "VIOLET": Color(135, 60, 190, 255),
        "MAGENTA": Color(255, 0, 255, 255),
        "GOLD": Color(255, 203, 0, 255),
        "LIME": Color(0, 158, 47, 255),
        "BROWN": Color(127, 106, 79, 255),
        "DARKBLUE": Color(0, 82, 172, 255),
        "MAROON": Color(190, 33, 55, 255),
        "DARKPURPLE": Color(112, 31, 126, 255),
        "BEIGE": Color(211, 176, 131, 255),
        "LAVENDER": Color(230, 230, 250, 255),
        "RAYWHITE": Color(245, 245, 245, 255),
        "MOUSE_BUTTON_LEFT": 0,
        "MOUSE_BUTTON_RIGHT": 1,
        "MOUSE_BUTTON_MIDDLE": 2,
    }.items():
        setattr(module, name, value)

    def __getattr__(name: str) -> Any:
        if name in module.__dict__:
            return module.__dict__[name]
        if name.startswith(("Vector", "Rectangle", "Color", "Camera", "Texture", "Image")):
            raise AttributeError(name)
        if name.startswith(("KEY_", "MOUSE_", "GAMEPAD_", "FLAG_", "BLEND_", "GESTURE_")) or name.isupper():
            return 0
        if name.startswith(("is_", "get_", "set_", "load_", "unload_", "draw_", "begin_", "end_", "gui_", "check_", "export_", "image_", "measure_", "text_", "toggle_", "close_", "clear_", "play_", "stop_", "pause_", "resume_", "init_", "update_")):
            return _noop
        return _noop

    def __dir__() -> list[str]:
        return sorted(module.__dict__)

    module.__getattr__ = __getattr__  # type: ignore[attr-defined]
    module.__dir__ = __dir__  # type: ignore[attr-defined]
    sys.modules["pyray"] = module
