#!/usr/bin/env python3
"""THE WORLD TODAY - the news of Monday 23 November 2026 in one image.

A fresh, self-contained renderer: a stroke-vector letterform set drawn
with thick polylines, data-driven pictogram emblems, and a small PNG
writer on top of zlib. Python 3 standard library only, no network,
no randomness - two runs write identical bytes.

Layout (1024 x 1024, newsprint page):
  masthead band with the paper name and the date in large type
  lead panel: COP31 collapses in Antalya
  four story cards: Poland / FIFA / markets / killer robots
  IN BRIEF strip: BepiColombo, Marquez, Indonesia factory fire
  footer restating the date
"""

import os
import struct
import sys
import zlib
from math import cos, pi, sin

W = 1024
H = 1024

PAPER = (246, 241, 229)
CARD = (255, 255, 255)
INK = (25, 25, 25)
NAVY = (20, 38, 74)
RED = (166, 30, 30)
GOLD = (232, 197, 71)
BLUE = (31, 78, 121)
GREY = (122, 117, 104)
RULE = (198, 190, 172)
WHITE = (255, 255, 255)
ORANGE = (214, 106, 24)


class Sheet:
    """An RGB canvas backed by one flat bytearray."""

    def __init__(self, w, h, colour):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, colour)

    def put(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = colour[0]
            self.px[i + 1] = colour[1]
            self.px[i + 2] = colour[2]

    def fill_rect(self, x, y, w, h, colour):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i] = colour[0]
                self.px[i + 1] = colour[1]
                self.px[i + 2] = colour[2]

    def rect_outline(self, x, y, w, h, colour, t=2):
        self.fill_rect(x, y, w, t, colour)
        self.fill_rect(x, y + h - t, w, t, colour)
        self.fill_rect(x, y, t, h, colour)
        self.fill_rect(x + w - t, y, t, h, colour)

    def _brush(self, x, y, w, colour):
        r = w // 2
        for yy in range(y - r, y + r + 1):
            for xx in range(x - r, x + r + 1):
                self.put(xx, yy, colour)

    def line(self, x0, y0, x1, y1, colour, w=2):
        """Bresenham line with a square brush; a zero-length line is a dot."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            self._brush(x, y, w, colour)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def polyline(self, points, colour, w=2, closed=False):
        pts = list(points)
        if closed and len(pts) > 1:
            pts = pts + [pts[0]]
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], colour, w)

    def disc(self, cx, cy, r, colour):
        """Filled circle."""
        for yy in range(cy - r, cy + r + 1):
            d = r * r - (yy - cy) * (yy - cy)
            if d < 0:
                continue
            dx = int(d ** 0.5)
            for xx in range(cx - dx, cx + dx + 1):
                self.put(xx, yy, colour)

    def ring(self, cx, cy, r, colour, w=3):
        steps = max(24, int(2 * pi * r))
        pts = []
        for i in range(steps + 1):
            a = 2 * pi * i / steps
            pts.append((int(round(cx + r * cos(a))),
                        int(round(cy + r * sin(a)))))
        self.polyline(pts, colour, w, closed=True)

    def ellipse(self, cx, cy, rx, ry, colour, w=3):
        steps = max(24, int(2 * pi * max(rx, ry)))
        pts = []
        for i in range(steps + 1):
            a = 2 * pi * i / steps
            pts.append((int(round(cx + rx * cos(a))),
                        int(round(cy + ry * sin(a)))))
        self.polyline(pts, colour, w, closed=True)

    def poly_fill(self, points, colour):
        """Scanline fill of a simple polygon."""
        pts = list(points)
        if len(pts) < 3:
            return
        ymin = min(p[1] for p in pts)
        ymax = max(p[1] for p in pts)
        edges = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
        for y in range(ymin, ymax + 1):
            xs = []
            for x0, y0, x1, y1 in edges:
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                for xx in range(int(round(xs[j])), int(round(xs[j + 1])) + 1):
                    self.put(xx, y, colour)


# ---------------------------------------------------------------------------
# Stroke-vector letterforms.
#
# Every glyph is a list of strokes on a 5-wide by 7-tall grid (x 0..4,
# y 0..6, y grows downwards). A stroke is a polyline of grid points.
# All-caps text plus digits and punctuation; a zero-length stroke draws
# a dot. This is a vector font: nothing here is a bitmap mask.
# ---------------------------------------------------------------------------

GLYPHS = {
    "A": [[(0, 6), (2, 0), (4, 6)], [(1, 4), (3, 4)]],
    "B": [[(0, 0), (0, 6)],
          [(0, 0), (3, 0), (4, 1), (3, 2), (0, 2)],
          [(0, 2), (3, 2), (4, 3), (4, 5), (3, 6), (0, 6)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "D": [[(0, 0), (0, 6)],
          [(0, 0), (3, 0), (4, 1), (4, 5), (3, 6), (0, 6)]],
    "E": [[(0, 0), (0, 6)], [(0, 0), (4, 0)],
          [(0, 3), (3, 3)], [(0, 6), (4, 6)]],
    "F": [[(0, 0), (0, 6)], [(0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "G": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6),
           (3, 6), (4, 5), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(1, 0), (3, 0)], [(2, 0), (2, 6)], [(1, 6), (3, 6)]],
    "J": [[(4, 0), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4)]],
    "K": [[(0, 0), (0, 6)], [(3, 0), (0, 3), (4, 6)]],
    "L": [[(0, 0), (0, 6)], [(0, 6), (4, 6)]],
    "M": [[(0, 6), (0, 0), (2, 3), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "O": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6),
           (1, 6), (0, 5), (0, 1), (1, 0)]],
    "P": [[(0, 0), (0, 6)],
          [(0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)]],
    "Q": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6),
           (1, 6), (0, 5), (0, 1), (1, 0)],
          [(3, 4), (4, 6)]],
    "R": [[(0, 0), (0, 6)],
          [(0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)],
          [(2, 3), (4, 6)]],
    "S": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3),
           (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "U": [[(0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)]],
    "V": [[(0, 0), (2, 6), (4, 0)]],
    "W": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "Y": [[(0, 0), (2, 3), (4, 0)], [(2, 3), (2, 6)]],
    "Z": [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    "0": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6),
           (1, 6), (0, 5), (0, 1), (1, 0)]],
    "1": [[(1, 1), (2, 0), (2, 6)], [(0, 6), (4, 6)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (0, 6), (4, 6)]],
    "3": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (2, 3)],
          [(2, 3), (4, 3), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "4": [[(0, 0), (0, 3), (4, 3)], [(3, 0), (3, 6)]],
    "5": [[(4, 0), (0, 0), (0, 2), (3, 2), (4, 3),
           (4, 5), (3, 6), (1, 6), (0, 5)]],
    "6": [[(3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6),
           (4, 5), (4, 3), (3, 2), (1, 2), (0, 3)]],
    "7": [[(0, 0), (4, 0), (2, 6)]],
    "8": [[(1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3),
           (0, 2), (0, 1), (1, 0)],
          [(1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6),
           (0, 5), (0, 4), (1, 3)]],
    "9": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0),
           (1, 0), (0, 1), (0, 3), (1, 4), (3, 4), (4, 3)]],
    ".": [[(2, 5), (2, 5)]],
    ",": [[(2, 5), (2, 6), (1, 6)]],
    ":": [[(2, 1), (2, 1)], [(2, 4), (2, 4)]],
    ";": [[(2, 1), (2, 1)], [(2, 4), (2, 6), (1, 6)]],
    "'": [[(2, 0), (2, 2)]],
    "-": [[(0, 3), (4, 3)]],
    "(": [[(3, 0), (2, 1), (1, 3), (2, 5), (3, 6)]],
    ")": [[(1, 0), (2, 1), (3, 3), (2, 5), (1, 6)]],
    "/": [[(4, 6), (0, 0)]],
    "%": [[(4, 0), (0, 6)],
          [(0, 1), (2, 1), (2, 3), (0, 3), (0, 1)],
          [(2, 3), (4, 3), (4, 5), (2, 5), (2, 3)]],
    "!": [[(2, 0), (2, 4)], [(2, 5), (2, 5)]],
    "?": [[(1, 1), (2, 0), (3, 0), (4, 1), (4, 2), (3, 3), (2, 3)],
          [(2, 5), (2, 5)]],
    "+": [[(0, 3), (4, 3)], [(2, 1), (2, 5)]],
    '"': [[(1, 0), (1, 2)], [(3, 0), (3, 2)]],
    "=": [[(0, 2), (4, 2)], [(0, 4), (4, 4)]],
    " ": [],
}


def _advance(ch, scale):
    """Horizontal advance of one character, in pixels."""
    if ch == " ":
        return 4 * scale
    return 6 * scale


def text_width(text, scale):
    """Pixel width of a string at the given scale."""
    return sum(_advance(ch, scale) for ch in text)


def draw_char(sheet, x, y, ch, scale, colour):
    """Draw one glyph with its top-left corner at (x, y)."""
    strokes = GLYPHS.get(ch)
    if not strokes:
        return
    w = max(2, scale // 2 + 1)
    for stroke in strokes:
        pts = [(x + gx * scale, y + gy * scale) for gx, gy in stroke]
        sheet.polyline(pts, colour, w)


def draw_text(sheet, x, y, text, scale, colour, align="left", width=0):
    """Draw a single line of text. align=center centres it in width."""
    if align == "center":
        x = x + (width - text_width(text, scale)) // 2
    cx = x
    for ch in text:
        draw_char(sheet, cx, y, ch, scale, colour)
        cx += _advance(ch, scale)


def wrap_text(text, scale, max_w):
    """Greedy word wrap; returns a list of lines that fit max_w pixels."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# PNG writer: filter-0 scanlines, zlib level 9, IHDR/IDAT/IEND chunks.
