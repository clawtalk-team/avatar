#!/usr/bin/env python3
"""
svg_generator.py  —  cartoon SVG viseme generator
--------------------------------------------------
Generates 15 viseme face frames as SVG files using parametric bezier curves.
No AI generation — all geometry is computed from the same (jaw_open,
lip_spread, lip_part) shape parameters used by generator.py.

Character: Duolingo-style generic cartoon face (white male, brown hair).

Steps:
  1. Generate all 15 SVG viseme frames
     python svg_generator.py --mode visemes

  2. Preview contact sheet (requires Pillow + cairosvg, or opens in browser)
     python svg_generator.py --mode sheet

Output: outputs/svg_visemes/{sil,PP,FF,...}.svg  (15 files)
        outputs/svg_visemes/contact_sheet.html    (browser preview)
"""

import argparse
import json
import math
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Viseme shape parameters  (same source of truth as generator.py)
#
# (jaw_open, lip_spread, lip_part)
#   jaw_open   0.0 = closed  →  1.0 = fully open
#   lip_spread -1.0 = pursed  →  0.0 = neutral  →  1.0 = wide spread
#   lip_part   negative = pressed  →  0.0 = touching  →  1.0 = max open
# ─────────────────────────────────────────────────────────────────────────────

VISEMES = {
    "sil": {"phonemes": ["silence"],          "shape": ( 0.00,  0.00,  0.00)},
    "PP":  {"phonemes": ["p","b","m"],         "shape": ( 0.00,  0.00, -0.20)},
    "FF":  {"phonemes": ["f","v"],             "shape": ( 0.05,  0.15,  0.20)},
    "TH":  {"phonemes": ["th","dh"],           "shape": ( 0.10,  0.00,  0.30)},
    "DD":  {"phonemes": ["t","d"],             "shape": ( 0.15,  0.10,  0.30)},
    "kk":  {"phonemes": ["k","g"],             "shape": ( 0.20,  0.00,  0.25)},
    "CH":  {"phonemes": ["ch","j","sh","zh"],  "shape": ( 0.12, -0.35,  0.28)},
    "SS":  {"phonemes": ["s","z"],             "shape": ( 0.05,  0.50,  0.12)},
    "nn":  {"phonemes": ["n","l","ng"],        "shape": ( 0.10,  0.05,  0.20)},
    "RR":  {"phonemes": ["r"],                 "shape": ( 0.15, -0.28,  0.25)},
    "aa":  {"phonemes": ["ah","aa","ae"],      "shape": ( 0.85,  0.15,  0.80)},
    "E":   {"phonemes": ["eh","ey"],           "shape": ( 0.40,  0.30,  0.50)},
    "I":   {"phonemes": ["ih","iy"],           "shape": ( 0.05,  0.55,  0.10)},
    "O":   {"phonemes": ["oh","ao","ow"],      "shape": ( 0.45, -0.40,  0.52)},
    "U":   {"phonemes": ["oo","uw","uh"],      "shape": ( 0.18, -0.65,  0.28)},
}

OUTPUT_DIR = Path("outputs/svg_visemes")

# ─────────────────────────────────────────────────────────────────────────────
# Canvas / face geometry constants  (all in SVG user units, 512×512 canvas)
# ─────────────────────────────────────────────────────────────────────────────

W, H = 512, 512
CX, CY = 256, 256   # face centre

# Head — oval, not circle
HEAD_RX = 148    # horizontal (narrower than vertical)
HEAD_RY = 192    # vertical
HEAD_CY = CY + 6  # face centre shifted down slightly to give hair room on top

# Hair — ellipse clipped to above the hairline (no half-circle artifact)
HAIRLINE_Y   = HEAD_CY - 108   # where forehead meets hair (~84px below top of head)
HAIR_RX      = HEAD_RX + 16    # slightly wider than face for volume
HAIR_RY      = HEAD_RY + 22    # extends above head
HAIR_ECY     = HEAD_CY - 48    # hair ellipse centre is above face centre

