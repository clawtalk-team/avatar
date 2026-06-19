"""Tests for voxhelm.core.animations."""

from voxhelm.core.animations import (
    AnimationMode,
    AnimationSequence,
    AnimationKeyframe,
    NEUTRAL,
    ANIMATIONS,
    IDLE_SEQUENCE,
    LISTENING_SEQUENCE,
    THINKING_SEQUENCE,
    get_animation,
    get_all_animations,
    interpolate_transform,
    sample_animation,
)


# ── Mode enum ────────────────────────────────────────────────────────────────

def test_animation_mode_values():
    assert AnimationMode.IDLE.value == "idle"
    assert AnimationMode.LISTENING.value == "listening"
    assert AnimationMode.THINKING.value == "thinking"


def test_animation_mode_from_string():
    assert AnimationMode("idle") == AnimationMode.IDLE
    assert AnimationMode("listening") == AnimationMode.LISTENING
    assert AnimationMode("thinking") == AnimationMode.THINKING


# ── All three sequences are registered ───────────────────────────────────────

def test_all_three_modes_registered():
    assert len(ANIMATIONS) == 3
    assert AnimationMode.IDLE in ANIMATIONS
    assert AnimationMode.LISTENING in ANIMATIONS
    assert AnimationMode.THINKING in ANIMATIONS


def test_get_animation_by_enum():
    assert get_animation(AnimationMode.IDLE) is IDLE_SEQUENCE
    assert get_animation(AnimationMode.LISTENING) is LISTENING_SEQUENCE
    assert get_animation(AnimationMode.THINKING) is THINKING_SEQUENCE


def test_get_animation_by_string():
    assert get_animation("idle") is IDLE_SEQUENCE
    assert get_animation("thinking") is THINKING_SEQUENCE


# ── Sequence structure ───────────────────────────────────────────────────────

def test_sequences_have_positive_duration():
    for mode, seq in ANIMATIONS.items():
        assert seq.duration_ms > 0, f"{mode} has non-positive duration"


def test_sequences_start_at_zero():
    for mode, seq in ANIMATIONS.items():
        assert seq.keyframes[0].t == 0.0, f"{mode} doesn't start at t=0"


def test_sequences_end_at_one():
    for mode, seq in ANIMATIONS.items():
        assert seq.keyframes[-1].t == 1.0, f"{mode} doesn't end at t=1"


def test_sequences_start_neutral():
    """Every sequence starts at the neutral pose for seamless mode switching."""
    for mode, seq in ANIMATIONS.items():
        kf = seq.keyframes[0]
        for gid, transform in kf.groups.items():
            assert transform == NEUTRAL, (
                f"{mode} group '{gid}' at t=0 is not neutral: {transform}"
            )


def test_sequences_end_neutral():
    """Every sequence ends at the neutral pose for seamless looping."""
    for mode, seq in ANIMATIONS.items():
        kf = seq.keyframes[-1]
        for gid, transform in kf.groups.items():
            assert transform == NEUTRAL, (
                f"{mode} group '{gid}' at t=1 is not neutral: {transform}"
            )


def test_sequences_have_all_four_groups():
    """Every keyframe should define transforms for head, eyes, brows, mouth."""
    required = {"head", "eyes", "brows", "mouth"}
    for mode, seq in ANIMATIONS.items():
        for kf in seq.keyframes:
            assert required <= set(kf.groups.keys()), (
                f"{mode} keyframe t={kf.t} missing groups: "
                f"{required - set(kf.groups.keys())}"
            )


def test_keyframes_monotonically_increasing():
    for mode, seq in ANIMATIONS.items():
        for i in range(1, len(seq.keyframes)):
            assert seq.keyframes[i].t > seq.keyframes[i - 1].t, (
                f"{mode} keyframes not monotonic at index {i}"
            )


def test_each_sequence_has_at_least_four_keyframes():
    """Need enough keyframes for meaningful motion."""
    for mode, seq in ANIMATIONS.items():
        assert len(seq.keyframes) >= 4, (
            f"{mode} has only {len(seq.keyframes)} keyframes"
        )


# ── Interpolation ────────────────────────────────────────────────────────────

