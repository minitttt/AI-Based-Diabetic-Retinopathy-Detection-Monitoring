import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1] / "deployment" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from utils import decode_image, load_and_preprocess, validate_fundus_image
except ModuleNotFoundError as exc:  # The production dependency may be absent locally.
    if exc.name != "cv2":
        raise

    def _unavailable(*args, **kwargs):
        raise RuntimeError("opencv-python-headless is not installed")

    decode_image = load_and_preprocess = validate_fundus_image = _unavailable
    _UTILS_IMPORT_ERROR = "opencv-python-headless is not installed"
else:
    _UTILS_IMPORT_ERROR = None


def _synthetic_fundus(size: int = 256) -> np.ndarray:
    """Build a small deterministic fundus-like image without patient data."""

    coordinates = np.indices((size, size), dtype=np.float32)
    y, x = coordinates
    center = (size - 1) / 2.0
    radius = size * 0.42
    field = (x - center) ** 2 + (y - center) ** 2 <= radius**2

    image = np.zeros((size, size, 3), dtype=np.uint8)
    gradient = ((x + y) / max(1.0, 2.0 * (size - 1)) * 90.0).astype(np.uint8)
    image[..., 0] = np.where(field, 95 + gradient, 0)
    image[..., 1] = np.where(field, 35 + (gradient // 3), 0)
    image[..., 2] = np.where(field, 25 + (gradient // 4), 0)
    return image


def _encode_png(image: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


@unittest.skipUnless(_UTILS_IMPORT_ERROR is None, _UTILS_IMPORT_ERROR or "")
class FundusValidationTests(unittest.TestCase):
    def test_accepts_colorful_fundus_sized_image(self):
        image = _synthetic_fundus()

        self.assertTrue(validate_fundus_image(image))

    def test_rejects_none_wrong_channels_and_small_images(self):
        self.assertFalse(validate_fundus_image(None))
        self.assertFalse(validate_fundus_image(np.zeros((256, 256), dtype=np.uint8)))
        self.assertFalse(
            validate_fundus_image(np.zeros((256, 256, 4), dtype=np.uint8))
        )
        self.assertFalse(
            validate_fundus_image(np.zeros((127, 256, 3), dtype=np.uint8))
        )

    def test_rejects_non_fundus_like_flat_upload(self):
        flat_white = np.full((256, 256, 3), 255, dtype=np.uint8)
        self.assertFalse(validate_fundus_image(flat_white))

    def test_decode_and_preprocess_reject_unreadable_or_invalid_images(self):
        with self.assertRaisesRegex(ValueError, "not a readable image"):
            decode_image(b"not an image")

        invalid_png = _encode_png(np.full((256, 256, 3), 255, dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "retinal fundus image"):
            load_and_preprocess(invalid_png, img_size=64)

    def test_load_and_preprocess_returns_requested_size_for_valid_upload(self):
        processed = load_and_preprocess(_encode_png(_synthetic_fundus()), img_size=64)

        self.assertEqual(processed.shape, (64, 64, 3))
        self.assertEqual(processed.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()
