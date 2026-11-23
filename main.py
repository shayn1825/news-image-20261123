#!/usr/bin/env python3
"""news-image-20261123 -- The Monday World: one page of 23 Nov 2026 news.

A deterministic, stdlib-only PNG renderer. Draws a newspaper front page
(1024x1024) from the day's verified stories: a navy masthead with the
paper's name, the date in large red type, one lead story, six grid
stories with hand-drawn pictograms, an IN BRIEF strip and a footer.

No network, no time, no randomness: two runs write identical bytes.
Run:  python3 main.py [out.png]     (default /output/entry.png)
"""

import binascii
import math
import os
import struct
import sys
import zlib

W, H = 1024, 1024

PAPER = (246, 241, 231)   # warm newsprint
INK = (24, 24, 36)        # near-black ink
NAVY = (20, 33, 61)       # masthead band
RED = (178, 28, 28)       # date + kickers + rules
GREY = (96, 94, 88)       # secondary text
PANEL = (232, 226, 210)   # pictogram panels
GOLD = (198, 158, 74)     # thin masthead rule

# ---------------------------------------------------------------- canvas

buf = bytearray(W * H * 3)
for _i in range(W * H):
    buf[_i * 3:_i * 3 + 3] = bytes(PAPER)


def px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        o = (y * W + x) * 3
        buf[o], buf[o + 1], buf[o + 2] = c


def rect(x, y, w, h, c):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    for yy in range(y0, y1):
        o = (yy * W + x0) * 3
        for xx in range(x0, x1):
            buf[o], buf[o + 1], buf[o + 2] = c
            o += 3


def hline(x0, x1, y, c, t=1):
    for yy in range(y, y + t):
        for xx in range(max(0, x0), min(W, x1)):
            px(xx, yy, c)


def vline(x, y0, y1, c, t=1):
    for xx in range(x, x + t):
        for yy in range(max(0, y0), min(H, y1)):
            px(xx, yy, c)


