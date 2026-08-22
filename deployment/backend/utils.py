import cv2
import numpy as np

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
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = ben_graham_preprocess(img, img_size)
    if use_clahe:
        img = apply_clahe(img)
    return img
