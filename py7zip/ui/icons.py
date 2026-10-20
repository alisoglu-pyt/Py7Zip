"""Small dependency-free icon renderer with a classic Explorer palette.

Icons are drawn with simple primitives into an RGBA buffer, supersampled for
smooth edges and encoded as PNG for use in ``tk.PhotoImage``.  Two flavours
are produced:

* ``colored`` - classic 7-Zip/Explorer style yellow/blue/green/red icons
* ``normal`` / ``muted`` / ``accent`` / ``danger`` - monochrome icons that
  follow the active theme (used for navigation and settings).
"""

from __future__ import annotations

import base64
import math
import struct
import tkinter as tk
import zlib

BASE = 18

# Classic Windows icon palette.
YELLOW = (242, 183, 5)
YELLOW_DARK = (166, 117, 0)
BLUE = (10, 111, 194)
BLUE_DARK = (8, 74, 130)
GREEN = (22, 138, 22)
GREEN_DARK = (12, 92, 12)
RED = (196, 43, 28)
RED_DARK = (135, 25, 16)
GRAY = (96, 96, 96)
GRAY_DARK = (64, 64, 64)
WHITE = (255, 255, 255)


class _Canvas:
    def __init__(self, size: int = 16) -> None:
        self.output = size
        self.supersample = 3
        self.size = size * self.supersample
        self.factor = self.size / BASE
        self.buffer = bytearray(self.size * self.size * 4)

    # -- low level ---------------------------------------------------
    def _blend_px(self, x: int, y: int, color, alpha: float) -> None:
        if not (0 <= x < self.size and 0 <= y < self.size):
            return
        index = (y * self.size + x) * 4
        inverse = 1.0 - alpha
        self.buffer[index] = int(self.buffer[index] * inverse + color[0] * alpha)
        self.buffer[index + 1] = int(
            self.buffer[index + 1] * inverse + color[1] * alpha
        )
        self.buffer[index + 2] = int(
            self.buffer[index + 2] * inverse + color[2] * alpha
        )
        self.buffer[index + 3] = min(
            255, int(self.buffer[index + 3] + 255 * alpha)
        )

    def _disc_px(self, cx: float, cy: float, radius: float, color,
                 alpha: float = 1.0) -> None:
        r = max(radius, 0.5)
        x0 = max(0, int(math.floor(cx - r)))
        x1 = min(self.size - 1, int(math.ceil(cx + r)))
        y0 = max(0, int(math.floor(cy - r)))
        y1 = min(self.size - 1, int(math.ceil(cy + r)))
        r2 = r * r
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r2:
                    self._blend_px(x, y, color, alpha)

    # -- public drawing (BASE coordinates) ---------------------------
    def disc(self, cx: float, cy: float, radius: float, color,
             alpha: float = 1.0) -> None:
        self._disc_px(cx * self.factor, cy * self.factor,
                      radius * self.factor, color, alpha)

    def line(self, x0: float, y0: float, x1: float, y1: float, color,
             width: float = 2.0, alpha: float = 1.0) -> None:
        ax, ay = x0 * self.factor, y0 * self.factor
        bx, by = x1 * self.factor, y1 * self.factor
        distance = math.hypot(bx - ax, by - ay)
        steps = max(1, int(distance * 1.7))
        radius = (width * self.factor) / 2.0
        for step in range(steps + 1):
            t = step / steps
            self._disc_px(ax + (bx - ax) * t, ay + (by - ay) * t,
                          radius, color, alpha)

    def polyline(self, points, color, width: float = 2.0,
                 closed: bool = False) -> None:
        for index in range(len(points) - 1):
            self.line(*points[index], *points[index + 1], color, width)
        if closed and len(points) > 2:
            self.line(*points[-1], *points[0], color, width)

    def rect(self, x0: float, y0: float, x1: float, y1: float, color,
             width: float = 2.0, fill: bool = False) -> None:
        if fill:
            self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color)
        else:
            self.polyline(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                color, width, closed=True,
            )

    def polygon(self, points, color, alpha: float = 1.0) -> None:
        xs = [p[0] * self.factor for p in points]
        ys = [p[1] * self.factor for p in points]
        x0, x1 = int(min(xs)), int(max(xs))
        y0, y1 = int(min(ys)), int(max(ys))
        for y in range(max(0, y0), min(self.size - 1, y1) + 1):
            for x in range(max(0, x0), min(self.size - 1, x1) + 1):
                if _point_in_polygon(x + 0.5, y + 0.5, xs, ys):
                    self._blend_px(x, y, color, alpha)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, color,
                width: float = 2.0, start: float = 0.0,
                end: float = 360.0) -> None:
        steps = 180
        prev = None
        for index in range(steps + 1):
            angle = math.radians(start + (end - start) * index / steps)
            point = (cx + math.cos(angle) * rx, cy + math.sin(angle) * ry)
            if prev is not None:
                self.line(*prev, *point, color, width)
            prev = point

    # -- output ------------------------------------------------------
    def png(self) -> bytes:
        out = bytearray(self.output * self.output * 4)
        ss = self.supersample
        for y in range(self.output):
            for x in range(self.output):
                r = g = b = a = 0
                for sy in range(ss):
                    for sx in range(ss):
                        index = (
                            (y * ss + sy) * self.size + (x * ss + sx)
                        ) * 4
                        r += self.buffer[index]
                        g += self.buffer[index + 1]
                        b += self.buffer[index + 2]
                        a += self.buffer[index + 3]
                count = ss * ss
                index = (y * self.output + x) * 4
                out[index:index + 4] = bytes(
                    (r // count, g // count, b // count, a // count)
                )

        raw = b"".join(
            b"\x00" + bytes(
                out[row * self.output * 4:(row + 1) * self.output * 4]
            )
            for row in range(self.output)
        )

        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        header = struct.pack(
            ">IIBBBBB", self.output, self.output, 8, 6, 0, 0, 0
        )
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def _point_in_polygon(x: float, y: float, xs, ys) -> bool:
    inside = False
    count = len(xs)
    j = count - 1
    for i in range(count):
        xi, yi = xs[i], ys[i]
        xj, yj = xs[j], ys[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        ):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Monochrome icons (navigation, settings)
# ---------------------------------------------------------------------------
def _draw(name: str, canvas: _Canvas, color) -> None:
    width = 1.9
    if name == "back":
        canvas.polyline([(11, 4), (5, 9), (11, 14)], color, width)
    elif name == "forward":
        canvas.polyline([(7, 4), (13, 9), (7, 14)], color, width)
    elif name == "up":
        canvas.polyline([(4, 11.5), (9, 5.5), (14, 11.5)], color, width)
    elif name == "refresh":
        canvas.ellipse(9, 9, 5.6, 5.6, color, width, start=35, end=315)
        canvas.polygon([(14.5, 3.5), (15.5, 8.5), (10.8, 7.0)], color)
    elif name == "preview":
        canvas.ellipse(9, 9, 6.4, 4.0, color, width)
        canvas.disc(9, 9, 1.9, color)
    elif name == "settings":
        for y, knob in ((5.2, 7.0), (9.0, 12.0), (12.8, 6.5)):
            canvas.line(3.2, y, 14.8, y, color, width)
            canvas.disc(knob, y, 1.9, color)
    elif name == "search":
        canvas.ellipse(8.0, 8.0, 4.4, 4.4, color, width)
        canvas.line(11.3, 11.3, 15.0, 15.0, color, 2.1)
    elif name == "close":
        canvas.line(5.0, 5.0, 13.0, 13.0, color, width)
        canvas.line(13.0, 5.0, 5.0, 13.0, color, width)
    elif name == "down":
        canvas.polyline([(4.5, 7), (9, 11.5), (13.5, 7)], color, width)


# ---------------------------------------------------------------------------
# Classic colored icons
# ---------------------------------------------------------------------------
def _draw_colored(name: str, c: _Canvas) -> None:
    if name == "open":
        c.polygon(
            [(2.4, 7.0), (6.4, 7.0), (7.7, 4.5), (15.6, 4.5),
             (15.6, 14.6), (2.4, 14.6)],
            YELLOW,
        )
        c.polyline(
            [(2.4, 7.0), (6.4, 7.0), (7.7, 4.5), (15.6, 4.5),
             (15.6, 14.6), (2.4, 14.6)],
            YELLOW_DARK, 1.4, closed=True,
        )
        c.line(3.2, 8.4, 14.8, 8.4, YELLOW_DARK, 0.9)
    elif name == "new":
        c.rect(2.8, 3.2, 15.2, 15.0, BLUE_DARK, 1.5, fill=True)
        c.polygon(
            [(4.0, 4.4), (14.0, 4.4), (14.0, 13.8), (4.0, 13.8)], BLUE
        )
        c.line(9, 6.2, 9, 12.0, WHITE, 0.0 + 2.2)
        c.line(6.1, 9.1, 11.9, 9.1, WHITE, 2.2)
    elif name == "extract":
        c.polyline(
            [(3.2, 10.6), (3.2, 14.7), (14.8, 14.7), (14.8, 10.6)],
            GRAY_DARK, 2.0,
        )
        c.line(9, 12.8, 9, 4.2, BLUE_DARK, 3.0)
        c.line(9, 12.6, 9, 4.6, BLUE, 1.9)
        c.polygon([(9, 3.0), (13.6, 8.0), (4.4, 8.0)], BLUE)
    elif name == "add":
        c.line(9, 3.4, 9, 14.6, GREEN_DARK, 3.4)
        c.line(3.4, 9, 14.6, 9, GREEN_DARK, 3.4)
        c.line(9, 4.0, 9, 14.0, GREEN, 2.2)
        c.line(4.0, 9, 14.0, 9, GREEN, 2.2)
    elif name == "delete":
        c.line(4.0, 5.2, 14.0, 5.2, RED_DARK, 2.2)
        c.line(7.0, 3.0, 11.0, 3.0, RED_DARK, 2.0)
        c.polyline(
            [(5.2, 5.2), (6.0, 15.0), (12.0, 15.0), (12.8, 5.2)],
            RED, 1.8,
        )
        c.line(8.0, 8.0, 8.0, 12.2, RED, 1.2)
        c.line(10.0, 8.0, 10.0, 12.2, RED, 1.2)
    elif name == "test":
        c.polyline([(3.6, 9.2), (7.6, 13.2), (14.4, 3.8)], GREEN_DARK, 3.2)
        c.polyline([(3.8, 9.0), (7.6, 12.8), (14.2, 4.2)], GREEN, 1.9)
    elif name == "info":
        c.disc(9, 9, 6.6, BLUE_DARK)
        c.disc(9, 9, 5.7, BLUE)
        c.disc(9, 5.6, 1.0, WHITE)
        c.line(9, 8.0, 9, 12.8, WHITE, 1.9)
    elif name == "archive":
        c.rect(2.8, 4.2, 15.2, 15.0, YELLOW_DARK, 1.5, fill=True)
        c.polygon(
            [(4.0, 5.4), (14.0, 5.4), (14.0, 13.8), (4.0, 13.8)], YELLOW
        )
        c.line(3.2, 7.6, 14.8, 7.6, YELLOW_DARK, 1.1)
        c.rect(7.2, 9.6, 10.8, 11.8, YELLOW_DARK, 1.0, fill=True)
    elif name == "preview":
        c.ellipse(9, 9, 6.6, 4.2, BLUE_DARK, 1.8)
        c.ellipse(9, 9, 6.6, 4.2, BLUE, 1.0)
        c.disc(9, 9, 2.0, BLUE_DARK)
        c.disc(9, 9, 1.3, WHITE)
    elif name == "settings":
        for y, knob in ((5.2, 7.0), (9.0, 12.0), (12.8, 6.5)):
            c.line(3.2, y, 14.8, y, GRAY, 1.8)
            c.disc(knob, y, 1.9, GRAY_DARK)
    else:
        _draw(name, c, GRAY)


def render_icon(name: str, color_hex: str = "#000000",
                colored: bool = False, size: int = 16) -> bytes:
    canvas = _Canvas(size)
    if colored:
        _draw_colored(name, canvas)
    else:
        value = color_hex.lstrip("#")
        color = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
        _draw(name, canvas, color)
    return canvas.png()


class IconSet:
    """Caches ``tk.PhotoImage`` icons for a palette."""

    def __init__(self, master: tk.Misc, colors: dict[str, str]) -> None:
        self.master = master
        self.colors = dict(colors)
        self._cache: dict[tuple[str, str, int], tk.PhotoImage] = {}

    def get(self, name: str, variant: str = "normal",
            size: int = 16) -> tk.PhotoImage:
        key = (name, variant, size)
        image = self._cache.get(key)
        if image is None:
            if variant == "colored":
                png = render_icon(name, colored=True, size=size)
            else:
                color = self.colors.get(variant) or self.colors.get(
                    "normal", "#000000"
                )
                png = render_icon(name, color_hex=color, size=size)
            data = base64.b64encode(png).decode("ascii")
            image = tk.PhotoImage(master=self.master, data=data)
            self._cache[key] = image
        return image
