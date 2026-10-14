# Six-city Kalshi research: sample expansion

The original sample limitation is substantially reduced: **10,051 accepted real contracts across six cities and 280 weather dates**, compared with 401 contracts, one city and 67 dates in the earlier pilot.

This is still a daily-temperature study on one exchange. It does not establish a general result across prediction-market categories.

## Coverage

| Measure | Original Chicago pilot | Expanded study |
| --- | ---: | ---: |
| Accepted real contracts | 401 | 10,051 |
| Cities | 1 | 6 |
| Calendar weather dates | 67 | 280 |
| City-date events | 67 | 1,680 |
| Weather-date window | August 2–October 7, 2026 | January 1–October 7, 2026 |

| city | contracts | weather_dates | first_date | last_date |
| --- | --- | --- | --- | --- |
| Austin | 1668 | 280 | 2026-01-01 | 2026-10-07 |
| Chicago | 1679 | 280 | 2026-01-01 | 2026-10-07 |
| Denver | 1674 | 280 | 2026-01-01 | 2026-10-07 |
| Los Angeles | 1676 | 280 | 2026-01-01 | 2026-10-07 |
| Miami | 1674 | 280 | 2026-01-01 | 2026-10-07 |
| New York City | 1680 | 280 | 2026-01-01 | 2026-10-07 |

Of 10,080 catalog candidates, 29 were excluded. Candidate-to-accepted coverage is 99.71%. See `failures.csv`, `candidate_coverage.csv` and `outputs/real/coverage_by_city_month.csv`; exclusions are retained rather than replaced with terminal prices.

| Reason | Excluded contracts |
| --- | --- |
| No valid recent bid/ask candle | 27 |
| Not finalized binary | 2 |

The maximum accepted quote age is 120 minutes. The clock is unchanged: 24 hours before the recorded exchange close, not 24 hours before the weather day starts. Close times are retrospective metadata snapshots; historical schedule revisions remain unverified.

The median quoted full spread is 1.0 cents, the 95th percentile is 4.0 cents, and the maximum is 26.0 cents. The baseline's fixed two-cent spread is a scenario assumption, not the actual spread on every trade. See `outputs/real/quote_quality_by_city.csv` for quote-age and spread diagnostics.

## Fixed-method out-of-sample findings

The original logistic-calibration settings, 30-day refit schedule, minimum 150 earlier finalized contracts, quarter-Kelly sizing and assumed costs were retained. The pooled model now has a wider training history. No cities, dates or parameters were selected to improve returns.

- Test observations: **8,971 contracts**, 1,500 city-date events and **250 calendar weather dates**.
- Entry-time test window: 2026-01-31 04:59:00+00:00 through 2026-10-07 08:00:00+00:00.
- Market Brier score: **0.101376**.
- Calibration-model Brier score: **0.101227**.
- Earlier-history base-rate Brier score: **0.139174**.

Lower Brier scores are better. A negative model-minus-market difference favors the model; scores use the same contracts.

| method | model_minus_market_brier | ci_low | ci_high |
| --- | --- | --- | --- |
| Calendar-day clusters across cities | -0.000149 | -0.000641 | 0.000342 |
| Nonoverlapping 7-day clusters across cities | -0.000149 | -0.000719 | 0.000421 |
| 7-day moving-block bootstrap | -0.000149 | -0.000648 | 0.000378 |
| 14-day moving-block bootstrap | -0.000149 | -0.000636 | 0.000453 |

The week-block uncertainty checks do not establish a stable predictive improvement over market prices.

Calendar-day clusters group related contracts across cities. The bootstrap resamples contiguous blocks of days with all cities kept together, using fixed 7- and 14-day block lengths and 2,000 replications. It preserves nearby-day dependence approximately; it cannot remove seasonality, selection effects or nonstationarity.

Per-city, month and source results are descriptive robustness checks, not a search for a winning subgroup. The catalog identifies an NWS settlement-source period through August 13 and a Weather Company period starting August 14. Source and season effects are confounded.

## Illustrative trading simulation

The unchanged quarter-Kelly baseline makes **4,418 simulated trades**, taking $10,000 to **$13,004.59**, a **30.05%** settlement-accounted return. Settlement-accounted maximum drawdown is -50.01%.

These are simulated results with an assumed two-cent full spread and half-cent fee per contract. They are not actual exchange fees or reconstructed fills. Open positions remain valued at entry cost, so the equity curve does not capture interim mark-to-market risk. The 4% event cap applies to city-date events, not aggregate weather exposure across cities. Scenario results must not be cherry-picked as achievable performance.

## What is now stronger

The project now demonstrates a reusable real-data collection pipeline, broader geography, more seasons, explicit missing-data accounting, leakage checks, and inference that recognizes cross-city and nearby-date dependence. These are substantive improvements for a research portfolio or resume even if the model does not beat the market.

All 10,051 accepted observations were reconciled to their saved raw quote responses. The original 401 Chicago observations retain identical prices, outcomes and quote/entry timestamps. See `validation_summary.json`; this reconciliation does not establish historical schedule versions or executable fills.

Remaining limits: one exchange, one product family, less than a full year, unverified historical schedule versions and execution, and a previously inspected Chicago subset. Historical walk-forward predictions use only earlier labels, but the expanded research is not a pristine prospective holdout. Individual binary predictions also do not enforce outcome-bucket probabilities summing to one.

The next scope expansion would add earlier years and a genuinely different market family under its own defensible observation clock. Any model changes made after inspecting this report require a new untouched evaluation period.

## Exploratory risk-control follow-up

See **RISK_CONTROLS.md** for the subsequent one-tenth Kelly and shared weather-day cap comparison. The original results above remain the primary historical run. The follow-up uses already inspected data and is not independent validation.
