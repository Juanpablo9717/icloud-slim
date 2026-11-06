"""Retro arcade terminal logos from built-in bitmap fonts (no deps; rich only in gradient)."""

STYLES = ("shadow", "pixel", "small")  # big -> small
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -.!"


def _font(spec):
    """'A: row|row|...' lines -> {char: [rows]} with rows padded to equal width."""
    font = {}
    for line in spec.strip("\n").split("\n"):
        ch, rows = line[0], line[3:].split("|")
        w = max(map(len, rows))
        font[ch] = [r.ljust(w) for r in rows]
    return font


# 5-row fill masks in the spirit of figlet "ANSI Shadow" (the shadow is computed).
BIG = _font("""
A:  ##### |##   ##|#######|##   ##|##   ##
B: ###### |##   ##|###### |##   ##|######
C:  ######|##     |##     |##     | ######
D: ###### |##   ##|##   ##|##   ##|######
E: #######|##     |#####  |##     |#######
F: #######|##     |#####  |##     |##
G:  ######|##     |##  ###|##   ##| ######
H: ##   ##|##   ##|#######|##   ##|##   ##
I: ##|##|##|##|##
J:      ##|     ##|     ##|##   ##| #####
K: ##   ##|##  ## |#####  |##  ## |##   ##
L: ##     |##     |##     |##     |#######
M: ###   ###|#### ####|## ### ##|##  #  ##|##     ##
N: ###   ##|####  ##|## ## ##|##  ####|##   ###
O:  ##### |##   ##|##   ##|##   ##| #####
P: ###### |##   ##|###### |##     |##
Q:  ##### |##   ##|##   ##|##  ## | ### ##
R: ###### |##   ##|###### |##   ##|##   ##
S: #######|##     |#######|     ##|#######
T: ########|   ##   |   ##   |   ##   |   ##
U: ##   ##|##   ##|##   ##|##   ##| #####
V: ##   ##|##   ##|##   ##| ## ## |  ###
W: ##     ##|##     ##|##  #  ##|## ### ##| ###  ###
X: ##   ##| ## ## |  ###  | ## ## |##   ##
Y: ##    ##| ##  ## |  ####  |   ##   |   ##
Z: #######|    ## |   ##  |  ##   |#######
0:  ##### |##  ###|## # ##|###  ##| #####
1:  ##|###| ##| ##| ##
2: ###### |     ##| ##### |##     |#######
3: ###### |     ##| ##### |     ##|######
4: ##   ##|##   ##|#######|     ##|     ##
5: #######|##     |###### |     ##|######
6:  ######|##     |###### |##   ##| #####
7: #######|     ##|    ## |   ##  |   ##
8:  ##### |##   ##| ##### |##   ##| #####
9:  ##### |##   ##| ######|     ##| #####
-:      |      |######|      |
.:   |   |   |   |##
!: ##|##|##|  |##
 :    |   |   |   |
""")

# Classic 5x7 arcade/LCD font (one column per pixel, two pixel rows per line).
PX = _font("""
A:  ### |#   #|#   #|#####|#   #|#   #|#   #
B: #### |#   #|#   #|#### |#   #|#   #|####
C:  ### |#   #|#    |#    |#    |#   #| ###
D: #### |#   #|#   #|#   #|#   #|#   #|####
E: #####|#    |#    |#### |#    |#    |#####
F: #####|#    |#    |#### |#    |#    |#
G:  ### |#   #|#    |# ###|#   #|#   #| ####
H: #   #|#   #|#   #|#####|#   #|#   #|#   #
I:  ### |  #  |  #  |  #  |  #  |  #  | ###
J:   ###|   # |   # |   # |   # |#  # | ##
K: #   #|#  # |# #  |##   |# #  |#  # |#   #
L: #    |#    |#    |#    |#    |#    |#####
M: #   #|## ##|# # #|# # #|#   #|#   #|#   #
N: #   #|#   #|##  #|# # #|#  ##|#   #|#   #
O:  ### |#   #|#   #|#   #|#   #|#   #| ###
P: #### |#   #|#   #|#### |#    |#    |#
Q:  ### |#   #|#   #|#   #|# # #|#  # | ## #
R: #### |#   #|#   #|#### |# #  |#  # |#   #
S:  ####|#    |#    | ### |    #|    #|####
T: #####|  #  |  #  |  #  |  #  |  #  |  #
U: #   #|#   #|#   #|#   #|#   #|#   #| ###
V: #   #|#   #|#   #|#   #|#   #| # # |  #
W: #   #|#   #|#   #|# # #|# # #|# # #| # #
X: #   #|#   #| # # |  #  | # # |#   #|#   #
Y: #   #|#   #| # # |  #  |  #  |  #  |  #
Z: #####|    #|   # |  #  | #   |#    |#####
0:  ### |#   #|#  ##|# # #|##  #|#   #| ###
1:   #  | ##  |  #  |  #  |  #  |  #  | ###
2:  ### |#   #|    #|   # |  #  | #   |#####
3: #####|   # |  #  |   # |    #|#   #| ###
4:    # |  ## | # # |#  # |#####|   # |   #
5: #####|#    |#### |    #|    #|#   #| ###
6:   ## | #   |#    |#### |#   #|#   #| ###
7: #####|    #|   # |  #  | #   | #   | #
8:  ### |#   #|#   #| ### |#   #|#   #| ###
9:  ### |#   #|#   #| ####|    #|   # | ##
-:      |     |     |#####|     |     |
.:   |  |  |  |  |##|##
!: ##|##|##|##|##|  |##
 :    |   |   |   |   |   |
""")

