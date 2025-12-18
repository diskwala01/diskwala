# core/services.py
# Render + Production Safe Version

from moviepy.editor import VideoFileClip
from django.core.files.base import ContentFile
from PIL import Image
import io
import os


# ==============================
# FILE TYPE DETECTION (NO magic)
# ==============================
def detect_file_type(file):
    """
    Detect file type using Django's content_type
    (Render & production safe)
    """
    content_type = getattr(file, "content_type", "")

    if content_type.startswith("video"):
        return "video"
    if content_type.startswith("image"):
        return "image"
    return "other"


# ==============================
# VIDEO THUMBNAIL GENERATION
# ==============================
def generate_thumbnail(video_file):
    """
    Generate WEBP thumbnail from video
    Works only if file is stored temporarily on disk
    """
    try:
        # Render / Django temporary file path
        temp_path = video_file.temporary_file_path()

        clip = VideoFileClip(temp_path)

        # Take frame at 10% duration or max 2 seconds
        frame_time = min(2, clip.duration * 0.1)
        frame = clip.get_frame(frame_time)

        clip.close()

        # Convert frame to image
        image = Image.fromarray(frame)
        image_io = io.BytesIO()

        image.save(
            image_io,
            format="WEBP",
            quality=85,
            method=6
        )

        filename = os.path.splitext(video_file.name)[0] + ".webp"

        return ContentFile(
            image_io.getvalue(),  # ✅ FIXED TYPO
            name=filename
        )

    except Exception as e:
        print("Thumbnail generation error:", e)
        return None


# ==============================
# EARNINGS CALCULATION
# ==============================
def calculate_earnings_per_view(views):
    """
    Calculate earnings based on tiered view system
    (per 1000 views)
    """
    if views >= 100000:
        rate = 0.004
    elif views >= 50000:
        rate = 0.0035
    elif views >= 10000:
        rate = 0.003
    else:
        rate = 0.0025

    return round((views / 1000) * rate, 4)
