"""Exploratory sizing comparison on unchanged saved walk-forward predictions."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pmresearch.data import validate
from pmresearch.backtest import simulate

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'/'risk_controls'
POLICIES=[('Original quarter Kelly',.25,None),
          ('One-tenth Kelly',.10,None),
          ('One-tenth Kelly + 4% weather-day cap',.10,.04)]

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    pred=validate(pd.read_csv(ROOT/'outputs'/'real'/'predictions.csv'))
    rows=[];curves={}
    for i,(name,fraction,cap) in enumerate(POLICIES):
        trades,curve,stats=simulate(pred,fraction=fraction,weather_day_cap=cap)
        assert (curve.cash>=-1e-8).all()
        assert np.isclose(stats['ending_equity'],10000+trades.pnl.sum())
        if cap is not None:
            assert (trades.weather_day_locked_after<=cap*trades.entry_bankroll+1e-8).all()
        exposure=curve.locked/curve.equity
        rows.append(dict(policy=name,weather_day_cap=cap,**stats,
                         total_capital_deployed=trades.spent.sum(),
                         peak_locked_dollars=curve.locked.max(),
                         peak_locked_pct=exposure.max(),
                         peak_weather_day_at_entry_pct=(trades.weather_day_locked_after/trades.entry_bankroll).max()))
        trades.to_csv(OUT/f'policy_{i}_trades.csv',index=False)
        curve.to_csv(OUT/f'policy_{i}_equity.csv')
        curves[name]=curve
    result=pd.DataFrame(rows)
    original=json.loads((ROOT/'outputs'/'real'/'summary.json').read_text())['baseline']
    for key in ['ending_equity','total_return','settlement_max_drawdown','trades']:
        assert np.isclose(result.iloc[0][key],original[key],rtol=0,atol=1e-8),key
    result.to_csv(OUT/'comparison.csv',index=False)
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for name,curve in curves.items():
        axes[0].plot(curve.index,curve.equity,label=name,lw=1.3)
        axes[1].plot(curve.index,100*(curve.equity/curve.equity.cummax()-1),lw=1.3)
    axes[0].set(ylabel='Settlement-accounted equity ($)',title='Exploratory risk controls · same predictions and assumed costs')
    axes[0].legend(fontsize=9)
    axes[1].set(ylabel='Drawdown (%)')
    for ax in axes:ax.grid(alpha=.2)
    locator=mdates.AutoDateLocator(minticks=4,maxticks=7)
    axes[1].xaxis.set_major_locator(locator);axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.tight_layout();fig.savefig(OUT/'risk_comparison.png',dpi=150);plt.close(fig)
    lines=['| Policy | Return | Max drawdown | Ending equity | Peak locked capital |',
           '|---|---:|---:|---:|---:|']
    for r in result.itertuples():
        lines.append(f'| {r.policy} | {r.total_return:.2%} | {r.settlement_max_drawdown:.2%} | ${r.ending_equity:,.2f} | {r.peak_locked_pct:.2%} |')
    report='''# Exploratory drawdown-control comparison

The proposed revision is one-tenth Kelly with a 4% shared weather-date cap.
The 4% value reuses the existing city-event limit; it was specified before
running this comparison, not chosen by searching for a target drawdown.
The original quarter-Kelly policy remains the primary historical result.

'''+ '\n'.join(lines)+'''

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
'''
    (ROOT/'RISK_CONTROLS.md').write_text(report)
    (OUT/'policy_specification.json').write_text(json.dumps(dict(
        proposed_fraction=.10,proposed_weather_day_cap=.04,
        position_cap=.02,event_cap=.04,gross_cap=.5,
        selection='Specified before this comparison; motivated by previously inspected drawdown',
        forecast_changes=False,exploratory=True),indent=2))
    print(result.to_string(index=False))
    return result

if __name__=='__main__':run()