# Tiny 3x5 font (two pixel rows per line -> 3 lines).
SM = _font("""
A:  # |# #|###|# #|# #
B: ## |# #|## |# #|##
C:  ##|#  |#  |#  | ##
D: ## |# #|# #|# #|##
E: ###|#  |## |#  |###
F: ###|#  |## |#  |#
G:  ##|#  |# #|# #| ##
H: # #|# #|###|# #|# #
I: ###| # | # | # |###
J:   #|  #|  #|# #| #
K: # #|# #|## |# #|# #
L: #  |#  |#  |#  |###
M: # #|###|# #|# #|# #
N: ## |# #|# #|# #|# #
O: ###|# #|# #|# #|###
P: ## |# #|## |#  |#
Q:  # |# #|# #|## | ##
R: ## |# #|## |# #|# #
S:  ##|#  | # |  #|##
T: ###| # | # | # | #
U: # #|# #|# #|# #|###
V: # #|# #|# #|# #| #
W: # #|# #|###|###|# #
X: # #|# #| # |# #|# #
Y: # #|# #| # | # | #
Z: ###|  #| # |#  |###
0:  # |# #|# #|# #| #
1:  # |## | # | # |###
2: ## |  #| # |#  |###
3: ## |  #| # |  #|##
4: # #|# #|###|  #|  #
5: ###|#  |## |  #|##
6:  ##|#  |###|# #|###
7: ###|  #| # | # | #
8: ###|# #|###|# #|###
9: ###|# #|###|  #|##
-:    |   |###|   |
.:  | | | |#
!: #|#|#| |#
 :   |  |  |  |
""")

_FONTS = {"shadow": BIG, "pixel": PX, "small": SM}
_HALF = {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}


def _bitmap(text, font):
    """Glyph rows joined with a 1-column gap -> list of '#'/' ' rows."""
    glyphs = [font.get(c, font[" "]) for c in text.upper()] or [font[" "]]
    return [" ".join(g[r] for g in glyphs) for r in range(len(glyphs[0]))]


def _shadow(rows):
    """Fill -> ANSI-Shadow look: █ plus a box-drawing drop shadow down/right."""
    h, w = len(rows) + 1, len(rows[0]) + 1
    filled = lambda r, c: 0 <= r < h - 1 and 0 <= c < w - 1 and rows[r][c] == "#"
    kind = {}  # shadow cells: HV (left+up filled), V (left), H (up), D (diagonal only)
    for r in range(h):
        for c in range(w):
            if filled(r, c):
                continue
            left, up = filled(r, c - 1), filled(r - 1, c)
            if left and up:
                kind[r, c] = "HV"
            elif left:
                kind[r, c] = "V"
            elif up:
                kind[r, c] = "H"
            elif filled(r - 1, c - 1):
                kind[r, c] = "D"
    out = []
    for r in range(h):
        line = ""
        for c in range(w):
            k = kind.get((r, c))
            if filled(r, c):
                line += "█"
            elif k == "HV":
                line += "╔"
            elif k == "V":  # vertical edge; starts with ╗ unless a line comes from above
                line += "║" if kind.get((r - 1, c)) in ("HV", "V") else "╗"
            elif k == "H":  # horizontal edge; starts with ╚ unless a line comes from the left
                line += "═" if kind.get((r, c - 1)) in ("HV", "H") else "╚"
            elif k == "D":
                line += "╝"
            else:
                line += " "
        out.append(line)
    return out


def _halves(rows):
    """Pack two pixel rows per text line with ▀ ▄ █."""
    if len(rows) % 2:
        rows = rows + [" " * len(rows[0])]
    return ["".join(_HALF[a == "#", b == "#"] for a, b in zip(top, bot))
            for top, bot in zip(rows[::2], rows[1::2])]


