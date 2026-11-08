# RiskWeave – Weather Forecasting Experiment Report

## 1. Project Overview

RiskWeave is a climate-informed dengue risk forecasting and inspection
planning system for Sri Lanka.

This experiment develops machine learning models to forecast daily
rainfall and daily mean temperature at district level.

The weather forecasting component investigates two forecast horizons:
- 1-day ahead
- 7-days ahead

## 2. Weather Data

### Data source
ERA5 historical/reanalysis weather data.

### Geographic coverage
25 districts in Sri Lanka.

### Temporal coverage
23 December 2006 to 19 December 2025.

### Dataset size
173,425 district-day records.

### Forecast targets
- Daily rainfall: precipitation_sum (mm)
- Daily mean temperature: temperature_2m_mean (°C)

## 3. Forecasting Methodology

The experiment uses historical weather observations to construct
forecasting features.

Feature engineering includes:
- Historical lag features.
- Rolling mean features.
- District information.
- Calendar and seasonal features.
- Target-date calendar features.

The forecasting horizons are 1 day and 7 days.

## 4. Data Splitting Strategy

Chronological splitting was used to avoid random mixing of past and
future observations.

- Training: target dates through 31 December 2023.
- Validation: 1 January 2024 to 31 December 2024.
- Testing: 1 January 2025 to 19 December 2025.

The validation period was used for model selection.
The test period was kept separate for final evaluation.

## 5. Models

Three machine learning algorithms were evaluated:

1. XGBoost
2. Histogram Gradient Boosting
3. Random Forest

A persistence baseline was also evaluated.

The persistence baseline uses the latest available observation at the
forecast origin.

## 6. Resource Considerations

The development environment has approximately 8 GB RAM.

To reduce memory usage:
- Numerical data was represented using float32 where appropriate.
- Lightweight model configurations were used.
- Training data was systematically sampled.
- Models were trained and evaluated separately.

The training sample contained approximately 51,575 records after
sampling, while validation and test datasets were evaluated using
their full available records.

## 7. Model Selection

Models were selected using validation MAE.

Selected models:

- Rainfall, 1-day: XGBoost
- Rainfall, 7-day: Histogram Gradient Boosting
- Temperature, 1-day: Random Forest
- Temperature, 7-day: Random Forest

## 8. Final Test Results

The independent test period was 1 January 2025 to 19 December 2025.

| Target | Horizon | Selected model | MAE | RMSE | R² |
|---|---:|---|---:|---:|---:|
| Rainfall | 1 day | XGBoost | 5.5991 mm | 12.5339 | 0.1296 |
| Rainfall | 7 days | Histogram Gradient Boosting | 6.0237 mm | 13.0329 | 0.0589 |
| Mean temperature | 1 day | Random Forest | 0.5598 °C | 0.7230 | 0.9522 |
| Mean temperature | 7 days | Random Forest | 0.6612 °C | 0.8380 | 0.9358 |

## 9. Persistence Baseline Comparison

All four selected models achieved lower test MAE than the persistence
baseline.

| Target | Horizon | Model MAE | Persistence MAE | MAE improvement |
|---|---:|---:|---:|---:|
| Rainfall | 1 day | 5.5991 | 6.6156 | 15.3653% |
| Rainfall | 7 days | 6.0237 | 8.0376 | 25.0556% |
| Mean temperature | 1 day | 0.5598 | 0.5985 | 6.4553% |
| Mean temperature | 7 days | 0.6612 | 0.8213 | 19.4922% |

The selected models also outperformed persistence in test RMSE and R².

## 10. Error Analysis

### Rainfall

Rainfall predictions showed limited ability to capture extreme rainfall.

The models tended to:
- Overpredict dry and light-rainfall observations.
- Underpredict moderate and heavy rainfall.
- Substantially underestimate very heavy rainfall events.

Rainfall test R² was modest, particularly for the 7-day horizon.

### Temperature

Temperature predictions showed strong agreement with observed values.

The 7-day horizon generally had higher errors than the 1-day horizon.
The warmest temperature category showed some underprediction.

### District-level performance

District-level error analysis was conducted for all 25 districts.

The results showed geographic variation in forecasting errors.
These differences should be interpreted descriptively rather than
attributed to specific geographic causes without further investigation.

## 11. SHAP Explainability

SHAP TreeExplainer was used to investigate feature importance.

The analysis used a sample of 200 test observations per model.

### Temperature

Recent temperature observations and rolling temperature averages
were among the most influential features.

The 1-day model relied more strongly on the previous day's
temperature, while the 7-day model showed greater reliance on
rolling averages.

### Rainfall

The 1-day rainfall model relied strongly on previous-day rainfall
and relative humidity.

The 7-day model showed greater influence from seasonal features,
longer-term rainfall averages and wind speed.

SHAP importance indicates model contribution, not causality.

## 12. Limitations

1. Rainfall forecasting performance is modest, especially for the
   7-day horizon.
2. Heavy and very heavy rainfall events are substantially
   underestimated.
3. Training used a systematic chronological sample because of
   hardware memory constraints.
4. The evaluation uses historical ERA5 reanalysis data.
5. ERA5 reanalysis is not itself an operational future weather
   forecast feed.
6. The models therefore demonstrate historical forecasting
   simulation performance, not verified live forecasting
   performance for future dates.

## 13. Reproducibility and Saved Outputs

The trained models are saved under:

models/weather_forecasting/

Evaluation outputs are saved under:

outputs/weather_forecasting/

SHAP outputs are saved under:

outputs/weather_forecasting/shap_analysis/

The artifact audit is saved as:

outputs/weather_forecasting/weather_forecasting_artifact_audit.csv

## 14. Conclusion

The experiment developed and evaluated district-level daily rainfall
and mean-temperature forecasting models for 1-day and 7-day horizons.

Temperature forecasting achieved strong test performance.
Rainfall forecasting improved over the persistence baseline, but
performance on extreme rainfall remains a significant limitation.

The saved models and evaluation artifacts provide a reproducible
foundation for the next stage of RiskWeave development.

Operational deployment requires an appropriate future weather
forecast input source and further evaluation using genuine forecast
inputs.