# ---------------------------------------------------------------------------

def _png_chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png(sheet):
    raw = bytearray()
    stride = sheet.w * 3
    for y in range(sheet.h):
        raw.append(0)
        raw += sheet.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", sheet.w, sheet.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _png_chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# Pictogram emblems.
#
# Each emblem is a list of shapes in a 100 x 100 box. Shape kinds:
#   ("ring", cx, cy, r, w, key)      circle outline
#   ("ellipse", cx, cy, rx, ry, w, key)
#   ("disc", cx, cy, r, key)         filled circle
#   ("line", x1, y1, x2, y2, w, key)
#   ("rect", x, y, w, h, key, fill)  rectangle, filled or outline
#   ("poly", [(x, y), ...], fill, w, key)
# key "m" is the emblem's main colour, "a" its accent colour.
# ---------------------------------------------------------------------------

ICONS = {
    "globe": [
        ("ring", 50, 50, 42, 4, "m"),
        ("ellipse", 50, 50, 42, 15, 3, "m"),
        ("ellipse", 50, 50, 15, 42, 3, "m"),
        ("line", 8, 50, 92, 50, 3, "m"),
    ],
    "missile": [
        ("line", 18, 82, 76, 24, 9, "m"),
        ("poly", [(76, 24), (62, 22), (78, 38)], True, 0, "m"),
        ("poly", [(18, 82), (6, 94), (26, 90)], True, 0, "a"),
        ("poly", [(30, 70), (18, 82), (34, 86)], True, 0, "m"),
    ],
    "football": [
        ("ring", 50, 50, 42, 4, "m"),
        ("poly", [(50, 34), (64, 46), (59, 64), (41, 64), (36, 46)],
         True, 0, "m"),
        ("line", 50, 34, 50, 12, 3, "m"),
        ("line", 64, 46, 84, 38, 3, "m"),
        ("line", 59, 64, 72, 80, 3, "m"),
        ("line", 41, 64, 28, 80, 3, "m"),
        ("line", 36, 46, 16, 38, 3, "m"),
    ],
    "chart": [
        ("line", 14, 86, 14, 14, 4, "m"),
        ("line", 14, 86, 88, 86, 4, "m"),
        ("poly", [(18, 28), (36, 38), (54, 32), (82, 72)], False, 5, "a"),
        ("poly", [(82, 72), (70, 70), (80, 58)], True, 0, "a"),
    ],
    "robot": [
        ("rect", 28, 32, 44, 42, "m", False),
        ("line", 50, 32, 50, 14, 3, "m"),
        ("disc", 50, 12, 4, "a"),
        ("disc", 40, 50, 4, "m"),
        ("disc", 60, 50, 4, "m"),
        ("line", 40, 64, 60, 64, 3, "m"),
    ],
    "planet": [
        ("disc", 50, 52, 28, "m"),
        ("ellipse", 50, 50, 48, 14, 4, "a"),
        ("disc", 84, 26, 6, "a"),
    ],
    "motorcycle": [
        ("ring", 28, 70, 15, 4, "m"),
        ("ring", 72, 70, 15, 4, "m"),
        ("line", 28, 70, 48, 42, 4, "m"),
        ("line", 48, 42, 72, 70, 4, "m"),
        ("line", 48, 42, 60, 30, 4, "m"),
        ("line", 60, 30, 70, 30, 4, "m"),
        ("line", 38, 42, 52, 42, 4, "m"),
    ],
    "flame": [
        ("poly", [(50, 8), (62, 30), (76, 48), (72, 72), (60, 86),
                  (40, 86), (28, 72), (24, 48), (38, 30)], True, 0, "a"),
        ("poly", [(50, 40), (58, 54), (56, 70), (50, 76), (44, 70),
                  (42, 54)], True, 0, "m"),
    ],
}


