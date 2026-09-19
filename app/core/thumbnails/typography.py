"""Programmatic Typography Engine for Thumbnails and Cover Artwork."""
import math
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class TypographyEngine:
    """Renders highly legible, branded programmatic typography and exports multi-platform thumbnail variants."""

    PLATFORM_VARIANTS: Dict[str, Tuple[int, int]] = {
        "vertical_9_16": (1080, 1920),
        "square_1_1": (1080, 1080),
        "widescreen_16_9": (1280, 720),
    }

    @classmethod
    def get_font(cls, size: int) -> ImageFont.ImageFont:
        """Loads default font at requested size."""
        try:
            # Try Arial or standard Windows fonts
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            try:
                return ImageFont.truetype("segoeui.ttf", size)
            except Exception:
                return ImageFont.load_default()

    @classmethod
    def apply_gradient_vignette(cls, img: Image.Image) -> Image.Image:
        """Applies a smooth dark gradient at top and bottom to ensure text readability."""
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Top gradient (height ~18% of canvas)
        top_h = int(h * 0.18)
        for y in range(top_h):
            alpha = int(160 * (1.0 - (y / top_h)))
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        # Bottom gradient (height ~35% of canvas)
        bottom_h = int(h * 0.35)
        for y in range(bottom_h):
            pos_y = h - bottom_h + y
            alpha = int(220 * (y / bottom_h))
            draw.line([(0, pos_y), (w, pos_y)], fill=(0, 0, 0, alpha))

        return Image.alpha_composite(img.convert("RGBA"), overlay)

    @classmethod
    def render_thumbnail(
        cls,
        background_image: Image.Image,
        series_title: str,
        episode_number: int,
        episode_title: str,
        target_size: Tuple[int, int] = (1080, 1920),
        logo_text: str = "PREETI STUDIO",
    ) -> Image.Image:
        """Renders stylized typography and branding over the background artwork."""
        target_w, target_h = target_size

        # Aspect-fit crop
        bg_ratio = background_image.width / background_image.height
        target_ratio = target_w / target_h

        if bg_ratio > target_ratio:
            # Crop sides
            new_w = int(background_image.height * target_ratio)
            left = (background_image.width - new_w) // 2
            cropped = background_image.crop((left, 0, left + new_w, background_image.height))
        else:
            # Crop top/bottom
            new_h = int(background_image.width / target_ratio)
            top = (background_image.height - new_h) // 2
            cropped = background_image.crop((0, top, background_image.width, top + new_h))

        resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        composited = cls.apply_gradient_vignette(resized)
        draw = ImageDraw.Draw(composited)

        # Scale typography proportionally based on width
        scale_factor = target_w / 1080.0
        badge_font_size = max(16, int(26 * scale_factor))
        series_font_size = max(24, int(42 * scale_factor))
        title_font_size = max(32, int(64 * scale_factor))
        logo_font_size = max(14, int(22 * scale_factor))

        badge_font = cls.get_font(badge_font_size)
        series_font = cls.get_font(series_font_size)
        title_font = cls.get_font(title_font_size)
        logo_font = cls.get_font(logo_font_size)

        # 1. Top Logo Stamp
        logo_x = int(50 * scale_factor)
        logo_y = int(50 * scale_factor)
        draw.text((logo_x, logo_y), logo_text.upper(), font=logo_font, fill=(240, 240, 240, 220))

        # 2. Episode Badge Pill
        badge_text = f"EPISODE {episode_number:02d}"
        badge_x = logo_x
        badge_y = target_h - int(240 * scale_factor)
        badge_padding_x = int(18 * scale_factor)
        badge_padding_y = int(8 * scale_factor)

        # Measure text box
        bbox = draw.textbbox((badge_x, badge_y), badge_text, font=badge_font)
        pill_rect = (
            bbox[0] - badge_padding_x,
            bbox[1] - badge_padding_y,
            bbox[2] + badge_padding_x,
            bbox[3] + badge_padding_y,
        )
        draw.rounded_rectangle(pill_rect, radius=int(6 * scale_factor), fill=(225, 29, 72, 240))  # Crimson red
        draw.text((badge_x, badge_y), badge_text, font=badge_font, fill=(255, 255, 255, 255))

        # 3. Series Title (subtle secondary)
        series_y = badge_y + int(45 * scale_factor)
        draw.text(
            (logo_x, series_y),
            series_title.upper(),
            font=series_font,
            fill=(220, 220, 220, 240),
            stroke_width=int(2 * scale_factor),
            stroke_fill=(10, 10, 10, 200),
        )

        # 4. Episode Title (hero header)
        title_y = series_y + int(55 * scale_factor)
        draw.text(
            (logo_x, title_y),
            episode_title,
            font=title_font,
            fill=(255, 255, 255, 255),
            stroke_width=int(3 * scale_factor),
            stroke_fill=(0, 0, 0, 240),
        )

        return composited.convert("RGB")

    @classmethod
    def export_all_variants(
        cls,
        base_artwork_path: str,
        series_title: str,
        episode_number: int,
        episode_title: str,
        output_dir: str,
        base_filename_prefix: str,
    ) -> Dict[str, str]:
        """Generates and saves all 3 platform variants (vertical 9:16, square 1:1, widescreen 16:9)."""
        base_img = Image.open(base_artwork_path)
        os.makedirs(output_dir, exist_ok=True)
        out_paths = {}

        for variant_key, dims in cls.PLATFORM_VARIANTS.items():
            rendered = cls.render_thumbnail(
                background_image=base_img,
                series_title=series_title,
                episode_number=episode_number,
                episode_title=episode_title,
                target_size=dims,
            )
            out_file = os.path.join(output_dir, f"{base_filename_prefix}_{variant_key}.jpg")
            rendered.save(out_file, "JPEG", quality=95)
            out_paths[variant_key] = out_file

        return out_paths
