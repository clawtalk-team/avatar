# Viseme Generator

Generates all 15 phoneme face frames using Stable Diffusion inpainting.
Identity is locked via ControlNet + same seed. Only the mouth region changes.

## Install

```bash
pip install diffusers transformers accelerate torch torchvision
pip install opencv-python pillow scikit-image mediapipe numpy
pip install gfpgan  # optional — face restoration
```

Needs ~6GB VRAM for GPU, runs on CPU/MPS too (slower).

## Usage

### Step 1 — Generate a base face

```bash
python viseme_generator.py \
  --mode base \
  --prompt "young woman, brown hair, blue eyes" \
  --seed 42
# → outputs/base_face.png
```

### Step 2 — Generate all 15 viseme frames

```bash
python viseme_generator.py \
  --mode visemes \
  --base outputs/base_face.png \
  --prompt "young woman, brown hair, blue eyes" \
  --seed 42
# → outputs/visemes/sil.png, PP.png, FF.png ... (15 files)
```

### Step 3 — Post-process (color match)

```bash
python viseme_generator.py \
  --mode postprocess \
  --base outputs/base_face.png
# → outputs/visemes/final/*.png  (color-matched)
```

### Step 4 — Preview contact sheet

```bash
python viseme_generator.py --mode sheet
# → outputs/visemes/contact_sheet.png
```

## Output structure

```
outputs/
  base_face.png              ← your character reference
  visemes/
    mouth_mask.png           ← the inpainting mask (check this looks right)
    pose_reference.png       ← ControlNet conditioning
    sil.png                  ← silence
    PP.png                   ← p, b, m
    FF.png                   ← f, v
    TH.png                   ← th
    DD.png                   ← t, d
    kk.png                   ← k, g
    CH.png                   ← ch, sh, j
    SS.png                   ← s, z
    nn.png                   ← n, l, ng
    RR.png                   ← r
    aa.png                   ← ah (wide open)
    E.png                    ← eh
    ih.png                   ← ih (nearly closed)
    oh.png                   ← oh (rounded)
    ou.png                   ← oo (pursed)
    contact_sheet.png        ← preview of all frames
    metadata.json            ← generation settings
    final/                   ← color-matched final frames
```

## Tips

- Check `mouth_mask.png` before generating — if it’s wrong, adjust
  `MOUTH_REGION` constants in the script for your face framing
- `--no-controlnet` is faster but less consistent across frames
- Higher `--seed` variation = more natural looking but less consistent
- If faces look too similar, increase `strength` in `generate_viseme_frame()`
- If faces drift too much, decrease `strength`

## Copy finals to Flutter

```bash
cp outputs/visemes/final/*.png your_flutter_app/assets/visemes/
```