def test_interpolate_at_zero():
    a = {"tx": 0, "ty": 0, "r": 0, "sx": 1.0, "sy": 1.0}
    b = {"tx": 10, "ty": 5, "r": 2.0, "sx": 1.1, "sy": 0.9}
    result = interpolate_transform(a, b, 0.0)
    assert result == a


def test_interpolate_at_one():
    a = {"tx": 0, "ty": 0, "r": 0, "sx": 1.0, "sy": 1.0}
    b = {"tx": 10, "ty": 5, "r": 2.0, "sx": 1.1, "sy": 0.9}
    result = interpolate_transform(a, b, 1.0)
    assert result == b


def test_interpolate_midpoint():
    a = {"tx": 0, "ty": 0, "r": 0, "sx": 1.0, "sy": 1.0}
    b = {"tx": 10, "ty": -4, "r": 2.0, "sx": 1.2, "sy": 0.8}
    result = interpolate_transform(a, b, 0.5)
    assert result["tx"] == 5.0
    assert result["ty"] == -2.0
    assert result["r"] == 1.0
    assert abs(result["sx"] - 1.1) < 1e-10
    assert abs(result["sy"] - 0.9) < 1e-10


# ── Sampling ─────────────────────────────────────────────────────────────────

def test_sample_at_zero_is_neutral():
    result = sample_animation(IDLE_SEQUENCE, 0.0)
    for gid, t in result.items():
        assert t == NEUTRAL, f"group '{gid}' at t=0 should be neutral"


def test_sample_at_one_wraps_to_zero():
    """t=1.0 wraps to t=0.0 and should be neutral."""
    result = sample_animation(IDLE_SEQUENCE, 1.0)
    for gid, t in result.items():
        assert t == NEUTRAL, f"group '{gid}' at t=1.0 (wrap) should be neutral"


def test_sample_mid_loop_is_not_neutral():
    """At the middle of the loop, transforms should be non-neutral."""
    result = sample_animation(IDLE_SEQUENCE, 0.35)
    head = result["head"]
    # The idle sequence at t=0.35 has head translation
    assert head != NEUTRAL, "head at t=0.35 should not be neutral"


def test_sample_returns_all_groups():
    result = sample_animation(THINKING_SEQUENCE, 0.4)
    assert "head" in result
    assert "eyes" in result
    assert "brows" in result
    assert "mouth" in result


def test_sample_looping():
    """Sampling at t+1 should give the same result as t (modular)."""
    r1 = sample_animation(LISTENING_SEQUENCE, 0.3)
    r2 = sample_animation(LISTENING_SEQUENCE, 1.3)
    for gid in r1:
        for key in ("tx", "ty", "r", "sx", "sy"):
            assert abs(r1[gid][key] - r2[gid][key]) < 1e-10, (
                f"group '{gid}' key '{key}' differs at t=0.3 vs t=1.3"
            )


# ── Serialisation ────────────────────────────────────────────────────────────

def test_get_all_animations_returns_dict():
    result = get_all_animations()
    assert isinstance(result, dict)
    assert "idle" in result
    assert "listening" in result
    assert "thinking" in result


def test_serialised_structure():
    result = get_all_animations()
    for mode_name, seq in result.items():
        assert "mode" in seq
        assert "duration_ms" in seq
        assert "keyframes" in seq
        assert seq["mode"] == mode_name
        assert isinstance(seq["duration_ms"], int)
        assert len(seq["keyframes"]) >= 4
        for kf in seq["keyframes"]:
            assert "t" in kf
            assert "groups" in kf


def test_sequence_to_dict():
    d = IDLE_SEQUENCE.to_dict()
    assert d["mode"] == "idle"
    assert d["duration_ms"] == 4000
    assert len(d["keyframes"]) == len(IDLE_SEQUENCE.keyframes)


# ── Duration values ──────────────────────────────────────────────────────────

def test_idle_duration():
    assert IDLE_SEQUENCE.duration_ms == 4000


def test_listening_duration():
    assert LISTENING_SEQUENCE.duration_ms == 3000


def test_thinking_duration():
    assert THINKING_SEQUENCE.duration_ms == 5000
