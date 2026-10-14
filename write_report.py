"""Build a concise report from saved outputs; never invent result metrics."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'/'real'

def markdown_table(frame):
    columns=list(frame.columns)
    lines=['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']
    for values in frame.itertuples(index=False,name=None):
        lines.append('| '+' | '.join(str(v) for v in values)+' |')
    return '\n'.join(lines)

def build():
    s=json.loads((OUT/'summary.json').read_text())
    c=json.loads((ROOT/'collection_summary.json').read_text())
    b=pd.read_csv(OUT/'out_of_sample_brier.csv').iloc[0]
    inf=pd.read_csv(OUT/'dependence_checks.csv')
    city=pd.read_csv(OUT/'coverage_by_city.csv')
    errors=pd.read_csv(ROOT/'failures.csv')
    spreads=pd.read_csv(ROOT/'real.csv',usecols=['full_spread']).full_spread
    q=s['baseline']; delta=s['primary_comparison']['model_minus_market_brier']
    mb=s['block_bootstrap_7_days']; mb14=s['block_bootstrap_14_days']
    if mb['ci_high']<0 and mb14['ci_high']<0:
        interpretation='The fixed calibration model improves Brier score in this retrospective sample, and both block-bootstrap intervals exclude zero. This does not establish executable trading profitability or stability beyond this cohort.'
    elif mb['ci_low']>0 and mb14['ci_low']>0:
        interpretation='The fixed calibration model has worse Brier score than market prices, and both block-bootstrap intervals exclude zero. The larger sample is evidence against this particular recalibration improving forecasts in this cohort.'
    else:
        interpretation='The week-block uncertainty checks do not establish a stable predictive improvement over market prices.'
    table=inf[['method','model_minus_market_brier','ci_low','ci_high']].copy()
    for col in table.columns[1:]:table[col]=table[col].map(lambda x:f'{x:.6f}')
    text=f'''# Six-city Kalshi research: sample expansion

The original sample limitation is substantially reduced: **{c['contracts']:,} accepted real contracts across six cities and {c['weather_dates']} weather dates**, compared with 401 contracts, one city and 67 dates in the earlier pilot.

This is still a daily-temperature study on one exchange. It does not establish a general result across prediction-market categories.

## Coverage

| Measure | Original Chicago pilot | Expanded study |
| --- | ---: | ---: |
| Accepted real contracts | 401 | {c['contracts']:,} |
| Cities | 1 | {c['cities']} |
| Calendar weather dates | 67 | {c['weather_dates']} |
| City-date events | 67 | {c['events']:,} |
| Weather-date window | August 2–October 7, 2026 | January 1–October 7, 2026 |

{markdown_table(city[['city','contracts','weather_dates','first_date','last_date']])}

Of {c['candidates']:,} catalog candidates, {c['exclusions']:,} were excluded. Candidate-to-accepted coverage is {100*c['contracts']/c['candidates']:.2f}%. See `failures.csv`, `candidate_coverage.csv` and `outputs/real/coverage_by_city_month.csv`; exclusions are retained rather than replaced with terminal prices.

{markdown_table(errors.groupby('error').size().rename('Excluded contracts').reset_index().rename(columns={'error':'Reason'}))}

The maximum accepted quote age is {c['max_quote_age_minutes']:.0f} minutes. The clock is unchanged: 24 hours before the recorded exchange close, not 24 hours before the weather day starts. Close times are retrospective metadata snapshots; historical schedule revisions remain unverified.

The median quoted full spread is {100*spreads.median():.1f} cents, the 95th percentile is {100*spreads.quantile(.95):.1f} cents, and the maximum is {100*spreads.max():.1f} cents. The baseline's fixed two-cent spread is a scenario assumption, not the actual spread on every trade. See `outputs/real/quote_quality_by_city.csv` for quote-age and spread diagnostics.

## Fixed-method out-of-sample findings

The original logistic-calibration settings, 30-day refit schedule, minimum 150 earlier finalized contracts, quarter-Kelly sizing and assumed costs were retained. The pooled model now has a wider training history. No cities, dates or parameters were selected to improve returns.

- Test observations: **{s['out_of_sample_observations']:,} contracts**, {s['out_of_sample_city_dates']:,} city-date events and **{s['out_of_sample_weather_dates']} calendar weather dates**.
- Entry-time test window: {s['out_of_sample_start']} through {s['out_of_sample_end']}.
- Market Brier score: **{b.market_brier:.6f}**.
- Calibration-model Brier score: **{b.model_brier:.6f}**.
- Earlier-history base-rate Brier score: **{b.historical_base_brier:.6f}**.

Lower Brier scores are better. A negative model-minus-market difference favors the model; scores use the same contracts.

{markdown_table(table)}

{interpretation}

Calendar-day clusters group related contracts across cities. The bootstrap resamples contiguous blocks of days with all cities kept together, using fixed 7- and 14-day block lengths and 2,000 replications. It preserves nearby-day dependence approximately; it cannot remove seasonality, selection effects or nonstationarity.

Per-city, month and source results are descriptive robustness checks, not a search for a winning subgroup. The catalog identifies an NWS settlement-source period through August 13 and a Weather Company period starting August 14. Source and season effects are confounded.

## Illustrative trading simulation

The unchanged quarter-Kelly baseline makes **{q['trades']:,} simulated trades**, taking $10,000 to **${q['ending_equity']:,.2f}**, a **{q['total_return']:.2%}** settlement-accounted return. Settlement-accounted maximum drawdown is {q['settlement_max_drawdown']:.2%}.

These are simulated results with an assumed two-cent full spread and half-cent fee per contract. They are not actual exchange fees or reconstructed fills. Open positions remain valued at entry cost, so the equity curve does not capture interim mark-to-market risk. The 4% event cap applies to city-date events, not aggregate weather exposure across cities. Scenario results must not be cherry-picked as achievable performance.

## What is now stronger

The project now demonstrates a reusable real-data collection pipeline, broader geography, more seasons, explicit missing-data accounting, leakage checks, and inference that recognizes cross-city and nearby-date dependence. These are substantive improvements for a research portfolio or resume even if the model does not beat the market.

All {c['contracts']:,} accepted observations were reconciled to their saved raw quote responses. The original 401 Chicago observations retain identical prices, outcomes and quote/entry timestamps. See `validation_summary.json`; this reconciliation does not establish historical schedule versions or executable fills.

Remaining limits: one exchange, one product family, less than a full year, unverified historical schedule versions and execution, and a previously inspected Chicago subset. Historical walk-forward predictions use only earlier labels, but the expanded research is not a pristine prospective holdout. Individual binary predictions also do not enforce outcome-bucket probabilities summing to one.

The next scope expansion would add earlier years and a genuinely different market family under its own defensible observation clock. Any model changes made after inspecting this report require a new untouched evaluation period.
'''
    (ROOT/'RESULTS.md').write_text(text)
    (ROOT/'README.md').write_text('''# Kalshi: expanded six-city research package

Start with **RESULTS.md** for the findings. Open **Multicity_Kalshi_Analysis.ipynb** for the executed analysis, tables and figures. The included CSV files are the real collected research dataset; synthetic observations appear only in software test fixtures.

## Run the included analysis

1. Extract this ZIP into a normal folder.
2. Open a terminal in that extracted folder.
3. On a Mac, create and activate a project environment:

   `python3 -m venv .venv`

   `source .venv/bin/activate`

4. Install the Python dependencies:

   `python -m pip install -r requirements.txt`

5. Run the analysis:

   `python expanded_analysis.py`

   Or open the notebook:

   `python -m jupyterlab Multicity_Kalshi_Analysis.ipynb`

   In JupyterLab, choose **Run → Run All Cells**.

The included dataset is sufficient to reproduce the analysis offline after installing dependencies. The shipped notebook's code cells were executed sequentially as Python with captured tables and images; no Jupyter kernel was used to generate the saved output.

## Main files

- `RESULTS.md`: concise findings, sample comparison and limitations.
- `study_config.json`: fixed cohort, observation rule and analysis settings.
- `real.csv`: one accepted historical observation per contract.
- `candidate_coverage.csv` and `failures.csv`: inclusion and exclusion records.
- `collection_summary.json`: collection counts and date coverage.
- `collect_multicity.py`: cached, read-only live/archive API collection.
- `expanded_analysis.py`: unchanged forecasting/backtest method plus expanded inference.
- `pmresearch/`: validation, modeling and portfolio-accounting functions.
- `outputs/real/`: predictions, trades, coverage, scores, uncertainty checks and figures.
- `raw/`: complete collected quote and catalog response envelopes with URLs and retrieval times.
- `SOURCES.md`: official source documentation and exact data-construction limits.
- `tests/`: leakage, pricing-unit, dependence and accounting checks.

To rerun the software checks: `python -m unittest discover -s tests -v`.
To rebuild the text report after analysis: `python write_report.py`.
To refresh or resume collection: `python collect_multicity.py`. Cached responses are intentionally reused; remove only the relevant cached files if a new retrieval is explicitly needed. No API key is required for these public read endpoints. Changing model-related config values requires an explicit implementation change; the script rejects silent mismatches with frozen defaults.

## Interpretation

This is historical research, not a trading service. "Real" describes the source quotes and outcomes. Returns are still simulated. The sample now covers six cities and a longer period, but remains one exchange and one temperature-market family. Keep these distinctions in any presentation or resume claim.
''')
    if (ROOT/'RISK_CONTROLS.md').exists():
        with (ROOT/'RESULTS.md').open('a') as f:
            f.write('\n## Exploratory risk-control follow-up\n\nSee **RISK_CONTROLS.md** for the subsequent one-tenth Kelly and shared weather-day cap comparison. The original results above remain the primary historical run. The follow-up uses already inspected data and is not independent validation.\n')
        with (ROOT/'README.md').open('a') as f:
            f.write('\n## Risk-control comparison\n\nOpen **RISK_CONTROLS.md** or the final notebook section for the exploratory sizing comparison. Run `python risk_controls.py` to reproduce it from the saved predictions. The original primary policy is preserved. `outputs/risk_controls/` contains the comparison, chart, policy specification and all three trade/equity histories.\n')
    print('Wrote RESULTS.md and README.md')

if __name__=='__main__':build()
