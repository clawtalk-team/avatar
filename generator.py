#!/usr/bin/env python3
"""
viseme_generator.py  —  geometric warp edition
-----------------------------------------------
Generates 15 viseme face frames by warping the base face's mouth region
geometrically.  No AI generation for visemes — same pixels, just moved.

Identity is perfect by construction: every frame is the original face with
its mouth/jaw displaced toward the target shape.

Steps:
  1. Generate a base face  (one-time, uses Stable Diffusion)
     python generator.py --mode base --prompt "young woman, brown hair"

  2. Generate viseme frames  (fast, <30 s total)
     python generator.py --mode visemes --base outputs/base_face.png

  3. Preview contact sheet
     python generator.py --mode sheet

Dependencies already in .venv:
    opencv-python, numpy, pillow, scipy, mediapipe
"""

import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


# ─────────────────────────────────────────────────────────────────────────────
# Viseme shapes
#
# Each entry is (jaw_open, lip_spread, lip_part):
#   jaw_open   0.0 = jaw up/closed  →  1.0 = jaw fully dropped
#   lip_spread -1.0 = pursed tight  →  0.0 = neutral  →  1.0 = wide smile
#   lip_part   0.0 = lips touching  →  1.0 = lips maximally parted
#              negative = lips pressed together
# ─────────────────────────────────────────────────────────────────────────────

VISEMES = {
    "sil": {"phonemes": ["silence"],          "shape": ( 0.00,  0.00,  0.00)},
    "PP":  {"phonemes": ["p","b","m"],         "shape": ( 0.00,  0.00, -0.20)},  # pressed
    "FF":  {"phonemes": ["f","v"],             "shape": ( 0.05,  0.15,  0.20)},  # teeth-lip
    "TH":  {"phonemes": ["th","dh"],           "shape": ( 0.10,  0.00,  0.30)},
    "DD":  {"phonemes": ["t","d"],             "shape": ( 0.15,  0.10,  0.30)},
    "kk":  {"phonemes": ["k","g"],             "shape": ( 0.20,  0.00,  0.25)},
    "CH":  {"phonemes": ["ch","j","sh","zh"],  "shape": ( 0.12, -0.35,  0.28)},  # rounded
    "SS":  {"phonemes": ["s","z"],             "shape": ( 0.05,  0.50,  0.12)},  # spread
    "nn":  {"phonemes": ["n","l","ng"],        "shape": ( 0.10,  0.05,  0.20)},
    "RR":  {"phonemes": ["r"],                 "shape": ( 0.15, -0.28,  0.25)},  # slightly pursed
    "aa":  {"phonemes": ["ah","aa","ae"],      "shape": ( 0.85,  0.15,  0.80)},  # wide open!
    "E":   {"phonemes": ["eh","ey"],           "shape": ( 0.40,  0.30,  0.50)},
    "ih":  {"phonemes": ["ih","iy"],           "shape": ( 0.05,  0.55,  0.10)},  # spread near-close
    "oh":  {"phonemes": ["oh","ao","ow"],      "shape": ( 0.45, -0.40,  0.52)},  # O-shape
    "ou":  {"phonemes": ["oo","uw","uh"],      "shape": ( 0.18, -0.65,  0.28)},  # pursed tight
}

OUTPUT_DIR = Path("outputs/visemes")
MEDIAPIPE_MODEL_PATH = Path("models/face_landmarker.task")
MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


