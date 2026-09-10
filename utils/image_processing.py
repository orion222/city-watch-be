from io import BytesIO

import pillow_heif
from fastapi import HTTPException
from PIL import ExifTags, Image, ImageOps
from uvicorn import logging

pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

MAX_DIM = 2048  # Maximum dimension for resizing images
JPEG_QUALITY = 85
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/heic", "image/heif"]


def _dms_to_decimal(dms: tuple, ref: str) -> float:
    """
    Converts GPS coordinates from degrees, minutes, seconds (DMS) format to decimal degrees.

    Args:
        dms (tuple): A tuple containing the DMS values.
        ref (str): The reference direction ('N', 'S', 'E', 'W').

    Returns:
        float: The converted decimal degree value.
    """
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])

    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

    # Negate directions
    if ref in ["S", "W"]:
        return -decimal

    return decimal


def _extract_gps_coordinates(img: Image) -> tuple[float | None, float | None]:
    """
    Extracts GPS coordinates from the EXIF data of an image.

    Args:
        img (Image): The PIL Image object.

    Returns:
        tuple containing:
            - latitude (float | None): The extracted latitude, or None if not found.
            - longitude (float | None): The extracted longitude, or None if not found.
    """

    try:
        exif = img.getexif()
        if not exif:
            return None, None

        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        if not gps_ifd:
            return None, None

        # Tags: 1=LatRef, 2=Lat, 3=LonRef, 4=Lon
        lat_val = gps_ifd.get(ExifTags.GPS.GPSLatitude) or gps_ifd.get(2)
        lat_ref = gps_ifd.get(ExifTags.GPS.GPSLatitudeRef) or gps_ifd.get(1)
        lon_val = gps_ifd.get(ExifTags.GPS.GPSLongitude) or gps_ifd.get(4)
        lon_ref = gps_ifd.get(ExifTags.GPS.GPSLongitudeRef) or gps_ifd.get(3)

        if not (lat_val and lat_ref and lon_val and lon_ref):
            return None, None

        lat = _dms_to_decimal(lat_val, lat_ref)
        lon = _dms_to_decimal(lon_val, lon_ref)

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            logger.warning(f"Extracted GPS coordinates out of bounds: lat={lat}, lon={lon}")
            return None, None

        return lat, lon

    except Exception as e:
        logger.error(f"Failed to extract EXIF data: {e}")
        return None, None


def process_image(file_bytes: bytes) -> tuple[bytes, str, float | None, float | None]:
    """
    Validates, extracts EXIF GPS, rotates according to orientation, resizes to MAX_DIM,
    extracts EXIF metadata, and converts HEIC/HEIF images to JPEG.

    Args:
        file_bytes (bytes): The bytes of the uploaded image file.

    Returns:
        tuple containing:
            - clean_bytes (bytes): The sanitized, resized JPEG bytes.
            - mime_type (str): The MIME type of the processed image (Always "image/jpeg").
            - latitude (float | None): The EXIF latitude, or None.
            - longitude (float | None): The EXIF longitude, or None.
    """

    # Verify
    try:
        test_img = Image.open(BytesIO(file_bytes))
        test_img.verify()
    except Exception as e:
        logger.error(f"Image verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file")

    img = Image.open(BytesIO(file_bytes))
    lat, lon = _extract_gps_coordinates(img)
    img = ImageOps.exif_transpose(img)  # Rotate based on EXIF orientation
    img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)  # Resize while preserving aspect ratio

    # Normalize if image was RGBA/HEIF
    if img.mode != "RGB":
        img = img.convert("RGB")

    output_buffer = BytesIO()
    img.save(output_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    clean_bytes = output_buffer.getvalue()

    return clean_bytes, "image/jpeg", lat, lon
