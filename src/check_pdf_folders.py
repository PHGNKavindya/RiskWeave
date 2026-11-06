from pathlib import Path

# Project root directory
PROJECT_DIR = Path(__file__).resolve().parents[1]

# Input directory containing downloaded PDFs
INPUT_DIR = PROJECT_DIR / "data" / "raw" / "dengue"

# Output directory
OUTPUT_DIR = PROJECT_DIR / "data" / "processed" / "dengue"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Project directory:", PROJECT_DIR)
print("Input directory:", INPUT_DIR)
print("Output directory:", OUTPUT_DIR)
print("Input folder exists:", INPUT_DIR.exists())

print("\nChecking for PDF files...")

if INPUT_DIR.exists():

    pdf_files = list(INPUT_DIR.rglob("*.pdf"))

    print("Total PDF files found:", len(pdf_files))

    for pdf in pdf_files[:10]:
        print("  ", pdf)

else:
    print("\nERROR: Input folder does not exist!")