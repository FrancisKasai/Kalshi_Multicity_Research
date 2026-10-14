# Exploratory drawdown-control comparison

The proposed revision is one-tenth Kelly with a 4% shared weather-date cap.
The 4% value reuses the existing city-event limit; it was specified before
running this comparison, not chosen by searching for a target drawdown.
The original quarter-Kelly policy remains the primary historical result.

| Policy | Return | Max drawdown | Ending equity | Peak locked capital |
|---|---:|---:|---:|---:|
| Original quarter Kelly | 30.05% | -50.01% | $13,004.59 | 50.00% |
| One-tenth Kelly | 30.86% | -32.34% | $13,085.79 | 48.63% |
| One-tenth Kelly + 4% weather-day cap | 21.21% | -16.15% | $12,121.08 | 11.85% |

All three policies use the same 8,971 saved walk-forward predictions, the same
contract universe, a $10,000 initial bankroll, an assumed two-cent full spread
and half-cent fee. The 2% contract, 4% city-event and 50% gross limits remain.
The middle policy isolates the sizing change; the last also adds the shared cap.
The original return and drawdown reproduce the previous run within numerical tolerance.

The shared cap limits entry-cost capital still locked in all cities for a
given weather date. Positions remain counted until their recorded settlement,
when exposure is released. It is a pre-trade cap: a later decline in bankroll
does not force liquidation of existing positions. It is not a 4% drawdown
limit and does not cap weather dependence across adjacent dates.

Allocation follows the existing chronological entry order, with ticker order
breaking ties. A shared cap can therefore favor cities with earlier entry
times and change the trade mix; this is not a pure proportional reduction of
every position. `comparison.csv` includes capital deployed and peak exposure;
each policy has a complete trade ledger and equity series.

These are settlement-accounted simulations, not executable returns or
mark-to-market drawdowns. This change was motivated by a drawdown already seen
in this dataset. The comparison is therefore exploratory, not independent
validation. Lower risk does not establish a forecasting edge; the earlier
forecast-quality findings are unchanged. Freeze this revised policy and test
it on an untouched future sample before making prospective performance claims.
