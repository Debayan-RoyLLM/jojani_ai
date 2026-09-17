import csv
import os

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "apify_reviews_joined.csv")
rows = list(csv.DictReader(open(path)))
n = 0
for r in rows:
    if r["translated_content"].strip():
        r["content"] = r["translated_content"].strip()
        n += 1
fieldnames = [c for c in rows[0].keys() if c != "translated_content"]
with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print("swapped", n, "of", len(rows))
