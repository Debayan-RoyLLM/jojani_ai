"""Model loading and batched inference for the BERT clause classifier."""
import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def load_model(model_name):
    """Load tokenizer + model. Offline (local dir) when model_name is a directory."""
    offline = "/" in model_name or "\\" in model_name or model_name.startswith((".", "/"))
    kwargs = {"local_files_only": True} if offline else {}
    tokenizer = AutoTokenizer.from_pretrained(model_name, **kwargs)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, **kwargs)
    model.eval()
    return tokenizer, model


def _fmt_eta(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def predict_batched(model, tokenizer, texts, batch_size, max_length, progress=True):
    """Return list of (label, score) aligned to `texts`, with a live ETA progress line."""
    results = []
    total = len(texts)
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            enc = tokenizer(batch, return_tensors="pt", padding=True,
                            truncation=True, max_length=max_length)
            out = model(**enc).logits
            probs = out.softmax(dim=-1)
            for prob, logit in zip(probs, out):
                idx = int(logit.argmax())
                label = model.config.id2label[idx]
                results.append((label, float(prob[idx])))
            if progress:
                done = i + len(batch)
                elapsed = time.time() - t0
                rate = done / max(elapsed, 1e-6)
                eta = (total - done) / max(rate, 1e-6)
                print(f"\r  {done}/{total} ({100 * done / total:.1f}%)  "
                      f"ETA {_fmt_eta(eta)}", end="", flush=True)
    if progress:
        print()
    return results
