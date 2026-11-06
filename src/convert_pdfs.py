
from pathlib import Path
import pdfplumber
import pandas as pd

# Project directories
INPUT_DIR = Path("data/raw/dengue")
OUTPUT_DIR = Path("data/processed/dengue")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Store extracted table rows
all_rows = []

# Find all PDF files, including files inside year folders
pdf_files = list(INPUT_DIR.rglob("*.pdf"))

print(f"Found {len(pdf_files)} PDF files.")

for pdf_path in pdf_files:

    print(f"\nProcessing: {pdf_path.name}")

    try:
        with pdfplumber.open(pdf_path) as pdf:

            for page_number, page in enumerate(
                pdf.pages, start=1
            ):

                tables = page.extract_tables()

                for table_number, table in enumerate(
                    tables, start=1
                ):

                    if not table:
                        continue

                    for row_number, row in enumerate(
                        table, start=1
                    ):

                        all_rows.append({
                            "source_pdf": pdf_path.name,
                            "year_folder": pdf_path.parent.name,
                            "page_number": page_number,
                            "table_number": table_number,
                            "row_number": row_number,
                            "extracted_row": row
                        })

        print("Completed:", pdf_path.name)

    except Exception as error:
        print("Error:", pdf_path.name, error)


# Convert extracted rows into a DataFrame
if all_rows:

    max_columns = max(
        len(item["extracted_row"])
        for item in all_rows
    )

    records = []

    for item in all_rows:

        record = {
            "source_pdf": item["source_pdf"],
            "year_folder": item["year_folder"],
            "page_number": item["page_number"],
            "table_number": item["table_number"],
            "row_number": item["row_number"]
        }

        for i in range(max_columns):
            row = item["extracted_row"]

            record[f"column_{i+1}"] = (
                row[i] if i < len(row) else None
            )

        records.append(record)

    df = pd.DataFrame(records)

    # Export Excel
    excel_path = OUTPUT_DIR / "dengue_extracted_tables.xlsx"
    df.to_excel(excel_path, index=False)

    # Export CSV
    csv_path = OUTPUT_DIR / "dengue_extracted_tables.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print("\nConversion completed!")
    print("Excel:", excel_path)
    print("CSV:", csv_path)
    print("Extracted rows:", len(df))

else:
    print("\nNo tables were extracted.")
    print("Check whether the PDFs contain selectable text.")
