"""Vẽ heatmap retention từ docs/cohort_retention.csv -> docs/evidence/03-cohort.png.

Chạy từ thư mục gốc repo:  python scripts/cohort_heatmap.py
Ô trống trong CSV (tháng chưa quan sát được) được để trắng, không tô màu.
"""
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "cohort_retention.csv"
OUT = ROOT / "docs" / "evidence" / "03-cohort.png"

with SRC.open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

month_cols = [c for c in rows[0] if c.startswith("m") and c[1:].isdigit()]
labels = [f"{r['cohort_month']}  (n={r['cohort_size']})" for r in rows]
data = np.array(
    [[float(r[c]) if r[c] else np.nan for c in month_cols] for r in rows]
)

fig, ax = plt.subplots(figsize=(9, 4.5))
im = ax.imshow(np.ma.masked_invalid(data), cmap="Blues", vmin=0, vmax=100, aspect="auto")

ax.set_xticks(range(len(month_cols)), [c.upper() for c in month_cols])
ax.set_yticks(range(len(labels)), labels)
ax.set_xlabel("Số tháng kể từ tháng mua đầu tiên")
ax.set_title("Cohort retention theo tháng (% customer còn mua)")

for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    color="white" if v >= 55 else "black", fontsize=9)

fig.colorbar(im, ax=ax, label="% retention")
fig.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=150)
print(f"Saved {OUT}")