def render(text: str, style: str = "shadow", scale: int = 1) -> list[str]:
    """Lines of the logo (all same width, monospace). Supports A-Z, 0-9, space, '-', '.', '!';
    lowercase rendered as uppercase; unknown chars -> space. scale=2 doubles the pixels (big screens)."""
    rows = _bitmap(text, _FONTS[style])
    rows = ["".join(ch * scale for ch in row) for row in rows for _ in range(scale)]
    return _shadow(rows) if style == "shadow" else _halves(rows)


def width(text: str, style: str = "shadow") -> int:
    return len(render(text, style)[0])


def fit(text: str, max_width: int) -> tuple[str, list[str]]:
    """Pick the biggest style whose width fits max_width; returns (style, lines).
    Nothing fits -> ("plain", [the uppercase text cut to max_width])."""
    for style in STYLES:
        lines = render(text, style)
        if len(lines[0]) <= max_width:
            return style, lines
    return "plain", [text.upper()[:max(max_width, 0)]]


PALETTES = {
    "sunset": ["#ff2fb9", "#ff4f7b", "#ff7a3d", "#ffa62b", "#ffe14d"],
    "neon": ["#00f0ff", "#00a8ff", "#4d6bff", "#a64dff", "#ff3df2"],
    "arcade": ["#ff3b3b", "#ff9b1a", "#ffe81a", "#4dff5a"],
    "mono": ["#ffffff", "#d6d6d6", "#a8a8a8", "#8a8a8a"],
    "ice": ["#e8fbff", "#9ff0ff", "#4fd3ff", "#3a8bff", "#7b6bff"],
}
_BOX = set("╔╗╚╝║═")


def _mix(palette, t, dim=1.0):
    t = min(max(t, 0.0), 1.0) * (len(palette) - 1)
    i = min(int(t), len(palette) - 2)
    a, b = (bytes.fromhex(palette[j][1:]) for j in (i, i + 1))
    f = t - i
    return "#" + "".join(f"{int((x + (y - x) * f) * dim):02x}" for x, y in zip(a, b))


def gradient(lines: list[str], palette: str = "sunset"):
    """Diagonal gradient across the logo; spaces stay uncolored; shadow strokes a bit darker.
    Returns one rich Text (lines joined with \\n), no_wrap."""
    from rich.text import Text

    colors = PALETTES.get(palette, PALETTES["sunset"])
    span = max(len(lines[0]) + 2 * len(lines) - 1, 1) if lines else 1
    out = Text(no_wrap=True, overflow="crop")
    for r, line in enumerate(lines):
        if r:
            out.append("\n")
        for c, ch in enumerate(line):
            if ch == " ":
                out.append(ch)
            else:
                out.append(ch, style=_mix(colors, (c + 2 * r) / span, 0.6 if ch in _BOX else 1.0))
    return out


NAMES = ("iCLOUD SLIM", "ZERO-G", "SPACE SAVER", "PAYLOAD", "FEATHER")


def preview_text(names=NAMES) -> str:
    out = []
    for name in names:
        for style in STYLES:
            out.append(f"== {name!r} · {style} · width {width(name, style)} ==")
            out += render(name, style) + [""]
    out.append("== alphabet ==")
    for style in STYLES:
        for chunk in ("ABCDEFGHIJ", "KLMNOPQRS", "TUVWXYZ", "0123456789", "-.! HI!"):
            out += render(chunk, style) + [""]
    return "\n".join(out)


def preview():
    """Print every style in every palette (needs rich)."""
    from rich.console import Console

    con = Console()
    for name in NAMES[:2]:
        for style in STYLES:
            for pal in PALETTES:
                con.print(f"[dim]{name} · {style} · {pal}[/]")
                con.print(gradient(render(name, style), pal))


def _selfcheck():
    for style in STYLES:
        for ch in CHARS:
            lines = render(ch, style)
            assert lines and len({len(l) for l in lines}) == 1, (style, ch)
            assert ch == " " or any(l.strip() for l in lines), (style, ch)
        assert render("a?", style) == render("A ", style)
        assert len({len(l) for l in render("iCLOUD SLIM", style)}) == 1
    for w in range(0, 140):
        style, lines = fit("SPACE SAVER", w)
        assert all(len(l) <= w for l in lines), (w, style)
    assert fit("ZERO-G", 999)[0] == "shadow"


if __name__ == "__main__":
    import os
    import sys

    _selfcheck()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_preview.txt")
    with open(path, "w") as f:
        f.write(preview_text() + "\n")
    print(f"self-check OK; wrote {path}")
    if "--color" in sys.argv:
        preview()
