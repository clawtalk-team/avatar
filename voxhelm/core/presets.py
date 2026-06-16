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
}


def list_presets() -> dict[str, str]:
    """Return all preset names and their style descriptions."""
    return dict(PRESETS)


def get_preset(name: str) -> str:
    """Return the style description for a preset. Raises KeyError if not found."""
    return PRESETS[name]