# Eyes
EYE_Y       = HEAD_CY - 50
EYE_OFFSET  = 60   # distance from centre to each eye
EYE_RX, EYE_RY = 28, 24
IRIS_R      = 14
PUPIL_R     = 7

# Nose
NOSE_CX, NOSE_CY = CX, HEAD_CY + 22
NOSE_RX, NOSE_RY = 10, 7

# Mouth neutral centre
MOUTH_CX    = CX
MOUTH_CY    = HEAD_CY + 78

# Mouth geometry scale factors
MOUTH_HALF_W = 54    # half-width of neutral mouth (corner to centre)
MOUTH_HALF_H = 10    # half-height of neutral mouth opening


# ─────────────────────────────────────────────────────────────────────────────
# Colours
# ─────────────────────────────────────────────────────────────────────────────

SKIN        = "#F5C5A3"
SKIN_SHADOW = "#E8A87C"
HAIR        = "#5C3A1E"
EYE_WHITE   = "#FFFFFF"
EYE_IRIS    = "#6B4C2A"
EYE_PUPIL   = "#1A1A1A"
EYE_OUTLINE = "#2A1A0A"
LIP_UPPER   = "#D4806A"
LIP_LOWER   = "#C06050"
MOUTH_DARK  = "#1A0A08"
TEETH       = "#F5F0E8"
TONGUE      = "#C85050"
OUTLINE     = "#2A1A0A"
BG          = "#F0EDE8"
CHEEK       = "#F0A898"