def draw_icon(sheet, name, x, y, size, main, accent):
    """Draw an emblem scaled into the box (x, y, size, size)."""
    s = size / 100.0
    colours = {"m": main, "a": accent}

    def sx(v):
        return int(round(x + v * s))

    def sy(v):
        return int(round(y + v * s))

    def sw(v):
        return max(1, int(round(v * s)))

    for shape in ICONS[name]:
        kind = shape[0]
        if kind == "ring":
            _, cx, cy, r, w, key = shape
            sheet.ring(sx(cx), sy(cy), sw(r), colours[key], sw(w))
        elif kind == "ellipse":
            _, cx, cy, rx, ry, w, key = shape
            sheet.ellipse(sx(cx), sy(cy), sw(rx), sw(ry),
                          colours[key], sw(w))
        elif kind == "disc":
            _, cx, cy, r, key = shape
            sheet.disc(sx(cx), sy(cy), sw(r), colours[key])
        elif kind == "line":
            _, x1, y1, x2, y2, w, key = shape
            sheet.line(sx(x1), sy(y1), sx(x2), sy(y2),
                       colours[key], sw(w))
        elif kind == "rect":
            _, rx, ry, rw, rh, key, fill = shape
            if fill:
                sheet.fill_rect(sx(rx), sy(ry), sw(rw), sw(rh),
                                colours[key])
            else:
                sheet.rect_outline(sx(rx), sy(ry), sw(rw), sw(rh),
                                   colours[key], sw(3))
        elif kind == "poly":
            _, pts, fill, w, key = shape
            scaled = [(sx(px), sy(py)) for px, py in pts]
            if fill:
                sheet.poly_fill(scaled, colours[key])
            else:
                sheet.polyline(scaled, colours[key], sw(w))