# ─────────────────────────────────────────────────────────────────────────────
# Face / landmark detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_face_rect(image: np.ndarray) -> tuple:
    """Returns (x, y, w, h) of the largest detected face, or full-image fallback."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=4, minSize=(60, 60)
    )
    if len(faces) == 0:
        h, w = image.shape[:2]
        m = int(min(w, h) * 0.08)
        print("  No face detected — using full-image estimate")
        return (m, m, w - 2 * m, h - 2 * m)
    return max(faces, key=lambda f: f[2] * f[3])


def get_landmarks_mediapipe(image: np.ndarray):
    """
    Returns list of (x, y) pixel coords for all 478 MediaPipe face landmarks,
    or None if unavailable.
    """
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        if not MEDIAPIPE_MODEL_PATH.exists():
            print(f"  Downloading face landmarker model (~3 MB)…")
            MEDIAPIPE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MEDIAPIPE_MODEL_URL, MEDIAPIPE_MODEL_PATH)
            print("  Download complete.")

        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=str(MEDIAPIPE_MODEL_PATH)
            ),
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        with mp_vision.FaceLandmarker.create_from_options(options) as detector:
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            result = detector.detect(mp_img)

        if not result.face_landmarks:
            print("  MediaPipe found no face landmarks")
            return None

        h, w = image.shape[:2]
        # Clamp to image bounds (normalized coords can slightly exceed [0,1])
        return [(min(max(lm.x * w, 0), w - 1),
                 min(max(lm.y * h, 0), h - 1))
                for lm in result.face_landmarks[0]]

    except Exception as exc:
        print(f"  MediaPipe Tasks unavailable ({exc}), using geometric fallback")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Mouth geometry
# ─────────────────────────────────────────────────────────────────────────────

# MediaPipe 478-point mesh indices used for mouth control
_MP_LEFT_CORNER  = 61
_MP_RIGHT_CORNER = 291
_MP_UPPER_TOP    = 0     # outermost top of upper lip
_MP_LOWER_BOT    = 17    # outermost bottom of lower lip
_MP_INNER_UPPER  = 13    # inner upper lip center
_MP_INNER_LOWER  = 14    # inner lower lip center
_MP_CHIN         = 152
_MP_UPPER_LEFT   = 39    # upper lip left of center
_MP_UPPER_RIGHT  = 269   # upper lip right of center
_MP_LOWER_LEFT   = 91    # lower lip left of center
_MP_LOWER_RIGHT  = 321   # lower lip right of center
# Anchors — nose bridge, cheeks, forehead
_MP_NOSE_TIP     = 1
_MP_LEFT_CHEEK   = 234
_MP_RIGHT_CHEEK  = 454
_MP_FOREHEAD     = 10
_MP_PHILTRUM_L   = 92
_MP_PHILTRUM_R   = 322


class MouthGeometry:
    """
    Defines the mouth control points and anchor points used for warping.
    Can be built from precise MediaPipe landmarks or estimated from face bbox.
    """

    def __init__(self, mouth_ctrl: np.ndarray, anchors: np.ndarray,
                 mw: float, mh: float, fh: float):
        # mouth_ctrl: (9, 2) array of control points in source image
        #   [0] left_corner
        #   [1] right_corner
        #   [2] upper_center
        #   [3] lower_center
        #   [4] chin
        #   [5] upper_left
        #   [6] upper_right
        #   [7] lower_left
        #   [8] lower_right
        self._src = mouth_ctrl.copy()
        self.anchors = anchors.copy()
        self.mw = mw   # half mouth width
        self.mh = mh   # half mouth height (neutral)
        self.fh = fh   # face height

    @classmethod
    def from_mediapipe(cls, landmarks, image_shape):
        """Build from MediaPipe 478-point landmarks."""
        def pt(idx):
            return np.array(landmarks[idx], dtype=np.float64)

        left_corner  = pt(_MP_LEFT_CORNER)
        right_corner = pt(_MP_RIGHT_CORNER)
        upper_center = pt(_MP_UPPER_TOP)
        lower_center = pt(_MP_LOWER_BOT)
        chin         = pt(_MP_CHIN)
        upper_left   = pt(_MP_UPPER_LEFT)
        upper_right  = pt(_MP_UPPER_RIGHT)
        lower_left   = pt(_MP_LOWER_LEFT)
        lower_right  = pt(_MP_LOWER_RIGHT)

        anchors = np.array([
            pt(_MP_NOSE_TIP),
            pt(_MP_LEFT_CHEEK),
            pt(_MP_RIGHT_CHEEK),
            pt(_MP_FOREHEAD),
            pt(_MP_PHILTRUM_L),
            pt(_MP_PHILTRUM_R),
        ])

        ctrl = np.array([left_corner, right_corner,
                         upper_center, lower_center, chin,
                         upper_left, upper_right,
                         lower_left, lower_right])

        mw = (right_corner[0] - left_corner[0]) / 2.0
        mh = (lower_center[1] - upper_center[1]) / 2.0
        # estimate face height from chin to forehead
        fh = abs(pt(_MP_CHIN)[1] - pt(_MP_FOREHEAD)[1])

        return cls(ctrl, anchors, mw, mh, fh)

    @classmethod
    def from_face_rect(cls, face_rect, image_shape):
        """Estimate mouth geometry from Haar-cascade face bounding box."""
        fx, fy, fw, fh = face_rect
        cx = fx + fw / 2.0

        mouth_cy = fy + fh * 0.69   # mouth center ≈ 69% down face
        mw = fw * 0.27              # half mouth width
        mh = fw * 0.055             # half mouth height (neutral)

        left_corner  = np.array([cx - mw,       mouth_cy],          dtype=np.float64)
        right_corner = np.array([cx + mw,       mouth_cy],          dtype=np.float64)
        upper_center = np.array([cx,            mouth_cy - mh * 0.8], dtype=np.float64)
        lower_center = np.array([cx,            mouth_cy + mh * 0.8], dtype=np.float64)
        chin         = np.array([cx,            fy + fh * 0.91],    dtype=np.float64)
        upper_left   = np.array([cx - mw * 0.55, mouth_cy - mh * 0.5], dtype=np.float64)
        upper_right  = np.array([cx + mw * 0.55, mouth_cy - mh * 0.5], dtype=np.float64)
        lower_left   = np.array([cx - mw * 0.55, mouth_cy + mh * 0.5], dtype=np.float64)
        lower_right  = np.array([cx + mw * 0.55, mouth_cy + mh * 0.5], dtype=np.float64)

        anchors = np.array([
            [cx,              fy + fh * 0.10],           # forehead
            [fx + fw * 0.05,  fy + fh * 0.50],           # left cheek far
            [fx + fw * 0.95,  fy + fh * 0.50],           # right cheek far
            [cx,              fy + fh * 0.44],            # nose tip
            [cx - mw * 0.5,  fy + fh * 0.58],            # philtrum left
            [cx + mw * 0.5,  fy + fh * 0.58],            # philtrum right
        ], dtype=np.float64)

        ctrl = np.array([left_corner, right_corner,
                         upper_center, lower_center, chin,
                         upper_left, upper_right,
                         lower_left, lower_right])

        return cls(ctrl, anchors, mw, mh, float(fh))

    def source_points(self) -> np.ndarray:
        return self._src.copy()

    def target_points(self, jaw_open: float, lip_spread: float,
                      lip_part: float) -> np.ndarray:
        """
        Compute displaced control points for a given viseme shape.

        jaw_open   0→1  lower jaw drops
        lip_spread -1→1 corners spread (positive) or pucker (negative)
        lip_part   -1→1 lips open (positive) or press together (negative)
        """
        mw, mh, fh = self.mw, self.mh, self.fh
        src = self._src

        # ── jaw drop ──────────────────────────────────────────────────────
        jaw_dy = jaw_open * fh * 0.13

        # ── horizontal spread / pucker ───────────────────────────────────
        spread_dx = lip_spread * mw * 0.32

        # ── lip parting / pressing ───────────────────────────────────────
        if lip_part >= 0:
            upper_dy_part = -lip_part * mh * 0.30   # upper lip lifts
            lower_dy_part =  lip_part * mh * 0.55   # lower lip lowers
        else:
            # negative = lips press together
            upper_dy_part = -lip_part * mh * 0.12   # upper lip pushes down
            lower_dy_part =  lip_part * mh * 0.20   # lower lip pushes up

        # ── slight upward bulge on upper lip when pursed ─────────────────
        pucker_upper_dy = max(0.0, -lip_spread) * mh * 0.18

        left_corner  = src[0] + [-spread_dx,          jaw_dy * 0.25]
        right_corner = src[1] + [ spread_dx,          jaw_dy * 0.25]
        upper_center = src[2] + [0,  upper_dy_part  + pucker_upper_dy]
        lower_center = src[3] + [0,  jaw_dy         + lower_dy_part]
        chin         = src[4] + [0,  jaw_dy * 0.55]

        upper_left  = src[5] + [-spread_dx * 0.45,
                                  upper_dy_part * 0.65 + jaw_dy * 0.08]
        upper_right = src[6] + [ spread_dx * 0.45,
                                  upper_dy_part * 0.65 + jaw_dy * 0.08]
        lower_left  = src[7] + [-spread_dx * 0.30,
                                  jaw_dy * 0.60         + lower_dy_part * 0.50]
        lower_right = src[8] + [ spread_dx * 0.30,
                                  jaw_dy * 0.60         + lower_dy_part * 0.50]

        return np.array([left_corner, right_corner,
                         upper_center, lower_center, chin,
                         upper_left, upper_right,
                         lower_left, lower_right])


# ─────────────────────────────────────────────────────────────────────────────
# Thin-plate-spline warp
# ─────────────────────────────────────────────────────────────────────────────

def _build_remap(dst_pts: np.ndarray, src_pts: np.ndarray,
                 image_shape: tuple) -> tuple:
    """
    Compute (map_x, map_y) for cv2.remap using inverse TPS.

    For each pixel position p in the *output* image, the maps tell
    cv2.remap which pixel in the *source* image to sample.

    We fit a thin-plate-spline: dst_pts → src_pts (inverse mapping),
    plus fixed image-border anchors so everything outside the mouth
    is perfectly unchanged.
    """
    from scipy.interpolate import RBFInterpolator

    h, w = image_shape[:2]

    # Fixed border anchors — corners and edge midpoints
    border = np.array([
        [0, 0],        [w // 4, 0],    [w // 2, 0],    [3 * w // 4, 0],    [w - 1, 0],
        [0, h // 4],   [w - 1, h // 4],
        [0, h // 2],   [w - 1, h // 2],
        [0, 3*h//4],   [w - 1, 3*h//4],
        [0, h - 1],    [w // 4, h-1],  [w // 2, h-1],  [3*w//4, h-1],  [w-1, h-1],
    ], dtype=np.float64)

    dst_all = np.vstack([dst_pts, border])
    src_all = np.vstack([src_pts, border])

    # Fit inverse TPS: output position → source position
    rbf = RBFInterpolator(dst_all, src_all, kernel="thin_plate_spline", smoothing=0)

    yy, xx = np.mgrid[0:h, 0:w]
    query = np.column_stack([xx.ravel().astype(np.float64),
                             yy.ravel().astype(np.float64)])
    coords = rbf(query)   # (h*w, 2)

    map_x = coords[:, 0].reshape(h, w).astype(np.float32)
    map_y = coords[:, 1].reshape(h, w).astype(np.float32)
    return map_x, map_y


def warp_to_viseme(image: np.ndarray, geom: MouthGeometry,
                   jaw_open: float, lip_spread: float,
                   lip_part: float) -> np.ndarray:
    src_pts = np.vstack([geom.source_points(), geom.anchors])
    dst_pts = np.vstack([geom.target_points(jaw_open, lip_spread, lip_part),
                         geom.anchors])
    map_x, map_y = _build_remap(dst_pts, src_pts, image.shape)
    return cv2.remap(image, map_x, map_y, cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_REFLECT_101)


# ─────────────────────────────────────────────────────────────────────────────
# Mouth cavity overlay
# ─────────────────────────────────────────────────────────────────────────────

def _add_mouth_cavity(image: np.ndarray, dst_pts: np.ndarray,
                       jaw_open: float) -> np.ndarray:
    """
    Paint a dark mouth cavity between the warped lip positions.

    Geometric warping moves the jaw and lips but can't reveal the interior
    of the mouth (teeth, darkness) when starting from a closed-mouth face.
    This function composites a soft dark ellipse in the opened gap, scaled
    by jaw_open so it's invisible at small openings and prominent at aa/oh.
    """
    h, w = image.shape[:2]

    # Warped control point indices (same order as MouthGeometry):
    # 0=left_corner, 1=right_corner, 2=upper_center, 3=lower_center, 4=chin
    left_c  = dst_pts[0]
    right_c = dst_pts[1]
    upper_c = dst_pts[2]
    lower_c = dst_pts[3]

    cx = int((left_c[0] + right_c[0]) / 2)
    cy = int((upper_c[1] + lower_c[1]) / 2)

    # Ellipse axes — width spans mouth corners, height spans lip gap
    half_w = max(4, int((right_c[0] - left_c[0]) * 0.80))
    half_h = max(2, int((lower_c[1] - upper_c[1]) * 0.85))

    if half_h < 3:
        return image  # gap too small to paint

    # Build soft alpha mask: full ellipse then Gaussian-blurred edge
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(mask, (cx, cy), (half_w, half_h), 0, 0, 360, 1.0, -1)
    blur_k = max(3, (min(half_w, half_h) // 3) * 2 + 1)  # must be odd
    mask = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)

    # Dark mouth interior colour — very dark warm shadow
    mouth_dark = np.array([28, 18, 18], dtype=np.float32)

    # Scale opacity by jaw_open (subtle at 0.12, strong at 0.85)
    opacity = min(1.0, (jaw_open - 0.12) / 0.50) * 0.88

    alpha = mask[:, :, np.newaxis] * opacity
    result = image.astype(np.float32) * (1 - alpha) + mouth_dark * alpha
    return result.clip(0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# Viseme generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_visemes(base_image_path: str, size: int = 512,
                         debug: bool = False):
    """
    Warp the base face into all 15 viseme positions.
    Fast (<30 s), identity-perfect — uses only the original face pixels.
    Processes at native image resolution, then downscales to `size` for output.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Work at native resolution so landmarks aren't clipped by downscaling
    base_img_native = Image.open(base_image_path).convert("RGB")
    native_w, native_h = base_img_native.size
    base_arr = np.array(base_img_native)
    print(f"Loaded base face: {base_image_path} ({native_w}×{native_h})")

    # ── Detect landmarks ────────────────────────────────────────────────────
    print("Detecting face landmarks…")
    landmarks = get_landmarks_mediapipe(base_arr)

    if landmarks is not None:
        print("  Using MediaPipe face landmarks (precise)")
        geom = MouthGeometry.from_mediapipe(landmarks, base_arr.shape)
    else:
        face_rect = detect_face_rect(base_arr)
        print(f"  Using geometric estimate (face rect {face_rect})")
        geom = MouthGeometry.from_face_rect(face_rect, base_arr.shape)

    # ── Optional debug: show control points ─────────────────────────────────
    if debug:
        _save_debug_overlay(base_img_native, geom, OUTPUT_DIR / "debug_landmarks.png")

    # ── Generate each viseme ────────────────────────────────────────────────
    metadata = {"base_image": base_image_path, "visemes": {}}
    total = len(VISEMES)

    for i, (name, data) in enumerate(VISEMES.items(), 1):
        jaw_open, lip_spread, lip_part = data["shape"]
        print(f"[{i:2d}/{total}] {name:4s}  "
              f"jaw={jaw_open:.2f}  spread={lip_spread:+.2f}  part={lip_part:+.2f}")

        warped = warp_to_viseme(base_arr, geom, jaw_open, lip_spread, lip_part)

        # Add mouth cavity for open-mouth visemes
        if jaw_open > 0.12:
            dst_pts = geom.target_points(jaw_open, lip_spread, lip_part)
            warped = _add_mouth_cavity(warped, dst_pts, jaw_open)

        out_path = OUTPUT_DIR / f"{name}.png"
        # Downscale to target size for output
        out_img = Image.fromarray(warped)
        if out_img.size != (size, size):
            out_img = out_img.resize((size, size), Image.LANCZOS)
        out_img.save(out_path)

        metadata["visemes"][name] = {
            "path": str(out_path),
            "phonemes": data["phonemes"],
            "shape": data["shape"],
        }

    with open(OUTPUT_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nAll {total} visemes saved to {OUTPUT_DIR}/")


# ─────────────────────────────────────────────────────────────────────────────
# Contact sheet
# ─────────────────────────────────────────────────────────────────────────────

def generate_contact_sheet(viseme_dir: Path = OUTPUT_DIR, cols: int = 5,
                            thumb: int = 200):
    """Tile all viseme frames into a single preview image."""
    frames = {}
    for name in VISEMES:
        p = viseme_dir / f"{name}.png"
        if p.exists():
            frames[name] = Image.open(p).convert("RGB").resize((thumb, thumb))

    if not frames:
        print("No viseme frames found — run --mode visemes first")
        return

    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows * (thumb + 22)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)

    for i, (name, img) in enumerate(frames.items()):
        c, r = i % cols, i // cols
        x, y = c * thumb, r * (thumb + 22) + 22
        sheet.paste(img, (x, y))
        phonemes = ", ".join(VISEMES[name]["phonemes"][:3])
        draw.text((x + 4, r * (thumb + 22) + 3), f"{name}: {phonemes}",
                  fill=(200, 200, 200))

    out = viseme_dir / "contact_sheet.png"
    sheet.save(out)
    print(f"Contact sheet saved: {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Debug overlay
# ─────────────────────────────────────────────────────────────────────────────

def _save_debug_overlay(base_img: Image.Image, geom: MouthGeometry,
                         out_path: Path):
    """Save base face with control points drawn for visual verification."""
    img = base_img.copy().convert("RGB")
    draw = ImageDraw.Draw(img)

    src = geom.source_points()
    labels = ["L-corner", "R-corner", "Upper-C", "Lower-C", "Chin",
              "UL", "UR", "LL", "LR"]
    for pt, label in zip(src, labels):
        x, y = int(pt[0]), int(pt[1])
        draw.ellipse([x-5, y-5, x+5, y+5], fill=(255, 80, 80))
        draw.text((x + 7, y - 6), label, fill=(255, 220, 50))

    for pt in geom.anchors:
        x, y = int(pt[0]), int(pt[1])
        draw.ellipse([x-4, y-4, x+4, y+4], fill=(80, 180, 255))

    img.save(out_path)
    print(f"  Debug overlay saved: {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Base face generation  (Stable Diffusion — one-time only)
# ─────────────────────────────────────────────────────────────────────────────

def generate_base_face(prompt: str, seed: int = 42, size: int = 512,
                        output_path: str = "outputs/base_face.png"):
    """Generate a single front-facing base face with Stable Diffusion."""
    import torch
    from diffusers import StableDiffusionPipeline

    device = ("cuda" if torch.cuda.is_available()
              else "mps" if torch.backends.mps.is_available()
              else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"Loading SD pipeline on {device}…")
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5", torch_dtype=dtype
    ).to(device)
    pipe.enable_attention_slicing()

    generator = torch.Generator(device=device).manual_seed(seed)

    full_prompt = (
        f"front-facing portrait photo of a {prompt}, "
        "mouth closed, neutral expression, looking directly at camera, "
        "face centered, symmetrical, plain light background, "
        "head and shoulders, professional studio lighting, sharp focus, 8k"
    )
    neg = (
        "blurry, low quality, distorted, asymmetric, deformed, cartoon, anime, "
        "painting, watermark, text, side view, profile, angled, looking away"
    )

    result = pipe(full_prompt, negative_prompt=neg,
                  width=size, height=size,
                  num_inference_steps=30, guidance_scale=7.5,
                  generator=generator)

    image = result.images[0]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    print(f"Base face saved: {output_path}")
    return image


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Viseme face frame generator")
    parser.add_argument("--mode", required=True,
                        choices=["base", "visemes", "sheet"])
    parser.add_argument("--base", default="outputs/base_face.png",
                        help="Path to base face image")
    parser.add_argument("--prompt", default="person with neutral expression",
                        help="Face description (--mode base only)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--debug", action="store_true",
                        help="Save control-point overlay for verification")
    args = parser.parse_args()

    if args.mode == "base":
        generate_base_face(prompt=args.prompt, seed=args.seed,
                           size=args.size, output_path=args.base)

    elif args.mode == "visemes":
        generate_all_visemes(base_image_path=args.base, size=args.size,
                             debug=args.debug)

    elif args.mode == "sheet":
        generate_contact_sheet()


if __name__ == "__main__":
    main()
