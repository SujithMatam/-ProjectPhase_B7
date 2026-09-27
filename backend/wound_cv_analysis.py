"""
Preliminary wound-image analysis using classical computer vision.

This module analyzes the actual pixels of an uploaded image. It is NOT a
trained medical model and MUST NOT be presented as diagnosing infection,
healing complications, or any other medical condition.

The current implementation is intentionally provisional. A future version
can replace this analysis with a trained and clinically validated model once
the project has an appropriate labeled dataset.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

import numpy as np
from PIL import Image

MODEL_INPUT_MAX_DIM = 512

REDNESS_HUE_LOW = 345
REDNESS_HUE_HIGH = 15
REDNESS_MIN_SATURATION = 0.35
REDNESS_MIN_VALUE = 0.25

ELEVATED_REDNESS_SCORE_THRESHOLD = 0.05
ELEVATED_REDNESS_INTENSITY_THRESHOLD = 0.45

DARK_PIXEL_VALUE_THRESHOLD = 0.12
BRIGHT_PIXEL_VALUE_THRESHOLD = 0.92


@dataclass
class WoundImageAnalysis:
    redness_score: float
    redness_intensity: float
    color_variability: float
    brightness_mean: float
    brightness_std: float
    dark_spot_ratio: float
    bright_spot_ratio: float
    visual_flag: str
    friendly_summary: str = ""  # plain-language explanation, see _build_friendly_summary()
    analysis_method: str = "classical_cv_color_analysis"
    disclaimer: str = (
        "This is a preliminary automated analysis of image color and "
        "brightness. It is not a medical diagnosis and cannot determine "
        "whether a wound is infected. Lighting, skin tone, camera quality, "
        "and background objects can affect the result. Use it only as a "
        "supplementary signal alongside symptoms and clinical assessment."
    )
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_and_prepare(image_path: str) -> np.ndarray:
    with Image.open(image_path) as img:
        img = img.convert("RGB")

        if max(img.size) > MODEL_INPUT_MAX_DIM:
            ratio = MODEL_INPUT_MAX_DIM / max(img.size)
            new_size = (
                max(1, int(img.width * ratio)),
                max(1, int(img.height * ratio)),
            )
            img = img.resize(new_size, Image.LANCZOS)

        return np.array(img, dtype=np.float64) / 255.0


def _rgb_to_hsv_array(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    maxc = np.max(rgb, axis=-1)
    minc = np.min(rgb, axis=-1)
    v = maxc
    delta = maxc - minc

    safe_max = np.where(maxc == 0, 1, maxc)
    s = np.where(maxc == 0, 0, delta / safe_max)

    delta_safe = np.where(delta == 0, 1, delta)

    rc = (maxc - r) / delta_safe
    gc = (maxc - g) / delta_safe
    bc = (maxc - b) / delta_safe

    h = np.zeros_like(maxc)

    is_r_max = (maxc == r) & (delta != 0)
    is_g_max = (maxc == g) & (delta != 0)
    is_b_max = (maxc == b) & (delta != 0)

    h = np.where(is_r_max, (bc - gc) % 6, h)
    h = np.where(is_g_max, bc - rc + 2, h)
    h = np.where(is_b_max, rc - gc + 4, h)
    h = (h * 60) % 360

    return np.stack([h, s, v], axis=-1)


def _build_friendly_summary(
    visual_flag: str,
    color_variability: float,
    warnings: List[str],
) -> str:
    """
    Turns the raw numbers into a short, warm, plain-language explanation
    instead of a wall of numbers -- this is what the Flutter chat UI
    actually displays as the bot's message.

    IMPORTANT ordering: a genuine detection (elevated_redness_detected)
    must be checked BEFORE the generic low-contrast warning, otherwise a
    real finding gets silently overridden by an unrelated image-quality
    note (caught during testing -- a clearly red test image was getting
    the "hard to see" message instead of mentioning the redness it had
    actually detected).
    """

    if visual_flag == "elevated_redness_detected":
        if color_variability > 0.3:
            opening = (
                "Looking at the photo, I can see some noticeable redness, "
                "and the coloring around the area looks a bit uneven or "
                "patchy rather than uniform."
            )
        else:
            opening = (
                "Looking at the photo, I can see some noticeable redness "
                "in the area."
            )
    elif warnings and any("dark" in w or "contrast" in w for w in warnings):
        opening = (
            "I looked at the photo, but the lighting or focus made it "
            "hard to see clearly. 📷 It might help to retake it somewhere "
            "brighter, with the camera held steady."
        )
    else:
        opening = (
            "Looking at the photo, I don't see any strong signs of redness "
            "or irritation standing out."
        )

    closing = (
        " Keep in mind I'm reading colors and brightness in the photo, not "
        "actually examining the wound the way a person could -- lighting, "
        "skin tone, and camera quality can all throw this off. Use this "
        "alongside how the area actually feels to you, and if anything "
        "seems off, that's worth mentioning to your surgical team "
        "regardless of what this says. (This part of the app is still "
        "early -- once a properly trained model is ready, this read "
        "should get a lot more accurate.)"
    )

    return opening + closing


def analyze_wound_image(image_path: str) -> WoundImageAnalysis:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        rgb = _load_and_prepare(image_path)
    except Exception as exc:
        raise ValueError(f"File is not a valid image: {exc}") from exc

    hsv = _rgb_to_hsv_array(rgb)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    is_red_hue = (h >= REDNESS_HUE_LOW) | (h <= REDNESS_HUE_HIGH)
    is_saturated = s >= REDNESS_MIN_SATURATION
    is_visible = v >= REDNESS_MIN_VALUE
    redness_mask = is_red_hue & is_saturated & is_visible

    redness_score = float(np.mean(redness_mask))

    redness_intensity = (
        float(np.mean(s[redness_mask]))
        if np.any(redness_mask)
        else 0.0
    )

    meaningful_pixels = v >= 0.1

    if np.any(meaningful_pixels):
        hue_std = float(np.std(h[meaningful_pixels]))
        color_variability = min(hue_std / 180.0, 1.0)
    else:
        color_variability = 0.0

    brightness_mean = float(np.mean(v))
    brightness_std = float(np.std(v))

    dark_spot_ratio = float(
        np.mean(v <= DARK_PIXEL_VALUE_THRESHOLD)
    )
    bright_spot_ratio = float(
        np.mean(v >= BRIGHT_PIXEL_VALUE_THRESHOLD)
    )

    warnings: List[str] = []

    if (
        redness_score >= ELEVATED_REDNESS_SCORE_THRESHOLD
        and redness_intensity >= ELEVATED_REDNESS_INTENSITY_THRESHOLD
    ):
        visual_flag = "elevated_redness_detected"
    else:
        visual_flag = "no_strong_indicators"

    if brightness_mean < 0.15:
        warnings.append(
            "The image is very dark, so color readings may be unreliable."
        )

    if brightness_std < 0.03:
        warnings.append(
            "The image has very little contrast or detail. A clearer, "
            "well-lit photo may provide a more useful signal."
        )

    if bright_spot_ratio > 0.30:
        warnings.append(
            "A large portion of the image is very bright. Glare or "
            "overexposure may affect the color readings."
        )

    if dark_spot_ratio > 0.30:
        warnings.append(
            "A large portion of the image is very dark. Shadows may "
            "affect the color readings."
        )

    friendly_summary = _build_friendly_summary(
        visual_flag=visual_flag,
        color_variability=color_variability,
        warnings=warnings,
    )

    return WoundImageAnalysis(
        redness_score=round(redness_score, 4),
        redness_intensity=round(redness_intensity, 4),
        color_variability=round(color_variability, 4),
        brightness_mean=round(brightness_mean, 4),
        brightness_std=round(brightness_std, 4),
        dark_spot_ratio=round(dark_spot_ratio, 4),
        bright_spot_ratio=round(bright_spot_ratio, 4),
        visual_flag=visual_flag,
        friendly_summary=friendly_summary,
        warnings=warnings,
    )