# ─────────────────────────────────────────────────────────────────────────────
# Mouth geometry computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_mouth(jaw_open: float, lip_spread: float, lip_part: float) -> dict:
    """
    Returns a dict of mouth control points derived from the viseme parameters.

    All coordinates are in SVG canvas space (origin top-left).

    Returns:
        left_x, right_x           — corners
        upper_top_y               — top of upper lip arc
        upper_bot_y               — bottom of upper lip (inner edge)
        lower_top_y               — top of lower lip (inner edge)
        lower_bot_y               — bottom of lower lip arc
        corner_y                  — vertical position of mouth corners
        ctrl_spread               — bezier horizontal spread (how wide the curves bow)
        jaw_open, lip_spread, lip_part  — forwarded for downstream decisions
    """
    mw = MOUTH_HALF_W
    mh = MOUTH_HALF_H
    cx = MOUTH_CX
    cy = MOUTH_CY

    # Horizontal extent — corners spread outward with lip_spread
    spread_dx = lip_spread * mw * 0.38
    left_x  = cx - mw + spread_dx
    right_x = cx + mw - spread_dx

    # Vertical jaw drop — lower lip and chin move down
    jaw_dy = jaw_open * 52

    # Corner vertical shift — slight upward pull with spread (smile-like)
    corner_dy = -lip_spread * 6

    corner_y = cy + corner_dy

    # Lip parting
    if lip_part >= 0:
        upper_open = lip_part * mh * 0.9    # upper lip lifts
        lower_open = lip_part * mh * 1.4    # lower lip drops
    else:
        # Pressed together — both lips move toward each other
        upper_open = lip_part * mh * 0.4    # upper nudges down (negative = toward centre)
        lower_open = lip_part * mh * 0.6    # lower nudges up

    # Pucker — pursed lips bow upward slightly
    pucker_dy = max(0.0, -lip_spread) * 5

    upper_top_y = corner_y - mh * 1.2 - upper_open - pucker_dy
    upper_bot_y = corner_y - upper_open

    lower_top_y = corner_y + jaw_dy + lower_open
    lower_bot_y = corner_y + jaw_dy + mh * 1.2 + lower_open

    # Bezier control point spread — how much the lip curves bow horizontally
    ctrl_spread = (right_x - left_x) * 0.28

    return dict(
        left_x=left_x, right_x=right_x,
        upper_top_y=upper_top_y, upper_bot_y=upper_bot_y,
        lower_top_y=lower_top_y, lower_bot_y=lower_bot_y,
        corner_y=corner_y,
        ctrl_spread=ctrl_spread,
        jaw_open=jaw_open, lip_spread=lip_spread, lip_part=lip_part,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SVG path builders
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(x: float, y: float) -> str:
    return f"{x:.1f},{y:.1f}"


def mouth_cavity_path(m: dict) -> str | None:
    """
    Dark interior of the open mouth. Returns None if mouth is nearly closed.
    Only drawn when lip gap is large enough to be visible.
    """
    gap = m["lower_top_y"] - m["upper_bot_y"]
    if gap < 4:
        return None

    lx, rx = m["left_x"], m["right_x"]
    ut, ub = m["upper_bot_y"], m["lower_top_y"]
    cs = m["ctrl_spread"]
    cx = (lx + rx) / 2

    # Top edge of cavity = inner upper lip
    # Bottom edge of cavity = inner lower lip
    # Drawn as a filled shape with soft bezier curves
    d = (
        f"M {_fmt(lx, (ut+ub)/2)}"
        f" C {_fmt(cx - cs, ut)} {_fmt(cx + cs, ut)} {_fmt(rx, (ut+ub)/2)}"
        f" C {_fmt(cx + cs, ub)} {_fmt(cx - cs, ub)} {_fmt(lx, (ut+ub)/2)}"
        f" Z"
    )
    return d


def upper_lip_path(m: dict) -> str:
    """
    Upper lip: from left corner → top arc → right corner → inner arc → back.
    """
    lx, rx = m["left_x"], m["right_x"]
    cy_corner = m["corner_y"]
    top_y = m["upper_top_y"]
    bot_y = m["upper_bot_y"]
    cs = m["ctrl_spread"]
    cx = (lx + rx) / 2

    # Outer top arc (the cupid's bow)
    # Two bumps — left of centre slightly higher, classic lip shape
    left_peak_x  = cx - (rx - lx) * 0.22
    right_peak_x = cx + (rx - lx) * 0.22
    peak_y = top_y

    d = (
        f"M {_fmt(lx, cy_corner)}"
        # Outer top — left half to centre dip, then right half
        f" C {_fmt(lx + cs, top_y + 4)} {_fmt(left_peak_x - 8, peak_y - 2)} {_fmt(cx, top_y + 5)}"
        f" C {_fmt(right_peak_x + 8, peak_y - 2)} {_fmt(rx - cs, top_y + 4)} {_fmt(rx, cy_corner)}"
        # Inner bottom arc
        f" C {_fmt(rx - cs * 0.6, bot_y)} {_fmt(lx + cs * 0.6, bot_y)} {_fmt(lx, cy_corner)}"
        f" Z"
    )
    return d


def lower_lip_path(m: dict) -> str:
    """
    Lower lip: from left corner → inner top arc → right corner → outer bottom arc → back.
    """
    lx, rx = m["left_x"], m["right_x"]
    cy_corner = m["corner_y"]
    top_y = m["lower_top_y"]
    bot_y = m["lower_bot_y"]
    cs = m["ctrl_spread"]
    cx = (lx + rx) / 2

    d = (
        f"M {_fmt(lx, cy_corner)}"
        # Inner top (touches upper lip)
        f" C {_fmt(lx + cs * 0.6, top_y)} {_fmt(rx - cs * 0.6, top_y)} {_fmt(rx, cy_corner)}"
        # Outer bottom arc
        f" C {_fmt(rx - cs, bot_y)} {_fmt(lx + cs, bot_y)} {_fmt(lx, cy_corner)}"
        f" Z"
    )
    return d


def teeth_path(m: dict) -> str | None:
    """Teeth strip, shown when mouth is sufficiently open."""
    gap = m["lower_top_y"] - m["upper_bot_y"]
    if gap < 6:
        return None

    lx, rx = m["left_x"] + 6, m["right_x"] - 6
    top_y = m["upper_bot_y"] + 1
    bot_y = min(m["lower_top_y"] - 1, top_y + gap * 0.45)

    if bot_y <= top_y:
        return None

    cx = (lx + rx) / 2
    cs = (rx - lx) * 0.15
    d = (
        f"M {_fmt(lx, top_y)}"
        f" C {_fmt(cx - cs, top_y - 2)} {_fmt(cx + cs, top_y - 2)} {_fmt(rx, top_y)}"
        f" L {_fmt(rx, bot_y)}"
        f" C {_fmt(cx + cs, bot_y + 2)} {_fmt(cx - cs, bot_y + 2)} {_fmt(lx, bot_y)}"
        f" Z"
    )
    return d


def tongue_path(m: dict) -> str | None:
    """Tongue tip, visible on wide-open visemes (aa, E, O)."""
    gap = m["lower_top_y"] - m["upper_bot_y"]
    if gap < 20 or m["jaw_open"] < 0.35:
        return None

    cx = MOUTH_CX
    top_y = m["upper_bot_y"] + gap * 0.55
    bot_y = m["lower_top_y"] - 2
    half_w = (m["right_x"] - m["left_x"]) * 0.30

    if bot_y <= top_y:
        return None

    d = (
        f"M {_fmt(cx - half_w, bot_y)}"
        f" C {_fmt(cx - half_w * 1.1, top_y)} {_fmt(cx + half_w * 1.1, top_y)} {_fmt(cx + half_w, bot_y)}"
        f" C {_fmt(cx + half_w * 0.5, bot_y + 8)} {_fmt(cx - half_w * 0.5, bot_y + 8)} {_fmt(cx - half_w, bot_y)}"
        f" Z"
    )
    return d


def teeth_line_path(m: dict) -> str | None:
    """Subtle vertical tooth division lines when teeth are showing."""
    gap = m["lower_top_y"] - m["upper_bot_y"]
    if gap < 10:
        return None
    lx, rx = m["left_x"] + 8, m["right_x"] - 8
    top_y = m["upper_bot_y"] + 2
    bot_y = min(m["lower_top_y"] - 2, top_y + gap * 0.40)
    cx = (lx + rx) / 2

    # Two dividers: at 1/3 and 2/3 across
    p1x = lx + (rx - lx) / 3
    p2x = lx + (rx - lx) * 2 / 3
    lines = []
    for px in [cx]:  # single centre line — enough at cartoon scale
        lines.append(f"M {px:.1f},{top_y:.1f} L {px:.1f},{bot_y:.1f}")
    return " ".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Full face SVG builder
# ─────────────────────────────────────────────────────────────────────────────

def build_face_svg(viseme_name: str, jaw_open: float, lip_spread: float,
                   lip_part: float) -> str:
    m = compute_mouth(jaw_open, lip_spread, lip_part)

    cavity  = mouth_cavity_path(m)
    upper   = upper_lip_path(m)
    lower   = lower_lip_path(m)
    teeth   = teeth_path(m)
    tongue  = tongue_path(m)
    t_lines = teeth_line_path(m)

    # Philtrum (vertical groove above upper lip)
    philtrum_top_y = m["upper_top_y"] - 18
    philtrum_bot_y = m["upper_top_y"] + 2
    philtrum_x     = MOUTH_CX

    # Eyebrow positions (neutral expression)
    brow_y   = EYE_Y - 36
    brow_len = 40

    # Ear positions — flush with sides of the oval face
    ear_y  = HEAD_CY - 12
    ear_rx, ear_ry = 15, 24

    # Hair geometry (computed once for use in SVG below)
    hair_hl_y = HAIRLINE_Y      # hairline across forehead
    hair_ecx  = CX
    hair_ecy  = HAIR_ECY

    phoneme_label = ", ".join(VISEMES[viseme_name]["phonemes"][:3])

    # Derived hair geometry
    hair_top_y = hair_ecy - HAIR_RY   # top of hair ellipse (above head)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <radialGradient id="skinGrad" cx="45%" cy="38%" r="58%">
      <stop offset="0%"   stop-color="#FDD8BC"/>
      <stop offset="65%"  stop-color="{SKIN}"/>
      <stop offset="100%" stop-color="{SKIN_SHADOW}"/>
    </radialGradient>
    <radialGradient id="hairGrad" cx="40%" cy="30%" r="60%">
      <stop offset="0%"   stop-color="#7A5030"/>
      <stop offset="100%" stop-color="#3A2010"/>
    </radialGradient>
    <radialGradient id="cheekL" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{CHEEK}" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="{CHEEK}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="cheekR" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{CHEEK}" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="{CHEEK}" stop-opacity="0"/>
    </radialGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#00000028"/>
    </filter>
    <!-- Clip: show hair ellipse only ABOVE the hairline -->
    <clipPath id="hairClip">
      <rect x="0" y="0" width="{W}" height="{hair_hl_y:.1f}"/>
    </clipPath>
    <!-- Clip: show hair sides (below hairline, outside face oval) -->
    <clipPath id="hairSideClip">
      <rect x="0" y="{hair_hl_y:.1f}" width="{W}" height="{H - hair_hl_y:.1f}"/>
    </clipPath>
    <clipPath id="headClip">
      <ellipse cx="{CX}" cy="{HEAD_CY}" rx="{HEAD_RX + 3}" ry="{HEAD_RY + 3}"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="{W}" height="{H}" fill="{BG}"/>

  <!-- Neck (behind everything) -->
  <rect x="{CX - 38}" y="{HEAD_CY + HEAD_RY - 22}" width="76" height="85"
        rx="20" fill="{SKIN}" stroke="{OUTLINE}" stroke-width="2.5"/>

  <!-- Ears (behind head) -->
  <ellipse cx="{CX - HEAD_RX + 8}" cy="{ear_y}" rx="{ear_rx}" ry="{ear_ry}"
           fill="{SKIN}" stroke="{OUTLINE}" stroke-width="2.5"/>
  <ellipse cx="{CX + HEAD_RX - 8}" cy="{ear_y}" rx="{ear_rx}" ry="{ear_ry}"
           fill="{SKIN}" stroke="{OUTLINE}" stroke-width="2.5"/>

  <!-- Hair bulk: full ellipse clipped to above hairline (top of head + volume) -->
  <ellipse cx="{hair_ecx}" cy="{hair_ecy:.1f}" rx="{HAIR_RX}" ry="{HAIR_RY}"
           fill="url(#hairGrad)" clip-path="url(#hairClip)"/>

  <!-- Hair sides: small sideburn strips below hairline, outside face oval -->
  <!-- Left sideburn -->
  <ellipse cx="{CX - HEAD_RX + 4}" cy="{hair_hl_y + 28:.1f}"
           rx="18" ry="32"
           fill="url(#hairGrad)" clip-path="url(#hairSideClip)"/>
  <!-- Right sideburn -->
  <ellipse cx="{CX + HEAD_RX - 4}" cy="{hair_hl_y + 28:.1f}"
           rx="18" ry="32"
           fill="url(#hairGrad)" clip-path="url(#hairSideClip)"/>

  <!-- Hair highlight (sheen on top) -->
  <ellipse cx="{CX - 20}" cy="{hair_top_y + 30:.1f}" rx="38" ry="14"
           fill="white" fill-opacity="0.14" clip-path="url(#hairClip)"/>

  <!-- Hair texture lines (subtle strands) -->
  <g stroke="#2A1408" stroke-width="1.4" stroke-linecap="round" fill="none"
     stroke-opacity="0.35" clip-path="url(#hairClip)">
    <path d="M {CX - 50},{hair_top_y + 8:.1f} Q {CX - 30},{hair_top_y + 40:.1f} {CX - 60},{hair_hl_y - 10:.1f}"/>
    <path d="M {CX},{hair_top_y + 5:.1f}      Q {CX + 10},{hair_top_y + 50:.1f} {CX - 10},{hair_hl_y - 8:.1f}"/>
    <path d="M {CX + 50},{hair_top_y + 8:.1f} Q {CX + 30},{hair_top_y + 40:.1f} {CX + 55},{hair_hl_y - 10:.1f}"/>
  </g>

  <!-- Head oval (face skin) — drawn over the hair bottom edge to form clean hairline -->
  <ellipse cx="{CX}" cy="{HEAD_CY}" rx="{HEAD_RX}" ry="{HEAD_RY}"
           fill="url(#skinGrad)" stroke="{OUTLINE}" stroke-width="3"
           filter="url(#softShadow)"/>

  <!-- Hair outline stroke along hairline (crisp edge between hair and forehead) -->
  <!-- This is just the top arc of the head ellipse, traced in hair colour -->
  <ellipse cx="{CX}" cy="{HEAD_CY}" rx="{HEAD_RX}" ry="{HEAD_RY}"
           fill="none" stroke="{HAIR}" stroke-width="2.5"
           stroke-dasharray="1000"
           stroke-dashoffset="{int(math.pi * (HEAD_RX + HEAD_RY) * 0.55)}"
           clip-path="url(#hairClip)"/>

  <!-- Eyebrows -->
  <path d="M {CX - EYE_OFFSET - brow_len//2},{brow_y}
            Q {CX - EYE_OFFSET + 4},{brow_y - 8}
              {CX - EYE_OFFSET + brow_len//2},{brow_y + 2}"
        fill="none" stroke="{HAIR}" stroke-width="5" stroke-linecap="round"/>
  <path d="M {CX + EYE_OFFSET - brow_len//2},{brow_y + 2}
            Q {CX + EYE_OFFSET - 4},{brow_y - 8}
              {CX + EYE_OFFSET + brow_len//2},{brow_y}"
        fill="none" stroke="{HAIR}" stroke-width="5" stroke-linecap="round"/>

  <!-- Eyes: whites -->
  <ellipse cx="{CX - EYE_OFFSET}" cy="{EYE_Y}" rx="{EYE_RX}" ry="{EYE_RY}"
           fill="{EYE_WHITE}" stroke="{EYE_OUTLINE}" stroke-width="2.5"/>
  <ellipse cx="{CX + EYE_OFFSET}" cy="{EYE_Y}" rx="{EYE_RX}" ry="{EYE_RY}"
           fill="{EYE_WHITE}" stroke="{EYE_OUTLINE}" stroke-width="2.5"/>

  <!-- Irises -->
  <circle cx="{CX - EYE_OFFSET}" cy="{EYE_Y}" r="{IRIS_R}"
          fill="{EYE_IRIS}" stroke="{EYE_OUTLINE}" stroke-width="1.5"/>
  <circle cx="{CX + EYE_OFFSET}" cy="{EYE_Y}" r="{IRIS_R}"
          fill="{EYE_IRIS}" stroke="{EYE_OUTLINE}" stroke-width="1.5"/>

  <!-- Pupils -->
  <circle cx="{CX - EYE_OFFSET}" cy="{EYE_Y}" r="{PUPIL_R}" fill="{EYE_PUPIL}"/>
  <circle cx="{CX + EYE_OFFSET}" cy="{EYE_Y}" r="{PUPIL_R}" fill="{EYE_PUPIL}"/>

  <!-- Eye highlights -->
  <circle cx="{CX - EYE_OFFSET + 6}" cy="{EYE_Y - 6}" r="4" fill="white" fill-opacity="0.85"/>
  <circle cx="{CX + EYE_OFFSET + 6}" cy="{EYE_Y - 6}" r="4" fill="white" fill-opacity="0.85"/>

  <!-- Nose -->
  <ellipse cx="{NOSE_CX}" cy="{NOSE_CY}" rx="{NOSE_RX}" ry="{NOSE_RY}"
           fill="{SKIN_SHADOW}" stroke="{OUTLINE}" stroke-width="1.5" fill-opacity="0.6"/>
  <!-- Nostrils -->
  <ellipse cx="{NOSE_CX - 7}" cy="{NOSE_CY + 3}" rx="5" ry="3.5"
           fill="{OUTLINE}" fill-opacity="0.35"/>
  <ellipse cx="{NOSE_CX + 7}" cy="{NOSE_CY + 3}" rx="5" ry="3.5"
           fill="{OUTLINE}" fill-opacity="0.35"/>

  <!-- Cheek blush -->
  <ellipse cx="{CX - EYE_OFFSET - 8}" cy="{EYE_Y + 44}" rx="30" ry="17"
           fill="url(#cheekL)"/>
  <ellipse cx="{CX + EYE_OFFSET + 8}" cy="{EYE_Y + 44}" rx="30" ry="17"
           fill="url(#cheekR)"/>

  <!-- ── Mouth ── -->
"""

    # Mouth interior (cavity / tongue / teeth)
    if cavity:
        opacity = min(1.0, (jaw_open - 0.08) / 0.50) * 0.92
        svg += f'  <path d="{cavity}" fill="{MOUTH_DARK}" fill-opacity="{opacity:.2f}"/>\n'

    if tongue:
        svg += f'  <path d="{tongue}" fill="{TONGUE}" fill-opacity="0.90"/>\n'

    if teeth:
        svg += f'  <path d="{teeth}" fill="{TEETH}"/>\n'

    if t_lines:
        svg += f'  <path d="{t_lines}" fill="none" stroke="#D0CBC0" stroke-width="1.2" stroke-opacity="0.6"/>\n'

    # Lips
    svg += f'  <path d="{upper}" fill="{LIP_UPPER}" stroke="{OUTLINE}" stroke-width="2" stroke-linejoin="round"/>\n'
    svg += f'  <path d="{lower}" fill="{LIP_LOWER}" stroke="{OUTLINE}" stroke-width="2" stroke-linejoin="round"/>\n'

    # Lip highlight
    svg += f"""  <ellipse cx="{MOUTH_CX}" cy="{m['upper_top_y'] + 5:.1f}"
           rx="{(m['right_x'] - m['left_x']) * 0.20:.1f}" ry="3"
           fill="white" fill-opacity="0.30"/>
"""

    # Philtrum
    svg += f"""  <path d="M {philtrum_x - 5},{philtrum_top_y} L {philtrum_x - 3},{philtrum_bot_y}
            M {philtrum_x + 5},{philtrum_top_y} L {philtrum_x + 3},{philtrum_bot_y}"
        fill="none" stroke="{SKIN_SHADOW}" stroke-width="1.5" stroke-linecap="round" stroke-opacity="0.5"/>

  <!-- Label -->
  <text x="12" y="30" font-family="system-ui,sans-serif" font-size="18"
        font-weight="700" fill="{OUTLINE}" fill-opacity="0.55">{viseme_name}</text>
  <text x="12" y="50" font-family="system-ui,sans-serif" font-size="13"
        fill="{OUTLINE}" fill-opacity="0.35">{phoneme_label}</text>

</svg>"""
    return svg


# ─────────────────────────────────────────────────────────────────────────────
# Mouth-only SVG snippet  (for inline DOM-swap animation)
# ─────────────────────────────────────────────────────────────────────────────

def build_mouth_snippet(jaw_open: float, lip_spread: float,
                        lip_part: float) -> str:
    """
    Returns an SVG fragment (no wrapper) containing only the mouth elements.
    Safe to set as innerHTML of a <g id="mouth"> inside a larger SVG.
    """
    m = compute_mouth(jaw_open, lip_spread, lip_part)
    cavity  = mouth_cavity_path(m)
    upper   = upper_lip_path(m)
    lower   = lower_lip_path(m)
    teeth   = teeth_path(m)
    tongue  = tongue_path(m)
    t_lines = teeth_line_path(m)

    parts = []
    if cavity:
        opacity = min(1.0, (jaw_open - 0.08) / 0.50) * 0.92
        parts.append(f'<path d="{cavity}" fill="{MOUTH_DARK}" fill-opacity="{opacity:.2f}"/>')
    if tongue:
        parts.append(f'<path d="{tongue}" fill="{TONGUE}" fill-opacity="0.90"/>')
    if teeth:
        parts.append(f'<path d="{teeth}" fill="{TEETH}"/>')
    if t_lines:
        parts.append(f'<path d="{t_lines}" fill="none" stroke="#D0CBC0" stroke-width="1.2" stroke-opacity="0.6"/>')

    parts.append(f'<path d="{upper}" fill="{LIP_UPPER}" stroke="{OUTLINE}" stroke-width="2" stroke-linejoin="round"/>')
    parts.append(f'<path d="{lower}" fill="{LIP_LOWER}" stroke="{OUTLINE}" stroke-width="2" stroke-linejoin="round"/>')
    parts.append(
        f'<ellipse cx="{MOUTH_CX}" cy="{m["upper_top_y"] + 5:.1f}" '
        f'rx="{(m["right_x"] - m["left_x"]) * 0.20:.1f}" ry="3" '
        f'fill="white" fill-opacity="0.30"/>'
    )
    return "".join(parts)


def generate_mouth_data():
    """
    Writes outputs/svg_visemes/mouth_paths.json — a map of viseme ID → SVG
    fragment string containing only the mouth elements.  Used by demo.html
    for flicker-free DOM-swap animation.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for name, vdata in VISEMES.items():
        jaw, spread, part = vdata["shape"]
        data[name] = build_mouth_snippet(jaw, spread, part)
    out = OUTPUT_DIR / "mouth_paths.json"
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Mouth data written: {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Contact sheet (HTML — opens in any browser, no extra deps)
# ─────────────────────────────────────────────────────────────────────────────

def generate_contact_sheet_html(viseme_dir: Path = OUTPUT_DIR):
    rows = []
    for name, data in VISEMES.items():
        svg_path = viseme_dir / f"{name}.svg"
        if not svg_path.exists():
            continue
        phonemes = ", ".join(data["phonemes"][:3])
        jaw, spread, part = data["shape"]
        rows.append(f"""
      <div class="card">
        <img src="{name}.svg" alt="{name}"/>
        <div class="label">{name}</div>
        <div class="sub">{phonemes}</div>
        <div class="params">jaw={jaw:.2f} spr={spread:+.2f} pt={part:+.2f}</div>
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Viseme Contact Sheet</title>
  <style>
    body {{ background:#F0EDE8; font-family:system-ui,sans-serif; padding:20px; }}
    h1   {{ color:#2A1A0A; margin-bottom:16px; }}
    .grid {{ display:flex; flex-wrap:wrap; gap:12px; }}
    .card {{ background:white; border-radius:12px; padding:8px;
             box-shadow:0 2px 8px #0002; text-align:center; width:160px; }}
    .card img {{ width:140px; height:140px; }}
    .label {{ font-weight:700; font-size:15px; color:#2A1A0A; margin-top:4px; }}
    .sub   {{ font-size:12px; color:#888; }}
    .params {{ font-size:10px; color:#aaa; margin-top:2px; font-family:monospace; }}
  </style>
</head>
<body>
  <h1>Viseme Contact Sheet — {len(rows)} frames</h1>
  <div class="grid">{"".join(rows)}
  </div>
</body>
</html>"""

    out = viseme_dir / "contact_sheet.html"
    out.write_text(html)
    print(f"Contact sheet: {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SVG cartoon viseme generator")
    parser.add_argument("--mode", required=True,
                        choices=["visemes", "sheet", "all", "mouth-data"])
    parser.add_argument("--open", action="store_true",
                        help="Open contact sheet in browser after generating")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode in ("visemes", "all"):
        total = len(VISEMES)
        for i, (name, data) in enumerate(VISEMES.items(), 1):
            jaw, spread, part = data["shape"]
            print(f"[{i:2d}/{total}] {name:4s}  "
                  f"jaw={jaw:.2f}  spread={spread:+.2f}  part={part:+.2f}")
            svg = build_face_svg(name, jaw, spread, part)
            out = OUTPUT_DIR / f"{name}.svg"
            out.write_text(svg)
        print(f"\nAll {total} SVG visemes saved to {OUTPUT_DIR}/")

    if args.mode in ("sheet", "all"):
        out = generate_contact_sheet_html()
        if args.open:
            import subprocess
            subprocess.run(["open", str(out)], check=False)

    if args.mode == "mouth-data":
        generate_mouth_data()

    if args.mode == "sheet" and not any((OUTPUT_DIR / f"{n}.svg").exists() for n in VISEMES):
        print("No SVG files found — run --mode visemes first")


if __name__ == "__main__":
    main()
