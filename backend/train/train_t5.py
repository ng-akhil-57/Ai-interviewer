"""
backend/train/train_t5.py  —  STEP 4
Fine-tunes T5-small to generate interview questions
from resume context (skills, projects, experience).

Run: python backend/train/train_t5.py
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import json
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from transformers import (
    T5Tokenizer,
    T5ForConditionalGeneration,
    get_linear_schedule_with_warmup
)

from torch.optim import AdamW
from sklearn.model_selection import train_test_split
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────────────────
QA_PATH    = Path("data/processed/qa_pairs.json")
MODEL_DIR  = Path("models/t5")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

T5_MODEL   = "t5-small"
MAX_INPUT  = 256
MAX_OUTPUT = 64
BATCH_SIZE = 8
EPOCHS     = 5
LR         = 3e-4
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

print(f"⚙️  Using device: {DEVICE}")


# ── DATASET ──────────────────────────────────────────────────────────────────
class QADataset(Dataset):
    def __init__(self, pairs, tokenizer):
        self.pairs     = pairs
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        pair = self.pairs[idx]

        # Input: "generate question: <context>"
        input_text  = f"generate question: {pair['context']}"
        target_text = pair["question"]

        inputs = self.tokenizer(
            input_text,
            max_length=MAX_INPUT,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        targets = self.tokenizer(
            target_text,
            max_length=MAX_OUTPUT,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        labels = targets["input_ids"].squeeze()
        # Replace padding token id with -100 so loss ignores it
        labels[labels == self.tokenizer.pad_token_id] = -100

        return {
            "input_ids":      inputs["input_ids"].squeeze(),
            "attention_mask": inputs["attention_mask"].squeeze(),
            "labels":         labels,
        }


# ── LOAD DATA ────────────────────────────────────────────────────────────────
def load_data():
    if not QA_PATH.exists():
        raise FileNotFoundError(
            "❌ data/processed/qa_pairs.json not found!\n"
            "   Run: python backend/train/prepare_data.py first."
        )
    with open(QA_PATH, encoding="utf-8") as f:
        pairs = json.load(f)

    # Filter: keep pairs that have non-empty context and question
    pairs = [p for p in pairs if p.get("context","").strip() and p.get("question","").strip()]
    print(f"   Total QA pairs: {len(pairs)}")
    return pairs


# ── TRAIN ────────────────────────────────────────────────────────────────────
def train():
    print("📂 Loading QA data...")
    pairs = load_data()

    train_pairs, val_pairs = train_test_split(pairs, test_size=0.1, random_state=42)

    print("🔤 Loading T5 tokenizer...")
    tokenizer = T5Tokenizer.from_pretrained(T5_MODEL)

    train_ds = QADataset(train_pairs, tokenizer)
    val_ds   = QADataset(val_pairs,   tokenizer)

    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    print("🧠 Loading T5 model...")
    model = T5ForConditionalGeneration.from_pretrained(T5_MODEL).to(DEVICE)

    optimizer   = AdamW(model.parameters(), lr=LR)
    total_steps = len(train_dl) * EPOCHS
    scheduler   = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=total_steps // 10,
        num_training_steps=total_steps,
    )

    best_val_loss = float("inf")

    print(f"\n🚀 Training for {EPOCHS} epochs...\n")
    for epoch in range(EPOCHS):
        # ── Train ──
        model.train()
        total_loss = 0

        for batch in tqdm(train_dl, desc=f"Epoch {epoch+1}/{EPOCHS} [Train]"):
            input_ids      = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels         = batch["labels"].to(DEVICE)

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss    = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()

        avg_train_loss = total_loss / len(train_dl)

        # ── Validate ──
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_dl:
                input_ids      = batch["input_ids"].to(DEVICE)
                attention_mask = batch["attention_mask"].to(DEVICE)
                labels         = batch["labels"].to(DEVICE)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                val_loss += outputs.loss.item()

        avg_val_loss = val_loss / len(val_dl)
        print(f"   Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")

        # Sample a generated question
        model.eval()
        sample = val_pairs[0]["context"][:200]
        inp    = tokenizer(f"generate question: {sample}", return_tensors="pt", truncation=True, max_length=MAX_INPUT).to(DEVICE)
        out    = model.generate(**inp, max_length=MAX_OUTPUT, num_beams=4, early_stopping=True)
        print(f"   🔎 Sample Q: {tokenizer.decode(out[0], skip_special_tokens=True)}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            model.save_pretrained(MODEL_DIR)
            tokenizer.save_pretrained(MODEL_DIR)
            print(f"   💾 Best model saved (val_loss={avg_val_loss:.4f})")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║              ✅ T5 TRAINING COMPLETE!                    ║
╠══════════════════════════════════════════════════════════╣
║  Best Val Loss  : {best_val_loss:.4f}                            ║
║  Model saved to : models/t5/                             ║
╚══════════════════════════════════════════════════════════╝

Next → Run: python backend/app.py
""")


if __name__ == "__main__":
    train()