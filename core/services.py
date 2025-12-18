import magic
from moviepy.editor import VideoFileClip
from django.core.files.base import ContentFile
from PIL import Image
import io
import os

def detect_file_type(file):
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    if mime.startswith('video'): return 'video'
    if mime.startswith('image'): return 'image'
    return 'other'

def generate_thumbnail(video_file):
    try:
        temp_path = video_file.temporary_file_path()
        clip = VideoFileClip(temp_path)
        frame_time = min(2, clip.duration * 0.1)
        frame = clip.get_frame(frame_time)
        clip.close()

        img = Image.fromarray(frame)
        img_io = io.BytesIO()
        img.save(img_io, format='WEBP', quality=85)
        filename = os.path.splitext(video_file.name)[0] + '.webp'
        return ContentFile(img_io.getulo(), name=filename)
    except Exception as e:
        print(f"Thumbnail error: {e}")
        return None

def calculate_earnings_per_view(views):
    # Tiered earning (example)
    if views >= 100000: rate = 0.004
    elif views >= 50000: rate = 0.0035
    elif views >= 10000: rate = 0.003
    else: rate = 0.0025
    return round(views * rate / 1000, 4)  # per 1000 views