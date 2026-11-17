
import pandas as pd
from pathlib import Path

folder = Path("data/raw/dengue")

old_file = folder / "dengue_cases_2025_2026_backup_20261118_003009.csv"
new_file = folder / "dengue_cases_2025_2026.csv"

old = pd.read_csv(old_file)
new = pd.read_csv(new_file)

for name, df in [("BACKUP", old), ("UPDATED", new)]:
    week = df[
        (df["year"] == 2026) &
        (df["week"] == 44)
    ]

    print(f"\n{name}")
    print("Districts:", week["district"].nunique())
    print("Cases:", week["weekly_cases"].sum())
    print("Records:", len(week))
