import torch
import torch.nn as nn
import torchvision.transforms as transforms
import timm
from pathlib import Path

NUM_CLASSES = 5
CLASS_NAMES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]
IMG_SIZE = 380

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

def predict(img_np):
    if model is None:
        load_model()
    
    img_tensor = transform(img_np).unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        logits = model(img_tensor)
        probs = torch.softmax(logits, 1)[0].cpu().numpy()
        pred_idx = int(logits.argmax(1)[0].item())
        
    confidence = float(probs[pred_idx])
    return {
        "grade_idx": pred_idx,
        "grade_name": CLASS_NAMES[pred_idx],
        "confidence": confidence,
        "probabilities": [float(p) for p in probs]
    }
