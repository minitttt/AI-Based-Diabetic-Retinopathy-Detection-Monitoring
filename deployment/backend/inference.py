import os
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms
import timm
from pathlib import Path

NUM_CLASSES = 5
CLASS_NAMES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]
IMG_SIZE = 380
MODEL_VERSION = os.getenv("RETINASCAN_MODEL_VERSION", "EfficientNet-B4-NS")

class DRClassifier(nn.Module):
    def __init__(self, num_classes=NUM_CLASSES, dropout_p=0.4, pretrained=False):
        super().__init__()
        self.backbone = timm.create_model(
            "tf_efficientnet_b4_ns",
            pretrained=pretrained,
            num_classes=0,
            global_pool="avg",
        )
        feat_dim = self.backbone.num_features
        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout_p),
            nn.Linear(feat_dim, 512),
            nn.GELU(),
            nn.BatchNorm1d(512),
            nn.Dropout(p=dropout_p / 2),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.backbone(x))

DEVICE = torch.device("cpu") # For inference, CPU is fine if no GPU available
model = None

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def load_model(ckpt_path=Path(__file__).parent.parent.parent / "checkpoints" / "best_model.pth"):
    global model
    model = DRClassifier(pretrained=False).to(DEVICE)
    ckpt = Path(ckpt_path)
    if ckpt.exists():
        checkpoint = torch.load(ckpt, map_location=DEVICE, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"Model loaded from {ckpt_path}")
    else:
        print(f"Warning: Checkpoint not found at {ckpt_path}. Using untrained weights for testing.")
    model.eval()


def get_model_version() -> str:
    """Return the public model label used in reports and API metadata."""

    return MODEL_VERSION


def _prediction_from_logits(logits: torch.Tensor) -> dict[str, Any]:
    probs = torch.softmax(logits, 1)[0].detach().cpu().numpy()
    pred_idx = int(logits.argmax(1)[0].detach().cpu().item())
    confidence = float(probs[pred_idx])
    return {
        "grade_idx": pred_idx,
        "grade_name": CLASS_NAMES[pred_idx],
        "confidence": confidence,
        "probabilities": [float(p) for p in probs],
    }


def _feature_tensor(value: Any) -> Optional[torch.Tensor]:
    """Extract a tensor from model feature outputs across timm variants."""

    if isinstance(value, torch.Tensor):
        return value
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            tensor = _feature_tensor(item)
            if tensor is not None:
                return tensor
    if isinstance(value, dict):
        for item in reversed(list(value.values())):
            tensor = _feature_tensor(item)
            if tensor is not None:
                return tensor
    return None


