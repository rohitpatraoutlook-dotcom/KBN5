import io
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, url_for
from PIL import Image, UnidentifiedImageError

from services.auth_service import api_admin_required

admin_image_bp = Blueprint(
    "admin_images",
    __name__,
    url_prefix="/api/v1/admin/images",
)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


@admin_image_bp.post("/upload")
@api_admin_required
def upload_product_image():
    uploaded = request.files.get("image")

    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Choose an image file."}), 400

    raw = uploaded.stream.read(MAX_IMAGE_BYTES + 1)

    if not raw:
        return jsonify({"error": "The uploaded file is empty."}), 400

    if len(raw) > MAX_IMAGE_BYTES:
        return jsonify({"error": "Image must be 5 MB or smaller."}), 413

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image_format = image.format
            width, height = image.size

            if image_format not in ALLOWED_FORMATS:
                return jsonify({
                    "error": "Only JPEG, PNG and WEBP images are allowed."
                }), 415

            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                return jsonify({"error": "Image dimensions are too large."}), 400

            image.verify()

        # Decode again and re-encode to remove metadata and reject
        # malformed files that only pass a superficial file check.
        with Image.open(io.BytesIO(raw)) as image:
            image.load()

            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            output = io.BytesIO()
            image.save(
                output,
                format=image_format,
                optimize=True,
            )
            clean_bytes = output.getvalue()

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        ValueError,
    ):
        return jsonify({"error": "Invalid or unsupported image."}), 400

    upload_dir = Path(current_app.static_folder) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = secrets.token_hex(16) + ALLOWED_FORMATS[image_format]
    destination = upload_dir / filename

    try:
        destination.write_bytes(clean_bytes)
    except OSError:
        current_app.logger.exception("Image save failed")
        return jsonify({"error": "Could not save image."}), 500

    return jsonify({
        "message": "Image uploaded.",
        "image_key": filename,
        "image_url": url_for(
            "static",
            filename=f"uploads/{filename}",
            _external=False,
        ),
        "width": width,
        "height": height,
        "size_bytes": len(clean_bytes),
    }), 201
