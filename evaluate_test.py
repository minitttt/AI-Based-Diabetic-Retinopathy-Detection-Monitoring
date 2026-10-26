"""Evaluate the trained DR model on the frozen test split."""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import (
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    roc_auc_score,
)
from tqdm import tqdm

from deployment.backend import inference
from deployment.backend.utils import load_and_preprocess


ROOT = Path(__file__).resolve().parent
TEST_CSV = ROOT / "logs" / "test_split.csv"
OUTPUT_DIR = ROOT / "logs" / "evaluation"
CHECKPOINT = ROOT / "checkpoints" / "best_model.pth"
BOOTSTRAP_ROUNDS = 1000
SEED = 42


def predict_test_set(test_df):
    inference.load_model(CHECKPOINT)
    labels, predictions, probabilities, ids = [], [], [], []

    with torch.no_grad():
        for row in tqdm(test_df.itertuples(index=False), total=len(test_df), desc="Evaluating"):
            image = load_and_preprocess((ROOT / row.filepath).read_bytes(), img_size=inference.IMG_SIZE)
            tensor = inference.transform(image).unsqueeze(0).to(inference.DEVICE)
            probs = torch.softmax(inference.model(tensor), dim=1)[0].cpu().numpy()
            labels.append(int(row.label))
            predictions.append(int(np.argmax(probs)))
            probabilities.append(probs)
            ids.append(row.id_code)

    return np.asarray(ids), np.asarray(labels), np.asarray(predictions), np.asarray(probabilities)


def macro_auc(y_true, probabilities):
    one_hot = np.eye(len(inference.CLASS_NAMES))[y_true]
    return float(roc_auc_score(one_hot, probabilities, multi_class="ovr", average="macro"))


def bootstrap_intervals(y_true, predictions, probabilities):
    rng = np.random.default_rng(SEED)
    qwk_scores, auc_scores = [], []
    indices = np.arange(len(y_true))

    for _ in tqdm(range(BOOTSTRAP_ROUNDS), desc="Bootstrapping"):
        sample = rng.choice(indices, size=len(indices), replace=True)
        sampled_true = y_true[sample]
        sampled_probs = probabilities[sample]
        qwk_scores.append(cohen_kappa_score(sampled_true, predictions[sample], weights="quadratic"))
        auc_scores.append(macro_auc(sampled_true, sampled_probs))

    return {
        "qwk_ci_95": [float(np.percentile(qwk_scores, 2.5)), float(np.percentile(qwk_scores, 97.5))],
        "macro_auc_ci_95": [float(np.percentile(auc_scores, 2.5)), float(np.percentile(auc_scores, 97.5))],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    test_df = pd.read_csv(TEST_CSV)
    ids, y_true, y_pred, probabilities = predict_test_set(test_df)

    cm = confusion_matrix(y_true, y_pred, labels=range(len(inference.CLASS_NAMES)))
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=inference.CLASS_NAMES, yticklabels=inference.CLASS_NAMES)
    plt.xlabel("Predicted label")
    plt.ylabel("True label")
    plt.title("APTOS 2019 Test Set Confusion Matrix")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "confusion_matrix.png", dpi=200)
    plt.close()

    report = classification_report(y_true, y_pred, target_names=inference.CLASS_NAMES,
                                   labels=range(len(inference.CLASS_NAMES)), output_dict=True, zero_division=0)
    intervals = bootstrap_intervals(y_true, y_pred, probabilities)
    metrics = {
        "test_size": int(len(y_true)),
        "accuracy": float(np.mean(y_true == y_pred)),
        "qwk": float(cohen_kappa_score(y_true, y_pred, weights="quadratic")),
        "macro_auc": macro_auc(y_true, probabilities),
        "classification_report": report,
        **intervals,
    }

    with (OUTPUT_DIR / "metrics.json").open("w") as handle:
        json.dump(metrics, handle, indent=2)
    pd.DataFrame({"id_code": ids, "y_true": y_true, "y_pred": y_pred,
                        **{f"prob_{name.lower().replace(' ', '_')}": probabilities[:, i]
                            for i, name in enumerate(inference.CLASS_NAMES)}}).to_csv(
                         OUTPUT_DIR / "predictions.csv", index=False)
    print(json.dumps({key: metrics[key] for key in ["test_size", "accuracy", "qwk", "macro_auc", "qwk_ci_95", "macro_auc_ci_95"]}, indent=2))


if __name__ == "__main__":
    main()