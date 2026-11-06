"""
Organise dengue weekly-report PDFs by detected report year.

Important:
- Original PDFs are never moved or deleted.
- Detection is heuristic. Always inspect the generated CSV.
- Put source PDFs in data/raw/dengue_pdfs/ before running.
"""

from pathlib import Path
import re
import shutil
import pandas as pd
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "dengue_pdfs"
YEAR_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "dengue_pdfs_by_year"
REPORTS_DIR = PROJECT_ROOT / "reports"

YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
WEEK_PATTERNS = [
    re.compile(r"\b(?:epidemiological\s+)?week\s*[:#\-]?\s*0?(\d{1,2})\b", re.I),
    re.compile(r"\bweek\s*no\.?\s*[:#\-]?\s*0?(\d{1,2})\b", re.I),
]


def read_first_pages(pdf_path: Path, page_limit: int = 2) -> str:
    """Extract text from the first few pages; return empty text if extraction fails."""
    try:
        reader = PdfReader(str(pdf_path))
        return "\n".join(
            (page.extract_text() or "") for page in reader.pages[:page_limit]
        )
    except Exception as exc:
        print(f"Could not read PDF text from {pdf_path.name}: {exc}")
        return ""


def detect_year(filename: str, text: str):
    """Prefer a year in the filename; otherwise use the first year found in PDF text."""
    filename_years = YEAR_PATTERN.findall(filename)
    text_years = YEAR_PATTERN.findall(text)
    candidates = filename_years or text_years
    return int(candidates[0]) if candidates else None


def detect_week(text: str):
    """Return the first plausible epidemiological week (1–53), otherwise None."""
    for pattern in WEEK_PATTERNS:
        match = pattern.search(text)
        if match:
            week = int(match.group(1))
            if 1 <= week <= 53:
                return week
    return None


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    YEAR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not PDF_INPUT_DIR.exists():
        raise FileNotFoundError(
            f"PDF input folder does not exist: {PDF_INPUT_DIR}\n"
            "Create it and place the original weekly-report PDFs inside."
        )

    pdf_files = sorted(PDF_INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {PDF_INPUT_DIR}")
        return

    records = []

    for pdf_path in pdf_files:
        text = read_first_pages(pdf_path)
        year = detect_year(pdf_path.name, text)
        week = detect_week(text)

        destination = ""
        if year is not None:
            year_folder = YEAR_OUTPUT_DIR / str(year)
            year_folder.mkdir(parents=True, exist_ok=True)
            target = year_folder / pdf_path.name

            # Avoid overwriting a different file with the same name.
            if not target.exists():
                shutil.copy2(pdf_path, target)
            destination = str(target.relative_to(PROJECT_ROOT))

        records.append({
            "filename": pdf_path.name,
            "detected_year": year,
            "detected_week": week,
            "year_week_key": f"{year}-W{week:02d}" if year and week else "",
            "source_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "copied_path": destination,
            "manual_review_required": year is None or week is None,
        })

    df = pd.DataFrame(records)
    inventory_path = REPORTS_DIR / "pdf_inventory.csv"
    unclassified_path = REPORTS_DIR / "pdf_inventory_unclassified.csv"

    df.to_csv(inventory_path, index=False)
    df[df["manual_review_required"]].to_csv(unclassified_path, index=False)

    print("\nPDF counts by detected year:")
    print(df["detected_year"].fillna("Unclassified").value_counts().sort_index())

    repeated = (
        df.dropna(subset=["detected_year", "detected_week"])
          .groupby(["detected_year", "detected_week"])
          .size()
          .reset_index(name="file_count")
    )
    repeated = repeated[repeated["file_count"] > 1]

    print("\nRepeated year-week combinations (review candidates):")
    if repeated.empty:
        print("None detected.")
    else:
        for row in repeated.itertuples(index=False):
            print(f"{int(row.detected_year)} Week {int(row.detected_week):02d}: "
                  f"{row.file_count} files")

    print(f"\nInventory saved to: {inventory_path}")
    print(f"Unclassified PDFs saved to: {unclassified_path}")
    print("Original PDFs were not moved or deleted.")


if __name__ == "__main__":
    main()
