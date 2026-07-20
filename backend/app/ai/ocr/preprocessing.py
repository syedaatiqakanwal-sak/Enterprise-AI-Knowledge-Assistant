"""Image preprocessing for OCR (OpenCV when available, Pillow fallback)."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PreprocessResult:
    image: np.ndarray  # RGB or grayscale uint8
    operations: list[str]
    rotation_degrees: float = 0.0


def _load_rgb(data: bytes) -> np.ndarray:
    try:
        import cv2

        arr = np.frombuffer(data, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("decode failed")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        return np.array(img)


def preprocess_image(
    data: bytes,
    *,
    max_side: int = 2000,
    deskew: bool = True,
    denoise: bool = True,
    enhance_contrast: bool = True,
    adaptive_threshold: bool = False,
) -> PreprocessResult:
    """
    Resize, deskew, denoise, contrast enhance, optional adaptive threshold.
    """
    ops: list[str] = []
    rgb = _load_rgb(data)
    ops.append("load")

    try:
        import cv2

        h, w = rgb.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            rgb = cv2.resize(
                rgb,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA,
            )
            ops.append(f"resize:{scale:.2f}")

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        rotation = 0.0
        if deskew:
            coords = np.column_stack(np.where(gray < 200))
            if len(coords) > 50:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                if abs(angle) > 0.5 and abs(angle) < 15:
                    (h2, w2) = gray.shape
                    M = cv2.getRotationMatrix2D((w2 / 2, h2 / 2), angle, 1.0)
                    gray = cv2.warpAffine(
                        gray,
                        M,
                        (w2, h2),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                    rgb = cv2.warpAffine(
                        rgb,
                        M,
                        (w2, h2),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                    rotation = float(angle)
                    ops.append(f"deskew:{angle:.2f}")

        if denoise:
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            ops.append("denoise")

        if enhance_contrast:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            ops.append("clahe")

        if adaptive_threshold:
            gray = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
            )
            ops.append("adaptive_threshold")
            return PreprocessResult(image=gray, operations=ops, rotation_degrees=rotation)

        # Return RGB for OCR engines that prefer color; gray also fine
        return PreprocessResult(
            image=cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB),
            operations=ops,
            rotation_degrees=rotation,
        )
    except Exception:
        logger.debug("OpenCV preprocess unavailable — using raw resize", exc_info=True)
        from PIL import Image

        img = Image.fromarray(rgb)
        img.thumbnail((max_side, max_side))
        ops.append("pillow_thumbnail")
        return PreprocessResult(image=np.array(img), operations=ops)


def encode_png(image: np.ndarray) -> bytes:
    try:
        import cv2

        if len(image.shape) == 2:
            bgr = image
        else:
            bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".png", bgr)
        if not ok:
            raise RuntimeError("imencode failed")
        return buf.tobytes()
    except Exception:
        from PIL import Image

        if len(image.shape) == 2:
            pil = Image.fromarray(image, mode="L")
        else:
            pil = Image.fromarray(image.astype(np.uint8), mode="RGB")
        out = io.BytesIO()
        pil.save(out, format="PNG")
        return out.getvalue()
