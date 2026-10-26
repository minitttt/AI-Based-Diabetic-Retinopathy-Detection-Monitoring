import cv2
import numpy as np


def validate_fundus_image(img):
    """Reject obvious non-fundus images before the classifier forces a result."""
    if img is None or img.ndim != 3 or img.shape[2] != 3:
        return False

    height, width = img.shape[:2]
    if min(height, width) < 128:
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    saturation = float(hsv[..., 1].mean())
    contrast = float(gray.std())

    corner_size = max(1, min(height, width) // 10)
    corners = np.concatenate([
        gray[:corner_size, :corner_size].ravel(),
        gray[:corner_size, -corner_size:].ravel(),
        gray[-corner_size:, :corner_size].ravel(),
        gray[-corner_size:, -corner_size:].ravel(),
    ])
    dark_corner_fraction = float((corners < 30).mean())

    return (
        saturation >= 25
        and contrast >= 12
        and dark_corner_fraction >= 0.20
    )


def decode_image(img_bytes):
    """Decode uploaded bytes into an RGB uint8 array.

    Keeping decoding in one utility lets report generation inspect the original
    upload while the prediction path continues to use the existing
    preprocessing pipeline.
    """

    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("The uploaded file is not a readable image.")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def compute_image_quality_score(img):
    """Return a deterministic 0-100 quality score for an RGB image.

    This is a screening-oriented technical quality estimate, not a clinical
    diagnosis.  It combines exposure, contrast, sharpness, and retinal-field
    coverage so the value can be included in a report without another model
    invocation.
    """

    if img is None:
        return 0.0

    if isinstance(img, (bytes, bytearray, memoryview)):
        img = decode_image(bytes(img))

    array = np.asarray(img)
    if array.ndim != 3 or array.shape[2] != 3 or min(array.shape[:2]) < 2:
        return 0.0

    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)

    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    brightness = float(gray.mean()) / 255.0
    contrast = float(gray.std())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Fundus photos normally have a darker border around the circular field;
    # this coverage term also penalizes all-black or all-white uploads.
    hsv = cv2.cvtColor(array, cv2.COLOR_RGB2HSV)
    saturation = float(hsv[..., 1].mean()) / 255.0
    non_background = float((gray > 12).mean())

    exposure_score = max(0.0, 1.0 - abs(brightness - 0.52) / 0.52)
    contrast_score = min(1.0, contrast / 64.0)
    sharpness_score = min(1.0, sharpness / 450.0)
    color_score = min(1.0, saturation / 0.35)
    coverage_score = min(1.0, non_background / 0.78)

    score = 100.0 * (
        0.25 * exposure_score
        + 0.25 * contrast_score
        + 0.25 * sharpness_score
        + 0.10 * color_score
        + 0.15 * coverage_score
    )
    return float(round(max(0.0, min(100.0, score)), 1))

def crop_black_borders(img, tolerance=7):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    mask = gray > tolerance
    if not np.any(mask):
        return img
    rows, cols = np.any(mask, axis=1), np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return img[rmin:rmax+1, cmin:cmax+1]

def apply_clahe(img, clip_limit=2.0, tile=8):
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return cv2.merge([clahe.apply(ch) for ch in cv2.split(img)])

def ben_graham_preprocess(img, img_size=380):
    try:
        img = crop_black_borders(img)
    except (IndexError, ValueError):
        pass
    img = cv2.resize(img, (img_size, img_size))
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=img_size/30)
    img = cv2.addWeighted(img, 4, blurred, -4, 128)
    mask = np.zeros_like(img)
    r = img_size // 2
    cv2.circle(mask, (r, r), int(r * 0.9), (1, 1, 1), -1)
    img = img * mask + 128 * (1 - mask)
    return img.astype(np.uint8)

def load_and_preprocess(img_bytes, img_size=380, use_clahe=True):
    img = decode_image(img_bytes)
    if not validate_fundus_image(img):
        raise ValueError("Please upload a retinal fundus image with the circular retinal field visible.")
    img = ben_graham_preprocess(img, img_size)
    if use_clahe:
        img = apply_clahe(img)
    return img
