import os
import hashlib
from datetime import datetime
from django.core.files import File
from django.utils.text import slugify
from PIL import Image
from io import BytesIO


def generate_unique_slug(model_class, title, slug_field='slug'):
    """
    Generate a unique slug for a model instance
    """
    slug = slugify(title)
    unique_slug = slug
    counter = 1
    
    while model_class.objects.filter(**{slug_field: unique_slug}).exists():
        unique_slug = f"{slug}-{counter}"
        counter += 1
    
    return unique_slug


def get_file_hash(file):
    """
    Generate MD5 hash of a file
    """
    hash_md5 = hashlib.md5()
    for chunk in file.chunks():
        hash_md5.update(chunk)
    return hash_md5.hexdigest()


def create_thumbnail(image_file, size=(300, 300)):
    """
    Create a thumbnail from an image file
    """
    img = Image.open(image_file)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    thumb_io = BytesIO()
    img.save(thumb_io, format='JPEG', quality=85)
    
    return File(thumb_io, name=f"thumb_{image_file.name}")


def format_file_size(size_bytes):
    """
    Format file size in human readable format
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def get_video_duration(video_path):
    """
    Get video duration using ffprobe (requires ffmpeg)
    """
    import subprocess
    import json
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        if 'format' in data and 'duration' in data['format']:
            return float(data['format']['duration'])
    except:
        pass
    
    return None


def extract_exif(image_path):
    """
    Extract EXIF data from image
    """
    from PIL import Image
    from PIL.ExifTags import TAGS
    
    exif_data = {}
    
    try:
        image = Image.open(image_path)
        exif = image._getexif()
        
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8')
                    except:
                        value = str(value)
                exif_data[tag] = value
    except:
        pass
    
    return exif_data


def send_email_notification(subject, message, recipient_list, from_email=None):
    """
    Send email notification
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=True,
        )
        return True
    except:
        return False