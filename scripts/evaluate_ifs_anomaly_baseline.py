
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

IFS_TEST_FILE = (
    PROJECT_ROOT
    / "data/raw/environmental_anomalies"
    / "ifs_comparison_2024_2025.csv"
)

ERA5_FILE = (
    PROJECT_ROOT
    / "data/processed/weather_era5_combined_2006_2026.csv"
)

IFS_BASELINE_FILE = (
    PROJECT_ROOT
    / "data/processed/environmental_anomalies"
    / "ifs_baseline_2017_2023"
    / "ifs_district_monthly_baselines_2017_2023.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data/processed/environmental_anomalies"
    / "ifs_baseline_evaluation_2024_2025"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MATCHED_OUTPUT = OUTPUT_DIR / "ifs_anomaly_test_2024_2025.csv"
METRICS_OUTPUT = OUTPUT_DIR / "ifs_anomaly_evaluation_metrics.csv"
DISTRICT_OUTPUT = OUTPUT_DIR / "ifs_anomaly_district_metrics.csv"
MONTHLY_OUTPUT = OUTPUT_DIR / "ifs_anomaly_monthly_metrics.csv"

# ============================================================
# 2. CONFIGURATION
# ============================================================

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

ANOMALY_SUFFIXES = {
    "precipitation_sum": "rainfall",
    "temperature_2m_mean": "temperature",
    "relative_humidity_2m_mean": "humidity"
}

ERA5_BASELINE_START = "2007-01-01"
ERA5_BASELINE_END = "2023-12-31"

IFS_BASELINE_START = "2017-01-01"
IFS_BASELINE_END = "2023-12-31"

TEST_START = "2024-01-01"
TEST_END = "2025-12-31"

EXPECTED_DISTRICTS = 25
EXPECTED_TEST_RECORDS = 25 * 731

LOWER_QUANTILE = 0.01
UPPER_QUANTILE = 0.99

# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def check_required_columns(df, columns, dataset_name):

    missing = [
        col for col in columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{dataset_name} is missing columns: {missing}"
        )


def prepare_weather_data(df, dataset_name):

    required = [
        "district",
        "date"
    ] + VARIABLES

    check_required_columns(
        df,
        required,
        dataset_name
    )

    df = df[required].copy()

    df["district"] = (
        df["district"].astype(str).str.strip()
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    for variable in VARIABLES:
        df[variable] = pd.to_numeric(
            df[variable],
            errors="coerce"
        )

    if df["date"].isna().any():
        raise ValueError(
            f"{dataset_name}: Invalid dates found."
        )

    if df.duplicated(["district", "date"]).any():
        raise ValueError(
            f"{dataset_name}: Duplicate district-date records."
        )

    return df


def calculate_thresholds(df, dataset_name):

    """
    Calculate district-month q01 and q99 thresholds.

    Missing observations are excluded independently
    for each weather variable.
    """

    rows = []

    for (district, month), group in df.groupby(
        ["district", "month"],
        sort=True
    ):

        row = {
            "district": district,
            "month": int(month)
        }

        for variable in VARIABLES:

            values = group[variable].dropna()

            if len(values) == 0:
                raise ValueError(
                    f"No valid observations for "
                    f"{dataset_name}: {district}, "
                    f"month {month}, {variable}"
                )

            row[f"{variable}_q01"] = values.quantile(
                LOWER_QUANTILE
            )

            row[f"{variable}_q99"] = values.quantile(
                UPPER_QUANTILE
            )

            row[f"{variable}_valid_count"] = len(values)

        rows.append(row)

    thresholds = pd.DataFrame(rows)

    if len(thresholds) != EXPECTED_DISTRICTS * 12:
        raise ValueError(
            f"{dataset_name}: Expected 300 threshold groups, "
            f"found {len(thresholds)}."
        )

    if thresholds.duplicated(
        ["district", "month"]
    ).any():
        raise ValueError(
            f"{dataset_name}: Duplicate threshold groups."
        )

    return thresholds


def apply_thresholds(df, thresholds, source_name):

    """
    Apply district-month q01/q99 thresholds
    and create anomaly flags.
    """

    result = df.copy()

    result["month"] = result["date"].dt.month

    result = result.merge(
        thresholds,
        on=["district", "month"],
        how="left",
        validate="many_to_one",
        indicator=True
    )

    if not (result["_merge"] == "both").all():
        raise ValueError(
            f"{source_name}: Some observations have no thresholds."
        )

    result = result.drop(columns="_merge")

    for variable in VARIABLES:

        suffix = ANOMALY_SUFFIXES[variable]

        lower = result[f"{variable}_q01"]
        upper = result[f"{variable}_q99"]

        result[f"{suffix}_{source_name}_anomaly"] = (
            (result[variable] < lower)
            |
            (result[variable] > upper)
        )

    return result


def calculate_metrics(reference, comparison):

    """
    Compare two binary anomaly classifications.

    ERA5 is treated as the reference classification,
    not as ground truth.
    """

    reference = reference.astype(bool)
    comparison = comparison.astype(bool)

    tp = int((reference & comparison).sum())
    tn = int((~reference & ~comparison).sum())
    fp = int((~reference & comparison).sum())
    fn = int((reference & ~comparison).sum())

    total = tp + tn + fp + fn

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0 else np.nan
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0 else np.nan
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (
            pd.notna(precision)
            and pd.notna(recall)
            and (precision + recall) > 0
        )
        else np.nan
    )

    agreement = (
        (tp + tn) / total
        if total > 0 else np.nan
    )

    return {
        "records": total,
        "reference_anomalies": int(reference.sum()),
        "comparison_anomalies": int(comparison.sum()),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "overall_agreement": agreement,
        "precision": precision,
        "recall": recall,
        "f1_score": f1
    }


# ============================================================
# 4. LOAD DATASETS
# ============================================================

print("\n" + "=" * 65)
print("IFS ANOMALY BASELINE EVALUATION")
print("=" * 65)

ifs_raw = pd.read_csv(
    IFS_TEST_FILE,
    parse_dates=["date"]
)

era5_raw = pd.read_csv(
    ERA5_FILE,
    parse_dates=["date"]
)

ifs_baseline = pd.read_csv(
    IFS_BASELINE_FILE
)

print("\nIFS test shape:", ifs_raw.shape)
print("ERA5 historical shape:", era5_raw.shape)
print("IFS baseline shape:", ifs_baseline.shape)

# ============================================================
# 5. PREPARE DATA
# ============================================================

ifs = prepare_weather_data(
    ifs_raw,
    "IFS test dataset"
)

era5 = prepare_weather_data(
    era5_raw,
    "ERA5 dataset"
)

ifs_baseline["district"] = (
    ifs_baseline["district"].astype(str).str.strip()
)

print("\nIFS districts:", ifs["district"].nunique())
print("ERA5 districts:", era5["district"].nunique())

# ============================================================
# 6. SPLIT ERA5 BASELINE AND TEST DATA
# ============================================================

print("\nPreparing ERA5 baseline and test periods...")

era5_train = era5.loc[
    era5["date"].between(
        ERA5_BASELINE_START,
        ERA5_BASELINE_END
    )
].copy()

era5_test = era5.loc[
    era5["date"].between(
        TEST_START,
        TEST_END
    )
].copy()

ifs_test = ifs.loc[
    ifs["date"].between(
        TEST_START,
        TEST_END
    )
].copy()

# ============================================================
# 7. VALIDATE TEST DATA
# ============================================================

print("\n" + "=" * 65)
print("TEST DATA VALIDATION")
print("=" * 65)

print("ERA5 baseline records:", len(era5_train))
print("ERA5 test records:", len(era5_test))
print("IFS test records:", len(ifs_test))

if era5_train.empty:
    raise ValueError("ERA5 baseline period is empty.")

if len(era5_test) != EXPECTED_TEST_RECORDS:
    raise ValueError(
        f"Expected {EXPECTED_TEST_RECORDS} ERA5 test records, "
        f"found {len(era5_test)}."
    )

if len(ifs_test) != EXPECTED_TEST_RECORDS:
    raise ValueError(
        f"Expected {EXPECTED_TEST_RECORDS} IFS test records, "
        f"found {len(ifs_test)}."
    )

for name, frame in [
    ("ERA5 test", era5_test),
    ("IFS test", ifs_test)
]:

    if frame[VARIABLES].isna().any().any():
        raise ValueError(
            f"{name} contains missing weather observations."
        )

    if frame["district"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError(
            f"{name} does not contain 25 districts."
        )

# ============================================================
# 8. CALCULATE ERA5-SPECIFIC BASELINE
# ============================================================

print("\n" + "=" * 65)
print("CALCULATING ERA5 BASELINE: 2007-2023")
print("=" * 65)

era5_train["month"] = era5_train["date"].dt.month

era5_thresholds = calculate_thresholds(
    era5_train,
    "ERA5"
)

print("ERA5 threshold groups:", len(era5_thresholds))

# ============================================================
# 9. VALIDATE IFS BASELINE
# ============================================================

print("\n" + "=" * 65)
print("VALIDATING IFS BASELINE: 2017-2023")
print("=" * 65)

required_ifs_thresholds = [
    "district",
    "month"
]

for variable in VARIABLES:

    required_ifs_thresholds.extend([
        f"{variable}_q01",
        f"{variable}_q99"
    ])

check_required_columns(
    ifs_baseline,
    required_ifs_thresholds,
    "IFS baseline"
)

if len(ifs_baseline) != 300:
    raise ValueError(
        "IFS baseline must contain 300 groups."
    )

print("IFS threshold groups:", len(ifs_baseline))

# ============================================================
# 10. APPLY SOURCE-SPECIFIC THRESHOLDS
# ============================================================

print("\nApplying ERA5-specific thresholds...")

era5_classified = apply_thresholds(
    era5_test,
    era5_thresholds,
    "era5"
)

print("Applying IFS-specific thresholds...")

ifs_classified = apply_thresholds(
    ifs_test,
    ifs_baseline,
    "ifs"
)


# ============================================================
# 11. MATCH CLASSIFICATIONS
# ============================================================

print("\n" + "=" * 65)
print("MATCHING ERA5 AND IFS CLASSIFICATIONS")
print("=" * 65)

# Select ERA5 anomaly flags from ERA5 dataframe.
era5_flag_columns = [
    "rainfall_era5_anomaly",
    "temperature_era5_anomaly",
    "humidity_era5_anomaly"
]

era5_output = era5_classified[
    ["district", "date"] + era5_flag_columns
].copy()

# Select IFS anomaly flags from IFS dataframe.
ifs_flag_columns = [
    "rainfall_ifs_anomaly",
    "temperature_ifs_anomaly",
    "humidity_ifs_anomaly"
]

ifs_output = ifs_classified[
    ["district", "date"] + ifs_flag_columns
].copy()

# Merge using district and date.
merged = era5_output.merge(
    ifs_output,
    on=["district", "date"],
    how="outer",
    validate="one_to_one",
    indicator=True
)

print("\nMatch status:")
print(merged["_merge"].value_counts())

# Confirm every observation has a match.
if not (merged["_merge"] == "both").all():
    raise ValueError(
        "ERA5 and IFS anomaly classifications do not fully match."
    )

merged = merged.drop(columns="_merge")

# Confirm expected records.
if len(merged) != EXPECTED_TEST_RECORDS:
    raise ValueError(
        f"Expected {EXPECTED_TEST_RECORDS} matched records, "
        f"found {len(merged)}."
    )

# Add calendar month for monthly evaluation.
merged["month"] = merged["date"].dt.month

print("\nMatched observations:", len(merged))
print("Districts:", merged["district"].nunique())

print("\nMatched anomaly columns:")
print(merged.columns.tolist())

# ============================================================
# 12. OVERALL VARIABLE-LEVEL EVALUATION
# ============================================================

print("\n" + "=" * 65)
print("VARIABLE-LEVEL EVALUATION")
print("=" * 65)

metric_rows = []

for variable in VARIABLES:

    suffix = ANOMALY_SUFFIXES[variable]

    result = calculate_metrics(
        merged[f"{suffix}_era5_anomaly"],
        merged[f"{suffix}_ifs_anomaly"]
    )

    result["variable"] = variable

    metric_rows.append(result)

metrics_df = pd.DataFrame(metric_rows)

metrics_df = metrics_df[
    [
        "variable",
        "records",
        "reference_anomalies",
        "comparison_anomalies",
        "true_positive",
        "true_negative",
        "false_positive",
        "false_negative",
        "overall_agreement",
        "precision",
        "recall",
        "f1_score"
    ]
]

print(metrics_df.to_string(index=False))

# ============================================================
# 13. DISTRICT-LEVEL EVALUATION
# ============================================================

print("\n" + "=" * 65)
print("DISTRICT-LEVEL EVALUATION")
print("=" * 65)

district_rows = []

for district, group in merged.groupby("district"):

    for variable in VARIABLES:

        suffix = ANOMALY_SUFFIXES[variable]

        result = calculate_metrics(
            group[f"{suffix}_era5_anomaly"],
            group[f"{suffix}_ifs_anomaly"]
        )

        result["district"] = district
        result["variable"] = variable

        district_rows.append(result)

district_df = pd.DataFrame(district_rows)

print(
    district_df.head(15).to_string(index=False)
)

# ============================================================
# 14. MONTHLY EVALUATION
# ============================================================

print("\n" + "=" * 65)
print("MONTHLY ANOMALY EVALUATION")
print("=" * 65)

monthly_rows = []

for month, group in merged.groupby("month"):

    for variable in VARIABLES:

        suffix = ANOMALY_SUFFIXES[variable]

        result = calculate_metrics(
            group[f"{suffix}_era5_anomaly"],
            group[f"{suffix}_ifs_anomaly"]
        )

        result["month"] = int(month)
        result["variable"] = variable

        monthly_rows.append(result)

monthly_df = pd.DataFrame(monthly_rows)

print(
    monthly_df.to_string(index=False)
)

# ============================================================
# 15. SAVE RESULTS
# ============================================================

print("\n" + "=" * 65)
print("SAVING EVALUATION RESULTS")
print("=" * 65)

merged.to_csv(
    MATCHED_OUTPUT,
    index=False
)

metrics_df.to_csv(
    METRICS_OUTPUT,
    index=False
)

district_df.to_csv(
    DISTRICT_OUTPUT,
    index=False
)

monthly_df.to_csv(
    MONTHLY_OUTPUT,
    index=False
)

print("\nSaved files:")

print("1.", MATCHED_OUTPUT)
print("2.", METRICS_OUTPUT)
print("3.", DISTRICT_OUTPUT)
print("4.", MONTHLY_OUTPUT)

print("\n" + "=" * 65)
print("IFS ANOMALY EVALUATION COMPLETED")
print("=" * 65)

print("ERA5 baseline: 2007-2023")
print("IFS baseline: 2017-2023")
print("Test period: 2024-2025")
print("Matched observations:", len(merged))
print("Districts:", merged["district"].nunique())