def line(x0, y0, x1, y1, c):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        px(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def disc(cx, cy, r, c):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                px(xx, yy, c)


def ring(cx, cy, r, c, t=2):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            d2 = (xx - cx) ** 2 + (yy - cy) ** 2
            if (r - t) ** 2 <= d2 <= r * r:
                px(xx, yy, c)


def tri(x0, y0, x1, y1, x2, y2, c):
    ys = sorted([(y0, x0), (y1, x1), (y2, x2)])
    (ya, xa), (yb, xb), (yc, xc) = ys
    if yc == ya:
        return

    def interp(y, y_a, x_a, y_b, x_b):
        if y_b == y_a:
            return x_a
        return x_a + (x_b - x_a) * (y - y_a) // (y_b - y_a)

    for y in range(ya, yc + 1):
        if y < yb:
            xa_y = interp(y, ya, xa, yb, xb)
            xb_y = interp(y, ya, xa, yc, xc)
        else:
            xa_y = interp(y, yb, xb, yc, xc)
            xb_y = interp(y, ya, xa, yc, xc)
        lo, hi = min(xa_y, xb_y), max(xa_y, xb_y)
        for x in range(lo, hi + 1):
            px(x, y, c)


def poly(points, c):
    # filled polygon via horizontal scanlines
    ys = [p[1] for p in points]
    for y in range(min(ys), max(ys) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (x1 - x0) * (y - y0) // (y1 - y0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            for x in range(xs[j], xs[j + 1] + 1):
                px(x, y, c)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits, written as strings. Uppercase only,
# plus digits and punctuation used by the copy below.

FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00000", "00100"),
    ",": ("00000", "00000", "00000", "00000", "00000", "00100", "01000"),
    ":": ("00000", "00100", "00000", "00000", "00000", "00100", "00000"),
    ";": ("00000", "00100", "00000", "00000", "00100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "10010", "00100", "01000", "01001", "10011", "00000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00000", "00100", "01110", "00100", "00000", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
}

CHAR_W = 6  # 5 pixels + 1 gap, times scale


def text_width(s, scale):
    return len(s) * CHAR_W * scale - scale


def draw_glyph(x, y, ch, scale, c):
    rows = FONT.get(ch)
    if rows is None:
        return
    for r in range(7):
        row = rows[r]
        for col in range(5):
            if row[col] == "1":
                rect(x + col * scale, y + r * scale, scale, scale, c)


def draw_text(x, y, s, scale, c):
    cx = x
    for ch in s.upper():  # the bitmap font is uppercase-only
        draw_glyph(cx, y, ch, scale, c)
        cx += CHAR_W * scale
    return cx


def wrap(text, scale, maxw):
    """Greedy word wrap. Returns list of lines; raises if a word is too long."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            if text_width(word, scale) > maxw:
                raise ValueError("word too long: %r" % word)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(x, y, text, scale, maxw, c, leading=4):
    lines = wrap(text, scale, maxw)
    for i, ln in enumerate(lines):
        draw_text(x, y + i * (7 * scale + leading), ln, scale, c)
    return len(lines)

# ---------------------------------------------------------------- pictograms
# Each icon is drawn from primitives inside a square box (x, y, size).
# All coordinates are relative to the box, so icons scale by construction.


def icon_globe_thermo(x, y, s):
    # COP31 lead: a globe with a rising thermometer beside it
    cx, cy, r = x + s * 38 // 100, y + s // 2, s * 30 // 100
    ring(cx, cy, r, INK, 3)
    # meridians + equator
    for k in range(-2, 3):
        vline(cx + k * r // 3, cy - r + 4, cy + r - 4, INK, 1)
    hline(cx - r + 3, cx + r - 2, cy, INK, 2)
    # thermometer
    tx = x + s * 74 // 100
    rect(tx, y + s * 12 // 100, s * 9 // 100, s * 58 // 100, RED)
    disc(tx + s * 9 // 200, y + s * 76 // 100, s * 11 // 100, RED)
    rect(tx + 2, y + s * 16 // 100, s * 9 // 100 - 4, s * 30 // 100, PAPER)
    # heat rays
    for k in range(3):
        yy = y + s * (10 + k * 14) // 100
        line(tx - 8, yy, tx - 2, yy - 6, RED)
        line(tx + s * 9 // 100 + 2, yy, tx + s * 9 // 100 + 8, yy - 6, RED)


def icon_ship(x, y, s):
    # Hormuz: a tanker on the water, smoke rising
    hull = [(x + s * 8 // 100, y + s * 52 // 100),
            (x + s * 92 // 100, y + s * 52 // 100),
            (x + s * 82 // 100, y + s * 74 // 100),
            (x + s * 18 // 100, y + s * 74 // 100)]
    poly(hull, INK)
    rect(x + s * 30 // 100, y + s * 34 // 100, s * 22 // 100, s * 18 // 100, RED)
    vline(x + s * 62 // 100, y + s * 18 // 100, y + s * 52 // 100, INK, 3)
    tri(x + s * 62 // 100, y + s * 18 // 100, x + s * 62 // 100,
        y + s * 34 // 100, x + s * 82 // 100, y + s * 34 // 100, RED)
    # smoke
    disc(x + s * 38 // 100, y + s * 22 // 100, s * 9 // 100, GREY)
    disc(x + s * 48 // 100, y + s * 12 // 100, s * 7 // 100, GREY)
    # waves
    for k, yy in enumerate((78, 86, 94)):
        xx = x + s * (6 + 4 * k) // 100
        for j in range(0, s * 88 // 100, 12):
            line(xx + j, y + s * yy // 100, xx + j + 6, y + s * yy // 100 - 4, NAVY)


def icon_radar(x, y, s):
    # Poland: radar dish sweeping, missile rising
    cx, cy = x + s * 42 // 100, y + s * 72 // 100
    line(cx, cy, cx - s * 30 // 100, cy - s * 26 // 100, INK)
    line(cx, cy, cx + s * 30 // 100, cy - s * 26 // 100, INK)
    line(cx - s * 30 // 100, cy - s * 26 // 100,
         cx + s * 30 // 100, cy - s * 26 // 100, INK)
    line(cx, cy, cx + s * 34 // 100, cy - s * 52 // 100, RED)
    disc(cx + s * 34 // 100, cy - s * 52 // 100, 4, RED)
    # missile
    mx = x + s * 76 // 100
    tri(mx, y + s * 12 // 100, mx - 7, y + s * 34 // 100,
        mx + 7, y + s * 34 // 100, INK)
    rect(mx - 5, y + s * 34 // 100, 10, s * 18 // 100, INK)
    line(mx, y + s * 56 // 100, mx, y + s * 66 // 100, RED)


def icon_ball(x, y, s):
    # FIFA: a football - ring, centre pentagon, seams to the edge
    cx, cy, r = x + s // 2, y + s // 2, s * 34 // 100
    ring(cx, cy, r, INK, 3)
    pts = []
    for i in range(5):
        ang = -math.pi / 2 + i * 2 * math.pi / 5
        rr = r * 38 // 100
        pts.append((cx + int(rr * math.cos(ang)), cy + int(rr * math.sin(ang))))
    poly(pts, INK)
    for i in range(5):
        ang = -math.pi / 2 + i * 2 * math.pi / 5
        px0 = cx + int(r * 38 // 100 * math.cos(ang))
        py0 = cy + int(r * 38 // 100 * math.sin(ang))
        px1 = cx + int((r - 3) * math.cos(ang))
        py1 = cy + int((r - 3) * math.sin(ang))
        line(px0, py0, px1, py1, INK)


def icon_trade(x, y, s):
    # Markets: two opposing arrows and a coin
    ay = y + s * 30 // 100
    rect(x + s * 10 // 100, ay, s * 62 // 100, 6, NAVY)
    tri(x + s * 72 // 100, ay - 8, x + s * 72 // 100, ay + 14,
        x + s * 92 // 100, ay + 3, NAVY)
    by = y + s * 58 // 100
    rect(x + s * 28 // 100, by, s * 62 // 100, 6, RED)
    tri(x + s * 28 // 100, by - 8, x + s * 28 // 100, by + 14,
        x + s * 8 // 100, by + 3, RED)
    cx, cy, r = x + s * 50 // 100, y + s * 82 // 100, s * 12 // 100
    disc(cx, cy, r, GOLD)
    ring(cx, cy, r, INK, 2)
    draw_text(cx - 6, cy - 7, "$", 2, INK)


def icon_un_globe(x, y, s):
    # UN / killer robots: globe ringed by two olive branches
    cx, cy, r = x + s // 2, y + s * 42 // 100, s * 30 // 100
    ring(cx, cy, r, NAVY, 3)
    for k in range(-2, 3):
        vline(cx + k * r // 3, cy - r + 4, cy + r - 4, NAVY, 1)
    hline(cx - r + 3, cx + r - 2, cy, NAVY, 2)
    # olive branches: two arcs of small discs
    for k in range(6):
        ang = 3.6 + k * 0.28
        bx = cx + int((r + 8) * math.cos(ang))
        by = cy + int((r + 8) * math.sin(ang)) - 4
        disc(bx, by, 3, NAVY)
        bx2 = cx - int((r + 8) * math.cos(ang))
        disc(bx2, by, 3, NAVY)


def icon_capitol(x, y, s):
    # Congress: a domed capitol with columns and a flag
    cx = x + s // 2
    # flag pole + flag
    vline(cx, y + s * 6 // 100, y + s * 24 // 100, INK, 3)
    tri(cx + 2, y + s * 6 // 100, cx + 2, y + s * 18 // 100,
        cx + s * 18 // 100, y + s * 12 // 100, RED)
    # dome: full disc with its lower half cut away
    dcx, dcy, dr = cx, y + s * 48 // 100, s * 26 // 100
    disc(dcx, dcy, dr, INK)
    rect(dcx - dr, dcy, 2 * dr, dr, PANEL)
    rect(dcx - dr, dcy - 2, 2 * dr, 4, INK)
    # columns
    for k in range(3):
        colx = x + s * (24 + k * 24) // 100
        rect(colx, y + s * 54 // 100, s * 8 // 100, s * 24 // 100, INK)
    # base
    rect(x + s * 12 // 100, y + s * 80 // 100, s * 76 // 100, s * 8 // 100, INK)
    rect(x + s * 6 // 100, y + s * 88 // 100, s * 88 // 100, s * 5 // 100, NAVY)

# ---------------------------------------------------------------- the news
# All stories verified from live sources on 23 Nov 2026 (see README).
# Copy is written to fit: headlines wrap to <=2 lines, decks to <=4 lines
# in the grid (30 chars/line at scale 2) and <=4 lines in the lead.

LEAD = {
    "kicker": "CLIMATE SUMMIT - ANTALYA, TURKEY",
    "headline": "COP31 COLLAPSES AFTER RECORD OVERTIME AS FOSSIL FUEL FIGHT KILLS DEAL",
    "deck": "The summit ended with no agreed text after record overtime. The "
            "draft drops every mention of fossil fuels and the $120BN "
            "adaptation fund - and admits the 1.5C goal has been missed.",
    "icon": icon_globe_thermo,
}

GRID = [
    {"kicker": "POLAND - NATO",
     "headline": "POLAND CONFIRMS FALLEN OBJECTS WERE RUSSIAN MISSILES",
     "deck": "Three cruise missiles fell in the south-east on Friday. NATO "
             "will meet as Warsaw reports an airspace breach.",
     "icon": icon_radar},
    {"kicker": "STRAIT OF HORMUZ",
     "headline": "TANKERS STRUCK AND MINED IN THE STRAIT OF HORMUZ",
     "deck": "At least three tankers were hit. Iran says two more caught "
             "fire on mines as attacks hit a wartime high.",
     "icon": icon_ship},
    {"kicker": "FOOTBALL - LONDON",
     "headline": "FIFA SET TO NAME UK AS 2035 WOMEN'S WORLD CUP HOST",
     "deck": "The first World Cup in Britain since 1966. The women's "
             "tournament heads to the UK in 2035.",
     "icon": icon_ball},
    {"kicker": "MARKETS - ASIA",
     "headline": "STOCKS PLUNGE AS TAIWAN BANS SHORT SELLING",
     "deck": "Taiwan shares fell 17.5% in a week. The regulator bans short "
             "selling from today as Asia stays on alert.",
     "icon": icon_trade},
    {"kicker": "UNITED NATIONS",
     "headline": "128 STATES AGREE TO PURSUE KILLER-ROBOT RULES BY 2028",
     "deck": "Nations agree to keep negotiating binding rules on lethal "
             "autonomous weapons at the UN conference.",
     "icon": icon_un_globe},
    {"kicker": "WASHINGTON",
     "headline": "DEMOCRATS WIN CONTROL OF CONGRESS",
     "deck": "Their largest House majority since 1992 after flipping a North "
             "Carolina seat. Funding deadline: 11 December.",
     "icon": icon_capitol},
]

BRIEF = [
    "BEPICOLOMBO REACHES MERCURY ORBIT",
    "MARQUEZ WINS RECORD-TYING 8TH MOTOGP TITLE",
    "INDONESIA FACTORY FIRE: 24 BODIES, SEARCH RESUMES",
]

# ---------------------------------------------------------------- layout


def draw():
    # --- masthead band
    rect(0, 0, W, 116, NAVY)
    name = "THE MONDAY WORLD"
    draw_text((W - text_width(name, 6)) // 2, 20, name, 6, PAPER)
    tag = "WORLD NEWS IN ONE IMAGE"
    draw_text((W - text_width(tag, 2)) // 2, 78, tag, 2, GOLD)
    hline(28, W - 28, 104, GOLD, 2)

    # --- date strip: the date must be unmistakable
    date = "MONDAY - 23 NOVEMBER 2026"
    draw_text((W - text_width(date, 4)) // 2, 128, date, 4, RED)
    hline(28, W - 28, 166, RED, 3)

    # --- lead story
    lx, lw = 28, 660
    draw_text(lx, 186, LEAD["kicker"], 2, RED)
    n = draw_para(lx, 210, LEAD["headline"], 3, lw, INK, leading=5)
    draw_para(lx, 210 + n * (7 * 3 + 5) + 8, LEAD["deck"], 2, lw, INK)
    # lead pictogram panel
    rect(700, 186, 296, 176, PANEL)
    rect(700, 186, 296, 176, INK)  # placeholder overwritten below (border)
    rect(703, 189, 290, 170, PANEL)
    LEAD["icon"](773, 200, 150)
    hline(28, W - 28, 380, INK, 2)

    # --- grid: 2 columns x 3 rows
    col_w, row_h = 472, 156
    for i, st in enumerate(GRID):
        cx = 28 + (i % 2) * 500
        cy = 392 + (i // 2) * 164
        # icon panel
        rect(cx, cy + 6, 92, 92, PANEL)
        st["icon"](cx + 4, cy + 10, 84)
        tx, tw = cx + 104, col_w - 104
        draw_text(tx, cy + 6, st["kicker"], 2, RED)
        n = draw_para(tx, cy + 28, st["headline"], 2, tw, INK, leading=4)
        draw_para(tx, cy + 28 + n * (7 * 2 + 4) + 6, st["deck"], 2, tw, GREY)
        if i % 2 == 0:
            vline(cx + col_w + 14, cy, cy + row_h, PANEL, 2)
        if i < 4:
            hline(cx, cx + col_w, cy + row_h + 4, PANEL, 2)

    # --- IN BRIEF strip
    by = 892
    hline(28, W - 28, by, INK, 2)
    draw_text(28, by + 12, "IN BRIEF", 2, RED)
    for i, item in enumerate(BRIEF):
        bx = 28 + i * 336
        rect(bx, by + 44, 8, 8, RED)
        draw_para(bx + 16, by + 40, item, 2, 304, INK, leading=4)

    # --- footer
    hline(28, W - 28, 972, INK, 2)
    foot = "ALL EVENTS OF MONDAY 23 NOVEMBER 2026 - DRAWN BY AN AI AGENT"
    draw_text((W - text_width(foot, 2)) // 2, 986, foot, 2, GREY)


# ---------------------------------------------------------------- PNG encode


def chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    return c + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)


def png_bytes():
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    draw()
    data = png_bytes()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print("%s %d bytes" % (out, len(data)))


if __name__ == "__main__":
    main()
