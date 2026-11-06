"""
Create a review list for PDFs sharing the same detected year and epidemiological week.

This script does not delete files or decide which report is correct.
Run separate_dengue_years.py first.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "reports" / "pdf_inventory.csv"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "duplicate_year_week_review.csv"


def main():
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(
            "Inventory not found. Run: python src/separate_dengue_years.py"
        )

    df = pd.read_csv(INVENTORY_PATH)

    required = {"detected_year", "detected_week", "filename", "source_path"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Inventory is missing columns: {sorted(missing)}")

    usable = df.dropna(subset=["detected_year", "detected_week"]).copy()
    repeated_keys = (
        usable.groupby(["detected_year", "detected_week"])
              .size()
              .reset_index(name="file_count")
    )
    repeated_keys = repeated_keys[repeated_keys["file_count"] > 1]

    review = usable.merge(
        repeated_keys,
        on=["detected_year", "detected_week"],
        how="inner"
    )

    review["review_status"] = "NOT REVIEWED"
    review["report_type_or_revision"] = ""
    review["publication_date"] = ""
    review["verified_case_total"] = ""
    review["decision"] = ""
    review["review_notes"] = ""

    review = review.sort_values(
        ["detected_year", "detected_week", "filename"]
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(OUTPUT_PATH, index=False)

    print(f"Duplicate review candidates: {len(review)} PDF files")
    if review.empty:
        print("No repeated year-week combinations found.")
    else:
        print(review[
            ["detected_year", "detected_week", "file_count", "filename"]
        ].to_string(index=False))

    print(f"\nReview file saved to: {OUTPUT_PATH}")
    print("Do not delete a report until its contents and revision status are checked.")


if __name__ == "__main__":
    main()
