# 🩺 AI-Based Diabetic Retinopathy Detection & Monitoring

<p align="center">
  <img src="https://img.shields.io/badge/Model-EfficientNet--B4--NS-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Framework-PyTorch-orange?style=for-the-badge&logo=pytorch" />
  <img src="https://img.shields.io/badge/API-FastAPI-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/AUC-0.90-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/QWK-0.755-teal?style=for-the-badge" />
</p>

### 🌐 [Live Demo Available Here](https://ai-based-diabetic-retinopathy-detec.vercel.app/)

> An end-to-end research and educational system that grades Diabetic Retinopathy (DR) severity from retinal fundus photographs into five ordinal labels — No DR, Mild, Moderate, Severe, and Proliferative — using a fine-tuned EfficientNet-B4-NS backbone served via a FastAPI REST API and a web frontend. The reported metrics are from this project's data split and do not establish clinical validation or regulatory clearance.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Model Details](#model-details)
- [Training Performance](#training-performance)
- [Evaluation Metrics & Graphs](#evaluation-metrics--graphs)
- [Why This Model is Efficient for DR Detection](#why-this-model-is-efficient-for-dr-detection)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Dataset](#dataset)
- [Disclaimer](#disclaimer)

---

## Overview

Diabetic Retinopathy is the leading cause of blindness among working-age adults worldwide. Early and accurate grading is critical but requires expert ophthalmologists, which creates a bottleneck in mass screening. This project uses AI to automate severity grading from color fundus photographs, enabling faster and more scalable screening.

**The system performs:**
- 5-class DR severity grading (International Clinical DR Scale)
- Real-time inference via REST API
- Optional patient progression monitoring over time using SQLite
- Attention-map explanations for review (not lesion segmentation or diagnosis)

---

## Model Details

### Architecture — `EfficientNet-B4-NS`

| Property | Value |
|---|---|
| Backbone | `tf_efficientnet_b4_ns` (NoisyStudent pretrained) |
| Input Resolution | `380 × 380` pixels |
| Pretrained Weights | ImageNet + NoisyStudent self-training |
| Output Classes | 5 (No DR → Proliferative) |
| Feature Dimension | `1792` (from EfficientNet-B4 global avg pool) |
| Classifier Head | `Dropout(0.4) → Linear(1792→512) → GELU → BN → Dropout(0.2) → Linear(512→5)` |
| Parameters | ~19.3M (backbone) + ~0.9M (head) ≈ **~20.2M total** |
| Inference Device | CPU (or GPU if available) |
| Runtime checkpoint | `checkpoints/best_model.pth` (optional local artifact; not committed) |
| Other exports | `.onnx` and TorchScript `.pt` may be retained for experiments; the current API loader uses the `.pth` state-dict checkpoint |

### Classifier Head (detailed)

```python
nn.Sequential(
    nn.Dropout(p=0.4),
    nn.Linear(feat_dim, 512),   # feat_dim = 1792
    nn.GELU(),
    nn.BatchNorm1d(512),
    nn.Dropout(p=0.2),
    nn.Linear(512, 5),          # 5 DR severity classes
)
```

### Preprocessing Pipeline

Images are processed with the following pipeline before inference:
1. **Black-border cropping** — removes non-retinal border pixels
2. **Ben Graham illumination correction** — reduces uneven illumination
3. **CLAHE** (Contrast Limited Adaptive Histogram Equalization) — improves local contrast
4. **Resize** to `380 × 380`
5. **Normalize** with ImageNet mean/std: `mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`

### Loss & Optimization

| Setting | Value |
|---|---|
| Loss Function | Focal loss (γ=2) with inverse-frequency class weights |
| Primary Metric | Quadratic Weighted Kappa (QWK) |
| Optimizer | AdamW |
| LR Schedule | Phase A cosine annealing; Phase B cosine warm restarts |
| Learning Rates | Phase A head `1e-3`; Phase B backbone `1e-4`, head `1e-3` |
| Weight Decay | `1e-4` |
| Epochs Recorded | 9 (5 Phase A + 4 Phase B) |
| Data Augmentation | Flips, 90° rotation, shift/scale/rotate, brightness/contrast, HSV, Gaussian noise, coarse dropout |

---

## Training Performance

The stored training history contains 9 recorded epochs: 5 frozen-backbone Phase-A epochs and 4 recorded Phase-B fine-tuning epochs. The notebook configured Phase B for up to 10 epochs, but the report documents only the epochs present in `logs/training_history.csv`:

| Epoch | Train Loss | Val Loss | Train Kappa | Val Kappa | Train Acc | Val Acc | LR |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 1.092 | 0.371 | 0.417 | 0.578 | 36.2% | 47.4% | 1.0e-3 |
| 2 | 0.741 | 0.336 | 0.485 | 0.614 | 38.4% | 44.4% | 9.0e-4 |
| 3 | 0.665 | 0.300 | 0.491 | 0.612 | 39.8% | 40.3% | 6.5e-4 |
| 4 | 0.638 | 0.299 | 0.448 | 0.616 | 38.5% | 43.9% | 3.5e-4 |
| 5 | 0.604 | 0.297 | 0.503 | 0.652 | 41.1% | 43.5% | 9.6e-5 |
| 6 | 0.633 | 0.304 | 0.557 | 0.666 | 40.7% | 37.3% | 1.0e-4 |
| 7 | 0.462 | 0.279 | 0.677 | 0.689 | 51.5% | 35.3% | 9.0e-5 |
| 8 | 0.371 | 0.300 | 0.713 | 0.658 | 56.5% | 44.6% | 6.5e-5 |
| **9** | **0.308** | **0.242** | **0.751** | **0.701** | **60.4%** | **55.0%** | 3.5e-5 |

> ✅ Best model checkpoint saved at **Epoch 9** with lowest val loss `0.242` and val kappa `0.701`

### Training Curves

![Training loss, accuracy, and kappa curves over 9 epochs](logs/training_curves.png)

*The training curves show the reported loss and QWK values for this training run. These values describe the project split and are not a clinical validation study.*

---

## Evaluation Metrics & Graphs

All evaluation was performed on a held-out **test split** never seen during training.

### Summary Metrics

| Metric | Score |
|---|---|
| **Test Accuracy** | 55.6% |
| **Quadratic Weighted Kappa (QWK)** | **0.755** |
| **Macro AUC (One-vs-Rest)** | **0.901** |
| No DR — AUC | 0.991 |
| Mild — AUC | 0.882 |
| Moderate — AUC | 0.910 |
| Severe — AUC | 0.813 |
| Proliferative — AUC | 0.906 |

> **Why accuracy is lower than AUC/QWK?** DR grading is ordinal, so QWK weights errors by the distance between grade labels. The **0.755** value is the score reported for this project's held-out split; it should not be interpreted as evidence of clinical agreement or readiness for patient care.

### ROC Curves (One-vs-Rest)

![ROC curves for each DR severity class](logs/roc_curves.png)

*On this project's held-out split, the reported AUC values were above 0.88 for all classes, including **0.991 for the No-DR class**. These measurements do not establish performance on other populations or devices.*

### Confusion Matrix

![Confusion matrix on test set](logs/confusion_matrix.png)

*Most misclassifications are between adjacent grades (e.g., Mild↔Moderate), which are also difficult for human graders. There is minimal confusion between extreme grades (No DR and Proliferative).*

### Class Distribution

![Dataset class distribution](logs/class_distribution.png)

*The APTOS 2019 dataset has significant class imbalance — No DR cases dominate. The model was trained with weighted sampling and augmentation to address this imbalance.*

---

## Why This Model is Efficient for DR Detection

### 1. 🧠 Ordinal Evaluation Metric: Quadratic Weighted Kappa
Standard accuracy can hide the distance between ordinal labels. QWK penalizes misclassifications by the *square* of the grade distance. The reported **0.755** score is useful for comparing this training run, but it is not a claim of clinical agreement.

### 2. 🔬 NoisyStudent Pretraining Advantage
`EfficientNet-B4-NS` was pretrained using **NoisyStudent self-training** on 300M unlabeled ImageNet images — giving it far richer feature representations than standard ImageNet-pretrained models. This is crucial for medical imaging where labeled data is scarce.

### 3. 📐 Optimal Resolution for Fundus Images
EfficientNet-B4 uses **380×380 input** — larger than EfficientNet-B0 (224×224). This preserves fine retinal details like microaneurysms (~10–125 µm) and hard exudates that are critical for DR grading but are lost at lower resolutions.

### 4. 🎯 CLAHE Preprocessing Enhances Subtle Lesions
Raw fundus images often have poor local contrast due to variable illumination. **CLAHE** (Contrast Limited Adaptive Histogram Equalization) is applied as a preprocessing step, specifically enhancing:
- Microaneurysms (Grade 1+)
- Hemorrhages (Grade 2+)
- Hard/soft exudates (Grade 2+)
- Neovascularization (Grade 4)

This preprocessing is intended to make local contrast more consistent; any sensitivity change must be measured on the target evaluation data.

### 5. ⚡ Efficient Architecture for Deployment

| Model | Params | Accuracy | Macro AUC |
|---|---|---|---|
| ResNet-50 | 25M | ~50–53% | ~0.85 |
| VGG-16 | 138M | ~48–51% | ~0.83 |
| **EfficientNet-B4-NS (ours)** | **~20M** | **55.6%** | **0.901** |

EfficientNet achieves **higher accuracy with fewer parameters** via compound scaling (depth + width + resolution), making it faster to deploy and less memory-intensive.

### 6. 🔍 Grad-CAM Explainability
The model produces attention maps that indicate image regions associated with the screening signal. They:
- Can support technical review of an inference
- Are not lesion segmentation or proof of causality
- Should not be treated as a substitute for clinical interpretation

### 7. 📊 Reported No-DR Test-Split AUC (0.991)
The No-DR one-vs-rest AUC was **0.991** on the reported test split. This is a project metric, not a validated rule-out threshold or a replacement for specialist review.

### 8. 🏥 Deployment Considerations

The following comparison describes project goals and local software behavior, not measured clinical or production performance:

| Manual Screening | AI-Assisted (This System) |
|---|---|
| 5–10 min per patient | Measure inference time for your hardware |
| Requires specialist ophthalmologist | Runs on CPU in this implementation; size workloads before deployment |
| High inter-grader variability | Same input/model/runtime can produce repeatable software output |
| Not scalable to rural areas | API-accessible from a browser when networking and CORS are configured |

---

## Project Structure

```
Project- AI-Based Diabetic Retinopathy Detection & Monitoring/
│
├── DR_Detection_Monitoring.ipynb   # Full training & evaluation notebook
├── start.sh                        # One-command startup script
├── monitoring.db                   # Generated local SQLite DB (ignored)
│
├── checkpoints/
│   └── best_model.pth              # Optional runtime artifact; not committed
│
├── logs/
│   ├── training_curves.png         # Loss, accuracy, kappa over epochs
│   ├── confusion_matrix.png        # Per-class prediction analysis
│   ├── roc_curves.png              # AUC curves per DR grade
│   ├── class_distribution.png      # Dataset class balance
│   ├── gradcam_examples.png        # Grad-CAM visual explanations
│   ├── training_history.csv        # Raw training metrics CSV
│   └── metrics_summary.json        # Final evaluation metrics
│
├── data/                           # Local training data (ignored)
│   └── aptos2019/
│
└── deployment/
    ├── backend/
    │   ├── main.py                 # FastAPI application entry point
    │   ├── inference.py            # Model definition + predict()
    │   ├── db.py                   # SQLite patient/scan history
    │   ├── reporting.py            # Temporary PDF/CSV/JSON report artifacts
    │   └── utils.py                # Image validation and preprocessing
    │   └── uploads/                # Generated saved-scan images (ignored)
    │   └── report_artifacts/       # Generated report files (ignored)
    └── frontend/
        ├── index.html              # Main UI
        ├── styles.css              # Dark glassmorphism theme
        └── app.js                  # API integration + result rendering
```

The repository keeps evaluation visuals under `logs/` as project assets, but
the Docker build excludes `logs/`, datasets, local databases, uploads, and
generated reports. The root `.gitignore` also keeps runtime state and model
weights out of version control.

---

## Deployment

This repository has a local development flow and a Docker API image. The
checked-in frontend is a static client; the Dockerfile starts the backend only.

### Prerequisites

Use Python 3.10 or newer and install the pinned dependency set for the
backend:

```bash
python3 -m pip install -r deployment/backend/requirements.txt
```

The API's current runtime checkpoint is `checkpoints/best_model.pth`. Model
weights are intentionally excluded from Git. Supply that file separately when
you need meaningful inference; if it is absent, the current loader falls back
to untrained weights and prints a warning.

### Local development

Run the all-in-one script from the repository root:

```bash
chmod +x start.sh
./start.sh
```

The script starts:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001`
- Interactive API docs: `http://localhost:8001/docs`

For the backend alone:

```bash
cd deployment/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

The frontend's `API_BASE` is currently `http://localhost:8001`. If the API is
served at another host or port, update that frontend configuration or place a
reverse proxy in front of both services. The sidebar's **API Online** state
only confirms that `GET /` responded; it does not verify that a trained
checkpoint is present or that predictions are clinically appropriate.

### Docker API image

The Docker image exposes the backend on port `7860` (the port used by the
Dockerfile command). Build from the repository root:

```bash
docker build -t retinascan-api .
docker run --rm -p 7860:7860 retinascan-api
```

The API root is then `http://localhost:7860/`. To keep patient history,
uploaded scan images, and report artifacts outside the container, mount a
local `runtime/` directory and point the runtime variables at it:

```bash
docker run --rm -p 7860:7860 \
  -e RETINASCAN_DB_PATH=/var/lib/retinascan/monitoring.db \
  -e RETINASCAN_UPLOAD_DIR=/var/lib/retinascan/uploads \
  -e RETINASCAN_REPORT_DIR=/var/lib/retinascan/report_artifacts \
  -v "$PWD/runtime:/var/lib/retinascan" \
  retinascan-api
```

The `.dockerignore` excludes datasets, environments, local databases,
uploads, report artifacts, logs, and alternate checkpoints from the build
context. If `checkpoints/best_model.pth` exists locally, it is the one model
artifact retained for the image build; it remains ignored by Git.

The API currently permits all CORS origins for the browser client. Treat this
as development-oriented behavior and apply the networking, access-control,
and data-retention controls required by your deployment before exposing it to
untrusted networks.

### Environment variables

All supported runtime variables are optional:

| Variable | Default | Behavior |
|---|---|---|
| `RETINASCAN_MODEL_VERSION` | `EfficientNet-B4-NS` | Label included in API reports; it does not select or download model weights. |
| `RETINASCAN_DB_PATH` | Repository-root `monitoring.db` | SQLite database for patient profiles and saved scans. Relative paths are anchored to the repository root. |
| `RETINASCAN_UPLOAD_DIR` | `deployment/backend/uploads/` | Directory for images attached to saved patient scans. Relative paths are anchored to the repository root. |
| `RETINASCAN_REPORT_DIR` | `deployment/backend/report_artifacts/` | Directory for temporary PDF/CSV/JSON and image artifacts. Relative paths are anchored to the backend directory. |
| `RETINASCAN_REPORT_TTL_SECONDS` | `86400` (24 hours) | Artifact lifetime used during cleanup; invalid values use the default and values below 60 seconds are clamped to 60. |

Report cleanup is best-effort and runs when a new report is created; an old
artifact is not necessarily removed at the exact expiry second. The API has
no separate `PORT` or model-path environment variable: local and Docker ports
are set by their respective commands, and the checkpoint path is fixed at
`checkpoints/best_model.pth`.

---

## API Reference

### `GET /`
Root health/reachability endpoint. It returns a small JSON response when the
FastAPI process is reachable:
```json
{ "message": "DR Detection API is running" }
```

There is no separate `/health` route. A successful response from `/` confirms
API reachability, not clinical validity or the presence of trained model
weights.

### Patient profiles and history

Patient history is optional and is stored in SQLite:

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/patients` | List patient profiles with latest-scan summaries. |
| `POST` | `/patients` | Create a profile; `name` is required and `patient_id` is optional. |
| `GET` | `/patients/{patient_id}` | Return one profile, saved scans, and ordinal progression summary. |
| `GET` | `/patients/{patient_id}/scans` | Return that patient's saved scans in chronological order. |

`POST /predict` accepts optional form fields `patient_id`, `scan_date`
(`YYYY-MM-DD`), `eye`, `notes`, and `save_scan`. Supplying a patient ID saves
the scan by default; `save_scan=false` performs a preview without persisting
the scan. Without a patient ID, the prediction is stateless. A saved scan
stores its generated image basename and prediction in the configured upload
directory and SQLite database.

### `POST /predict`
Upload a fundus image for DR grading.

**Request:** `multipart/form-data` with required field `file`. The backend
decodes readable JPEG, PNG, BMP, or WebP-style image uploads and rejects files
that do not resemble a fundus image. The frontend limits uploads to 20 MB.

**Response:**
```json
{
  "filename": "fundus_left.jpg",
  "saved": false,
  "scan": null,
  "prediction": {
    "grade_idx": 2,
    "grade_name": "Moderate",
    "confidence": 0.847,
    "probabilities": [0.02, 0.05, 0.847, 0.06, 0.023]
  },
  "report_id": "<32-character-hex-id>",
  "report_urls": {
    "json": "/reports/<id>/json",
    "csv": "/reports/<id>/csv",
    "pdf": "/reports/<id>/pdf"
  }
}
```

The response also includes full report metadata under `report`. When a scan is
saved, the response includes the saved scan identifiers and metadata. The
attention image is an explanatory visualization, not a diagnosis or lesion
segmentation.

| Grade Index | Grade Name | Clinical Description |
|:---:|---|---|
| 0 | No DR | No signs of diabetic retinopathy |
| 1 | Mild | Microaneurysms only |
| 2 | Moderate | More than just microaneurysms, less than severe |
| 3 | Severe | Extensive hemorrhages in 4 quadrants, venous beading |
| 4 | Proliferative | Neovascularization, fibrous proliferation |

### Report artifacts

Each prediction creates a temporary report bundle with these endpoints:

| Method | Path | Format |
|---|---|---|
| `GET` | `/reports/{report_id}` | Report metadata JSON response |
| `GET` | `/reports/{report_id}/json` | Downloadable JSON export |
| `GET` | `/reports/{report_id}/csv` | Downloadable one-row CSV export |
| `GET` | `/reports/{report_id}/pdf` | PDF screening report |
| `GET` | `/reports/{report_id}/image` | JPEG preview of the uploaded image |
| `GET` | `/reports/{report_id}/attention` | JPEG attention-map overlay |

The default report TTL is 24 hours and can be changed with
`RETINASCAN_REPORT_TTL_SECONDS`. Artifacts are cleaned up on a best-effort
basis when later reports are created, so callers should download anything they
need before expiry.

---

## Frontend

The web interface (`RetinaScan AI`) features:
- **Drag & drop** or browse fundus image upload
- **Animated scanning** overlay during inference
- **Per-class probability bars** with color-coded DR grades
- **Confidence meter** for the top prediction
- **Optional patient profiles and scan-history timeline**
- **Downloadable PDF, CSV, and JSON report artifacts**, plus preview/attention images
- **API status indicator** (bottom of sidebar) — checks the backend root endpoint

---

## Dataset

This project uses the **APTOS 2019 Blindness Detection** dataset from Kaggle:
- ~3,662 retinal fundus images (train set)
- Labeled by expert ophthalmologists on a 0–4 scale
- Significant class imbalance (majority No-DR)
- High variability in image quality, lighting, and camera type

---

## Disclaimer

> ⚠️ **This system is intended for research and educational purposes only.** It is not a certified or clinically validated medical device, and it should not be used as a substitute for diagnosis by a qualified ophthalmologist. The repository does not provide deployment security, authentication, audit controls, or a clinical data-retention program by default. Do not use predictions for clinical decisions without appropriate independent validation, qualified review, and deployment controls.

---

<p align="center">Made with ❤️ for accessible AI-assisted ophthalmology screening</p>