# ---------------------------------------------------------------------------
# The news of Monday 23 November 2026, as reported that day.
# Every item below was checked against live reporting on 23 November 2026:
# COP31 collapsed in Antalya on Sunday and led Monday's papers; Poland's
# prosecutors confirmed the three objects were Russian Kh-101 missiles and
# NATO's council meets on Monday; FIFA's congress votes in Zurich on
# Monday; Taiwan's short-selling ban takes effect on Monday after the
# Taiex fell 17.5% in its worst week since 1991; the Geneva killer-robot
# talks ended on Saturday; BepiColombo entered Mercury orbit on Saturday;
# Marquez clinched his eighth title on Sunday; Indonesia confirmed 24
# dead in the factory fire on Monday as the search resumed.
# ---------------------------------------------------------------------------

MASTHEAD_NAME = "THE WORLD TODAY"
MASTHEAD_DATE = "MONDAY 23 NOVEMBER 2026"

LEAD_KICKER = "CLIMATE - ANTALYA"
LEAD_HEAD = "COP31 COLLAPSES"
LEAD_SUB = "RECORD OVERTIME, NO DEAL"
LEAD_BODY = ("THE LONGEST CLIMATE SUMMIT EVER ENDS WITH NO DEAL. "
             "NEARLY 200 NATIONS REJECT A PACT WITH NO MENTION "
             "OF FOSSIL FUELS.")

CARDS = [
    ("SECURITY - POLAND",
     "RUSSIAN MISSILES IN POLAND",
     "ALL THREE WERE KH-101S. NATO MEETS TODAY.",
     "missile", RED),
    ("SPORT - ZURICH",
     "UK TO HOST THE 2035 WORLD CUP",
     "FIFA VOTES TODAY. FIRST UK WORLD CUP SINCE 1966.",
     "football", BLUE),
    ("MARKETS - TAIPEI",
     "TAIWAN BANS SHORT SELLING",
     "TAIEX FELL 17.5% IN A WEEK. ASIA STEPS IN.",
     "chart", RED),
    ("GENEVA - UNITED NATIONS",
     "KILLER-ROBOT RULES AGREED",
     "RULES DUE BY 2028. NO PROMISE THEY WILL BIND.",
     "robot", BLUE),
]

