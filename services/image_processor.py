"""
services/image_processor.py
Handles image loading, validation, and basic preprocessing
for regression analysis pipeline.
"""

from PIL import Image
import os
from io import BytesIO
from typing import Tuple
from models.finding import ImageMetadata


class ImageValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.code = "IMAGE_VALIDATION_ERROR"    
        self.message = message
        self.suggestion = "Ensure the file is a valid image in PNG, JPG, JPEG, or WEBP format."


class ImageProcessor:
    """
    Handles image loading and validation for design audit pipeline.
    """

    SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".webp")

    @staticmethod
    def load_image(image_path: str) -> Image.Image:
        if not os.path.exists(image_path):
            raise ImageValidationError(f"File not found: {image_path}")

        if not image_path.lower().endswith(ImageProcessor.SUPPORTED_FORMATS):
            raise ImageValidationError(
                f"Unsupported image format. Allowed: {ImageProcessor.SUPPORTED_FORMATS}"
            )

        try:
            img = Image.open(image_path)
            img.verify()
            img = Image.open(image_path)
            return img
        except Exception as e:
            raise ImageValidationError(f"Invalid image file: {str(e)}")

    @staticmethod
    def get_image_info(image_path: str) -> dict:
        with Image.open(image_path) as img:
            return {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
            }


    def validate_and_load(self, image_bytes: bytes, filename: str):

        if not filename.lower().endswith(self.SUPPORTED_FORMATS):
            raise ImageValidationError(
                f"Unsupported format: {filename}"
            )

        try:
            img = Image.open(BytesIO(image_bytes))
            img.verify()

            img = Image.open(BytesIO(image_bytes))

            metadata = ImageMetadata(
                filename=filename,
                format=img.format or "Unknown",
                width=img.width,
                height=img.height,
                size_bytes=len(image_bytes),
                file_size=len(image_bytes),
                color_mode=img.mode
            )

            return img, metadata

        except Exception as e:
            raise ImageValidationError(f"Invalid image: {str(e)}")