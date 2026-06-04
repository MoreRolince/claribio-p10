"""
Pretraitement image pour le module OCR ClariBio.
Auteur : N'TCHO PHANUEL ELIEL KONE - ClariBio P10

Objectif : ameliorer les photos de bilans avant passage OCR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ImagePreprocessor:
    """
    Pipeline OpenCV : niveaux de gris, CLAHE, denoising, deskew et seuillage.

    Le module degrade proprement si OpenCV n'est pas installe afin de garder les
    tests unitaires executables sur une machine legere.
    """

    def __init__(self, clahe_clip_limit: float = 2.0, clahe_grid_size: int = 8):
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_grid_size = clahe_grid_size

    def preprocess_file(self, image_path: str | Path) -> Any:
        cv2, _ = _load_cv2()
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Image illisible: {image_path}")
        return self.preprocess_array(image)

    def preprocess_array(self, image: Any) -> Any:
        cv2, np = _load_cv2()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=(self.clahe_grid_size, self.clahe_grid_size),
        )
        enhanced = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(enhanced, h=12)
        deskewed = self._deskew(denoised, cv2, np)
        return cv2.adaptiveThreshold(
            deskewed,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

    def _deskew(self, gray: Any, cv2: Any, np: Any) -> Any:
        coords = np.column_stack(np.where(gray < 245))
        if coords.size == 0:
            return gray

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return gray

        height, width = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((width // 2, height // 2), angle, 1.0)
        return cv2.warpAffine(
            gray,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )


def _load_cv2():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV/numpy non installes. Installer avec: pip install opencv-python numpy"
        ) from exc
    return cv2, np
