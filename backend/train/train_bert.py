"""
backend/train/train_bert.py
Fine-tunes BERT on processed resume data.

Run:
python backend/train/train_bert.py
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import json
import torch
from collections import Counter
from pathlib import Path
from torch.utils.data import Dataset, DataLoader

from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    get_linear_schedule_with_warmup,
)

from torch.optim import AdamW

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from tqdm import tqdm


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

DATA_PATH = Path("data/processed/parsed_resumes.json")

MODEL_DIR = Path("models/bert")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

BERT_MODEL = "bert-base-uncased"

MAX_LEN = 256
BATCH_SIZE = 8
EPOCHS = 5
LR = 2e-5

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"⚙️ Using device: {DEVICE}")


# ─────────────────────────────────────────────────────────────
# DATASET CLASS
# ─────────────────────────────────────────────────────────────

class ResumeDataset(Dataset):

    def __init__(self, texts, labels, tokenizer, max_len):

        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):

        return len(self.texts)

    def __getitem__(self, idx):

        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "label": torch.tensor(self.labels[idx], dtype=torch.long)
        }


# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────

def load_data():

    if not DATA_PATH.exists():

        raise FileNotFoundError(
            f"\n❌ File not found: {DATA_PATH}\n"
            f"Run prepare_data.py first.\n"
        )

    with open(DATA_PATH, "r", encoding="utf-8") as f:

        resumes = json.load(f)

    texts = []
    labels = []

    for r in resumes:

        text = " ".join([
            r.get("sections", {}).get("summary", ""),
            r.get("sections", {}).get("skills", ""),
            r.get("sections", {}).get("experience", ""),
            r.get("sections", {}).get("education", "")
        ])

        text = text[:1000]

        texts.append(text)

        labels.append(r.get("domain", "Unknown"))

    return texts, labels


# ─────────────────────────────────────────────────────────────
# TRAIN FUNCTION
# ─────────────────────────────────────────────────────────────

def train():

    print("\n📂 Loading dataset...")

    texts, raw_labels = load_data()

    print(f"✅ Total resumes: {len(texts)}")

    # Encode labels
    label_encoder = LabelEncoder()

    labels = label_encoder.fit_transform(raw_labels)

    num_classes = len(label_encoder.classes_)

    print(f"✅ Domains: {list(label_encoder.classes_)}")

    # Save labels
    with open(MODEL_DIR / "label_classes.json", "w") as f:

        json.dump(label_encoder.classes_.tolist(), f)

    # Split dataset
        # Count samples per class
        label_counts = Counter(labels)

        # Check minimum samples
        min_samples = min(label_counts.values())

        print(f"📊 Label Counts: {label_counts}")

        # If any class has less than 2 samples, disable stratify
        if min_samples < 2:

            print("⚠️ Some classes have less than 2 samples.")
            print("⚠️ Using normal train/test split without stratify.")

            X_train, X_val, y_train, y_val = train_test_split(
                texts,
                labels,
                test_size=0.2,
                random_state=42
            )

        else:

            X_train, X_val, y_train, y_val = train_test_split(
                texts,
                labels,
                test_size=0.2,
                random_state=42,
                stratify=labels
            )

    # Tokenizer
    print("\n🔤 Loading tokenizer...")

    tokenizer = BertTokenizer.from_pretrained(BERT_MODEL)

    # Dataset
    train_dataset = ResumeDataset(
        X_train,
        y_train,
        tokenizer,
        MAX_LEN
    )

    val_dataset = ResumeDataset(
        X_val,
        y_val,
        tokenizer,
        MAX_LEN
    )

    # Dataloader
    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE
    )

    # Model
    print("\n🧠 Loading BERT model...")

    model = BertForSequenceClassification.from_pretrained(
        BERT_MODEL,
        num_labels=num_classes
    )

    model.to(DEVICE)

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=LR
    )

    total_steps = len(train_loader) * EPOCHS

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=total_steps // 10,
        num_training_steps=total_steps
    )

    best_val_acc = 0.0

    print(f"\n🚀 Starting Training ({EPOCHS} epochs)\n")

    # ─────────────────────────────────────────────────────────
    # TRAIN LOOP
    # ─────────────────────────────────────────────────────────

    for epoch in range(EPOCHS):

        print(f"\n========== Epoch {epoch + 1}/{EPOCHS} ==========")

        model.train()

        total_loss = 0
        correct = 0
        total = 0

        for batch in tqdm(train_loader):

            input_ids = batch["input_ids"].to(DEVICE)

            attention_mask = batch["attention_mask"].to(DEVICE)

            labels_batch = batch["label"].to(DEVICE)

            optimizer.zero_grad()

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels_batch
            )

            loss = outputs.loss

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0
            )

            optimizer.step()

            scheduler.step()

            total_loss += loss.item()

            preds = torch.argmax(outputs.logits, dim=1)

            correct += (preds == labels_batch).sum().item()

            total += labels_batch.size(0)

        train_acc = correct / total

        avg_loss = total_loss / len(train_loader)

        # ─────────────────────────────────────────────────────
        # VALIDATION
        # ─────────────────────────────────────────────────────

        model.eval()

        val_correct = 0
        val_total = 0

        with torch.no_grad():

            for batch in val_loader:

                input_ids = batch["input_ids"].to(DEVICE)

                attention_mask = batch["attention_mask"].to(DEVICE)

                labels_batch = batch["label"].to(DEVICE)

                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask
                )

                preds = torch.argmax(outputs.logits, dim=1)

                val_correct += (preds == labels_batch).sum().item()

                val_total += labels_batch.size(0)

        val_acc = val_correct / val_total

        print(f"\n📊 Loss      : {avg_loss:.4f}")
        print(f"📊 Train Acc : {train_acc:.2%}")
        print(f"📊 Val Acc   : {val_acc:.2%}")

        # Save best model
        if val_acc > best_val_acc:

            best_val_acc = val_acc

            model.save_pretrained(MODEL_DIR)

            tokenizer.save_pretrained(MODEL_DIR)

            print("\n💾 Best model saved!")

    print("\n" + "=" * 60)

    print("✅ TRAINING COMPLETED")

    print(f"🏆 Best Validation Accuracy: {best_val_acc:.2%}")

    print(f"📁 Model saved in: {MODEL_DIR}")

    print("=" * 60)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    train()