BRIEFS = [
    ("BEPICOLOMBO AT MERCURY", "AFTER 8 YEARS", "planet", NAVY, GOLD),
    ("MARQUEZ WINS 8TH TITLE", "TIES AGOSTINI", "motorcycle", NAVY, RED),
    ("FACTORY FIRE IN INDONESIA", "24 DEAD CONFIRMED",
     "flame", GOLD, RED),
]

FOOTER_MAIN = "ALL STORIES AS REPORTED ON MONDAY 23 NOVEMBER 2026"
FOOTER_SUB = "THE WORLD TODAY - ONE DAY, ONE PAGE"


def draw_masthead(sheet):
    sheet.fill_rect(0, 0, W, 112, NAVY)
    sheet.fill_rect(0, 112, W, 4, GOLD)
    draw_text(sheet, 28, 18, MASTHEAD_NAME, 5, WHITE)
    draw_text(sheet, 0, 60, MASTHEAD_DATE, 6, GOLD,
              align="center", width=W)


def draw_lead(sheet):
    x, y, w, h = 24, 128, 976, 268
    sheet.fill_rect(x, y, w, h, CARD)
    sheet.rect_outline(x, y, w, h, RULE, 2)
    sheet.fill_rect(x, y, 10, h, RED)
    draw_text(sheet, 48, 150, LEAD_KICKER, 3, RED)
    draw_text(sheet, 48, 182, LEAD_HEAD, 7, INK)
    draw_text(sheet, 48, 242, LEAD_SUB, 4, INK)
    ty = 282
    for ln in wrap_text(LEAD_BODY, 3, 736):
        draw_text(sheet, 48, ty, ln, 3, INK)
        ty += 26
    draw_icon(sheet, "globe", 800, 172, 180, NAVY, BLUE)


def draw_card(sheet, x, y, w, h, kicker, head, body, icon, accent):
    sheet.fill_rect(x, y, w, h, CARD)
    sheet.rect_outline(x, y, w, h, RULE, 2)
    sheet.fill_rect(x, y, w, 6, accent)
    draw_text(sheet, x + 16, y + 16, kicker, 2, accent)
    ty = y + 38
    for ln in wrap_text(head, 4, w - 32)[:2]:
        draw_text(sheet, x + 16, ty, ln, 4, INK)
        ty += 32
    by = y + 102
    for ln in wrap_text(body, 3, w - 32 - 72)[:3]:
        draw_text(sheet, x + 16, by, ln, 3, INK)
        by += 22
    draw_icon(sheet, icon, x + w - 72, y + h - 72, 56, NAVY, accent)


def draw_briefs(sheet):
    x, y, w, h = 24, 788, 976, 128
    sheet.fill_rect(x, y, w, h, CARD)
    sheet.rect_outline(x, y, w, h, RULE, 2)
    draw_text(sheet, 40, 800, "IN BRIEF", 3, RED)
    for i, (head, sub, icon, main, accent) in enumerate(BRIEFS):
        col = 40 + i * 320
        draw_icon(sheet, icon, col, 828, 56, main, accent)
        tx = col + 68
        ty = 828
        for ln in wrap_text(head, 3, 228)[:2]:
            draw_text(sheet, tx, ty, ln, 3, INK)
            ty += 26
        draw_text(sheet, tx, 886, sub, 2, GREY)


def draw_footer(sheet):
    sheet.fill_rect(24, 932, 976, 2, RULE)
    draw_text(sheet, 0, 948, FOOTER_MAIN, 3, INK,
              align="center", width=W)
    draw_text(sheet, 0, 976, FOOTER_SUB, 2, GREY,
              align="center", width=W)


def build():
    sheet = Sheet(W, H, PAPER)
    draw_masthead(sheet)
    draw_lead(sheet)
    positions = [(24, 412), (524, 412), (24, 600), (524, 600)]
    for (cx, cy), (kicker, head, body, icon, accent) in zip(positions,
                                                            CARDS):
        draw_card(sheet, cx, cy, 476, 172, kicker, head, body,
                  icon, accent)
    draw_briefs(sheet)
    draw_footer(sheet)
    return sheet


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "out"
    sheet = build()
    data = encode_png(sheet)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))


if __name__ == "__main__":
    main()