def _forward_features_for_cam(img_tensor: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Run the current classifier while retaining its final 4-D feature map."""

    if model is None:  # pragma: no cover - guarded by public entry points
        raise RuntimeError("Model is not loaded")

    backbone = getattr(model, "backbone", None)
    forward_features = getattr(backbone, "forward_features", None)
    global_pool = getattr(backbone, "global_pool", None)
    if not callable(forward_features) or not callable(global_pool):
        raise RuntimeError("The EfficientNet backbone does not expose feature maps")

    features = _feature_tensor(forward_features(img_tensor))
    if features is None or features.ndim != 4:
        raise RuntimeError("The EfficientNet feature map is not spatial")

    pooled = global_pool(features)
    if pooled.ndim > 2:
        pooled = pooled.flatten(1)
    logits = model.classifier(pooled)
    return logits, features


def _resize_attention(attention: torch.Tensor, height: int, width: int) -> np.ndarray:
    """Resize and normalize a single-channel attention tensor."""

    if attention.ndim == 2:
        attention = attention.unsqueeze(0).unsqueeze(0)
    elif attention.ndim == 3:
        attention = attention.unsqueeze(1)
    attention = F.interpolate(
        attention.float(),
        size=(height, width),
        mode="bilinear",
        align_corners=False,
    )[0, 0]
    array = torch.nan_to_num(attention).detach().cpu().numpy().astype(np.float32)
    minimum = float(array.min()) if array.size else 0.0
    maximum = float(array.max()) if array.size else 0.0
    if maximum <= minimum + 1e-8:
        return np.zeros((height, width), dtype=np.float32)
    return np.clip((array - minimum) / (maximum - minimum), 0.0, 1.0)


def _grad_cam(features: torch.Tensor, logits: torch.Tensor, class_index: int) -> torch.Tensor:
    """Compute Grad-CAM for the selected class from the final feature map."""

    gradients = torch.autograd.grad(
        logits[0, class_index],
        features,
        retain_graph=False,
        allow_unused=True,
    )[0]
    if gradients is None or gradients.shape != features.shape:
        raise RuntimeError("Grad-CAM gradients were unavailable")
    weights = gradients.mean(dim=(2, 3), keepdim=True)
    return torch.relu((weights * features).sum(dim=1))


def _activation_attention(features: torch.Tensor) -> torch.Tensor:
    """Use EfficientNet activations when gradients are unavailable."""

    if features.ndim != 4:
        raise RuntimeError("Activation fallback requires a spatial feature map")
    return features.detach().abs().mean(dim=1)


def _input_gradient_attention(
    img_tensor: torch.Tensor,
    logits: torch.Tensor,
    class_index: int,
) -> torch.Tensor:
    """Last-resort saliency map that still comes from the loaded model."""

    gradients = torch.autograd.grad(
        logits[0, class_index],
        img_tensor,
        retain_graph=False,
        allow_unused=True,
    )[0]
    if gradients is None:
        raise RuntimeError("Input gradients were unavailable")
    return gradients.detach().abs().mean(dim=1)


def predict_with_explanation(img_np):
    """Return one prediction and its model attention map.

    The normal path computes Grad-CAM from the same EfficientNet forward pass
    used for the prediction.  If a timm version changes the feature API, the
    function falls back first to EfficientNet activation attention and then to
    input-gradient saliency.  The method label is returned so a report never
    presents a fallback as Grad-CAM.
    """

    if model is None:
        load_model()

    img_tensor = transform(img_np).unsqueeze(0).to(DEVICE)
    img_tensor.requires_grad_(True)
    height, width = int(img_np.shape[0]), int(img_np.shape[1])

    try:
        with torch.enable_grad():
            logits, features = _forward_features_for_cam(img_tensor)
            prediction = _prediction_from_logits(logits)
            class_index = int(prediction["grade_idx"])
            try:
                attention = _grad_cam(features, logits, class_index)
                method = "Grad-CAM (EfficientNet final feature map)"
            except Exception:
                attention = _activation_attention(features)
                method = "EfficientNet activation attention fallback"
            attention_map = _resize_attention(attention, height, width)
            if not np.isfinite(attention_map).all():
                raise RuntimeError("Attention map contained non-finite values")
            if float(attention_map.max()) <= 1e-6:
                attention_map = _resize_attention(
                    _activation_attention(features), height, width
                )
                method = "EfficientNet activation attention fallback"
            return prediction, attention_map, method
    except Exception:
        # A full forward keeps compatibility with timm releases whose
        # ``forward_features`` output is not spatial.  This is still one model
        # run for the fallback and makes the attention provenance explicit.
        with torch.enable_grad():
            try:
                logits = model(img_tensor)
                prediction = _prediction_from_logits(logits)
                class_index = int(prediction["grade_idx"])
                attention = _input_gradient_attention(img_tensor, logits, class_index)
                attention_map = _resize_attention(attention, height, width)
                return (
                    prediction,
                    attention_map,
                    "Input-gradient saliency fallback (EfficientNet)",
                )
            except Exception:
                # Keep the report path available even for a custom checkpoint
                # that cannot expose gradients.  The prediction is delegated
                # to the established API only when the fallback forward did
                # not produce usable logits; otherwise no extra model run is
                # needed for report generation.
                if not isinstance(locals().get("prediction"), dict):
                    prediction = predict(img_np)
                gray = np.asarray(img_np, dtype=np.float32).mean(axis=2)
                minimum, maximum = float(gray.min()), float(gray.max())
                if maximum > minimum + 1e-8:
                    gray = (gray - minimum) / (maximum - minimum)
                else:
                    gray = np.zeros_like(gray)
                return prediction, gray.astype(np.float32), "Input intensity fallback"


def predict(img_np):
    if model is None:
        load_model()

    img_tensor = transform(img_np).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        logits = model(img_tensor)
    return _prediction_from_logits(logits)
