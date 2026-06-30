"""Bundled character presets for SVG head generation."""

PRESETS: dict[str, str] = {
    "young_man": (
        "young man in his mid-20s, short dark hair, light skin, clean-shaven, "
        "bright eyes, friendly cartoon, flat design, warm colours"
    ),
    "middle_man": (
        "middle-aged man in his 40s, salt-and-pepper stubble, medium-brown skin, "
        "slight smile lines, professional cartoon, flat design"
    ),
    "older_man": (
        "elderly man in his 70s, white hair, weathered warm skin, kind deep-set eyes, "
        "gentle expression, cartoon, flat design"
    ),
    "young_woman": (
        "young woman in her mid-20s, long auburn hair, fair freckled skin, "
        "wide expressive eyes, cheerful cartoon, flat design, warm colours"
    ),
    "middle_woman": (
        "middle-aged woman in her 40s, shoulder-length dark hair with grey streaks, "
        "medium-brown skin, warm smile, cartoon, flat design"
    ),
    "older_woman": (
        "elderly woman in her 70s, silver bun, light wrinkled skin, rosy cheeks, "
        "warm grandmotherly expression, cartoon, flat design"
    ),
    # ── Photorealistic humans (use with --mode photo) ────────────────────────
    "photo_man": (
        "clean-cut Caucasian man in his late 30s, short brown hair, light stubble, "
        "blue eyes, neutral studio lighting, sharp focus, photorealistic headshot, "
        "front-facing"
    ),
    "photo_woman": (
        "Caucasian woman in her early 30s, fair skin, shoulder-length blonde hair, "
        "green eyes, soft natural lighting, photorealistic headshot, front-facing"
    ),
    # ── Fun robots / humanoids ───────────────────────────────────────────────
    "chrome_bot": (
        "friendly retro robot, rounded chrome head, glowing blue oval eyes, "
        "antenna with a little bulb, riveted metal panels, expressive cartoon mouth, "
        "flat design, warm colours"
    ),
    "bolt_bot": (
        "cheerful robot, pastel-mint rounded head, big heart-shaped LED eyes, "
        "two side antennae with bows, soft matte plating, friendly cartoon, "
        "flat design, warm colours"
    ),
    "mossling": (
        "friendly forest sprite, round leafy-green face, large amber eyes, "
        "tiny flower buds for hair, rosy cheeks, gentle cartoon, flat design, "
        "warm colours"
    ),
    "clayton": (
        "good-natured clay golem, warm terracotta head, big round eyes, "
        "chunky simple features, soft thumb-print texture, cartoon, flat design, "
        "warm colours"
    ),
    "nimbus": (
        "cute blue cloud genie, fluffy round head, swirling wisp on top, "
        "wide white eyes, friendly grin, cartoon, flat design, cool blue palette"
    ),
    # ── Non-human (anthropomorphic face for human viseme mouth-swap) ──────────
    "clawford": (
        "anthropomorphic cartoon lobster, glossy red-orange shell head, two large "
        "forward-facing cartoon eyes set side by side, expressive eyebrows above them, "
        "small claws framing the face, and a human-style lipped mouth (visible lips, "
        "teeth and tongue) centered where a mouth belongs — NOT real lobster mandibles "
        "— so the standard viseme mouth-swap maps correctly; friendly cartoon, "
        "flat design, warm colours"
    ),
}


def list_presets() -> dict[str, str]:
    """Return all preset names and their style descriptions."""
    return dict(PRESETS)


def get_preset(name: str) -> str:
    """Return the style description for a preset. Raises KeyError if not found."""
    return PRESETS[name]
