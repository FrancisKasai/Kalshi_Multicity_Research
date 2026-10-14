# Kalshi: expanded six-city research package

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

## Risk-control comparison

Open **RISK_CONTROLS.md** or the final notebook section for the exploratory sizing comparison. Run `python risk_controls.py` to reproduce it from the saved predictions. The original primary policy is preserved. `outputs/risk_controls/` contains the comparison, chart, policy specification and all three trade/equity histories.
