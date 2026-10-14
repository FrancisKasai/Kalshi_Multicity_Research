"""Fixed original forecasting/backtest method; expanded coverage and inference."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pmresearch.data import validate
from pmresearch.analysis import clustered_mean_test, brier_summary, calibration_table
from pmresearch.report import run

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs' / 'real'

def moving_block_interval(pred, block_days=7, repetitions=2000, seed=20261009):
    """Resample overlapping contiguous day blocks, keeping all cities together.

    CI targets contract-weighted mean paired Brier difference, with a percentile
    bootstrap. The length and seed are fixed before examining the results.
    Nonstationarity and sample selection are not removed by this procedure.
    """
    p = pred.copy()
    p['delta'] = (p.p_model-p.outcome)**2 - (p.price-p.outcome)**2
    daily = p.groupby('weather_date').agg(total=('delta','sum'),n=('delta','size'))
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(pd.date_range(daily.index.min(),daily.index.max(),freq='D'), fill_value=0)
    n = len(daily)
    if n < block_days:
        raise ValueError('Not enough calendar days for block bootstrap')
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n-block_days+1, size=(repetitions, int(np.ceil(n/block_days))))
    indexes = (starts[:,:,None]+np.arange(block_days)).reshape(repetitions,-1)[:,:n]
    draws = daily.total.to_numpy()[indexes].sum(axis=1) / daily.n.to_numpy()[indexes].sum(axis=1)
    return dict(method=f'{block_days}-day moving-block bootstrap',block_days=block_days,
                model_minus_market_brier=float(p.delta.mean()),
                ci_low=float(np.quantile(draws,.025)),ci_high=float(np.quantile(draws,.975)),
                repetitions=repetitions,seed=seed,n_calendar_days=n)

def comparison(pred, cluster):
    delta = (pred.p_model-pred.outcome)**2 - (pred.price-pred.outcome)**2
    mean,se,lo,hi,p,n = clustered_mean_test(delta,cluster)
    return dict(n_contracts=len(pred),n_weather_dates=pred.weather_date.nunique(),
                n_city_dates=pred.event_id.nunique(),model_minus_market_brier=mean,
                se=se,ci_low=lo,ci_high=hi,p_value=p,n_clusters=n)

def analyze():
    cfg=json.loads((ROOT/'study_config.json').read_text())
    fixed=dict(min_train=150,refit_days=30,logistic_C=1.0,kelly_fraction=.25,
               assumed_full_spread=.02,assumed_fee_per_contract=.005,initial_bankroll=10000)
    if any(cfg[k]!=v for k,v in fixed.items()):
        raise ValueError('Study configuration differs from frozen analysis defaults; revise the implementation explicitly.')
    d = validate(pd.read_csv(ROOT/'real.csv'))
    assert d.data_kind.eq('REAL').all()
    assert ((d.event_time-d.entry_time).dt.total_seconds()==86400).all()
    assert (pd.to_datetime(d.open_time,utc=True,format='ISO8601')<=d.quote_time).all()
    tables,pred,trades,equity,summary = run(d,OUT)
    assert (pred.latest_training_outcome<pred.fit_cutoff).all()
    assert (pred.fit_cutoff<=pred.entry_time).all()
    assert (equity.cash>=-1e-8).all()
    assert np.isclose(summary['baseline']['ending_equity'],10000+trades.pnl.sum())
    candidates = pd.read_csv(ROOT/'candidate_coverage.csv')
    candidates['month'] = candidates.weather_date.str[:7]
    coverage = candidates.groupby(['city','month']).agg(candidates=('market_id','size'),
                                                       accepted=('accepted','sum')).reset_index()
    coverage['coverage_pct'] = 100*coverage.accepted/coverage.candidates
    coverage.to_csv(OUT/'coverage_by_city_month.csv',index=False)
    d.groupby('city').agg(contracts=('market_id','size'),weather_dates=('weather_date','nunique'),
                         first_date=('weather_date','min'),last_date=('weather_date','max'),
                         median_spread=('full_spread','median')).to_csv(OUT/'coverage_by_city.csv')
    quality=d.assign(quote_age_minutes=(d.entry_time-d.quote_time).dt.total_seconds()/60)
    quality.groupby('city').agg(median_full_spread=('full_spread','median'),
                                p95_full_spread=('full_spread',lambda x:x.quantile(.95)),
                                max_full_spread=('full_spread','max'),
                                median_quote_age_minutes=('quote_age_minutes','median'),
                                max_quote_age_minutes=('quote_age_minutes','max')).to_csv(OUT/'quote_quality_by_city.csv')
    event_check = d.groupby(['event_id','city','weather_date']).agg(contracts=('market_id','size'),
                                                               yes_outcomes=('outcome','sum')).reset_index()
    event_check.to_csv(OUT/'event_completeness.csv',index=False)
    pd.crosstab(d.weather_date.str[:7],d.settlement_source).to_csv(OUT/'settlement_source_by_month.csv')
    infer = [dict(method='Calendar-day clusters across cities',**comparison(pred,pred.weather_date))]
    day = pd.to_datetime(pred.weather_date)
    weeks = ((day-day.min()).dt.days//7)
    infer.append(dict(method='Nonoverlapping 7-day clusters across cities',**comparison(pred,weeks)))
    infer.extend(moving_block_interval(pred,b) for b in [7,14])
    pd.DataFrame(infer).to_csv(OUT/'dependence_checks.csv',index=False)
    bycity = []
    for city,g in pred.groupby('city'):
        bycity.append(dict(city=city,**comparison(g,g.weather_date)))
    citystats = pd.DataFrame(bycity)
    citystats.to_csv(OUT/'forecast_comparison_by_city.csv',index=False)
    brier_summary(pred,['city']).to_csv(OUT/'brier_by_city.csv',index=False)
    brier_summary(pred,['settlement_source']).to_csv(OUT/'brier_by_settlement_source.csv',index=False)
    # Descriptive stratifications, not a search for a winning city or month.
    p = pred.copy(); p['month'] = p.weather_date.str[:7]
    brier_summary(p,['month']).to_csv(OUT/'brier_by_month.csv',index=False)
    rows=[]
    for name,g in [('Chicago',pred[pred.city.eq('Chicago')]),
                   ('Five additional cities',pred[~pred.city.eq('Chicago')])]:
        rows.append(dict(cohort=name,**comparison(g,g.weather_date)))
    pd.DataFrame(rows).to_csv(OUT/'geographic_cohorts.csv',index=False)
    pred.groupby('block').agg(first_entry=('entry_time','min'),last_entry=('entry_time','max'),
                             test_contracts=('market_id','size'),training_contracts=('n_train','first'),
                             latest_training_label=('latest_training_outcome','first'),
                             intercept=('calibration_intercept','first'),slope=('calibration_slope','first')).to_csv(OUT/'training_windows.csv')
    # Primary graph: actual breadth and per-city paired predictive results.
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),gridspec_kw={'width_ratios':[1.2,1]})
    pivot=coverage.pivot(index='month',columns='city',values='accepted').fillna(0)
    pivot.index=[s[5:] for s in pivot.index]
    pivot.plot.bar(stacked=True,ax=axes[0],colormap='tab20',width=.8)
    axes[0].set(title='Accepted contracts by month and city',xlabel='2026 month (October through 7th)',ylabel='Contracts')
    axes[0].tick_params(axis='x',rotation=0)
    axes[0].legend(fontsize=8,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.25))
    cs=citystats.sort_values('city'); positions=np.arange(len(cs))
    axes[1].errorbar(cs.model_minus_market_brier,positions,
                    xerr=np.vstack([cs.model_minus_market_brier-cs.ci_low,cs.ci_high-cs.model_minus_market_brier]),
                    fmt='o',color='#275DAD',capsize=4)
    axes[1].set_yticks(positions,cs.city)
    axes[1].axvline(0,color='gray',ls='--')
    axes[1].set(title='Out-of-sample calibration model vs market',xlabel='Brier difference: negative favors model\n95% calendar-day clustered intervals; descriptive')
    for ax in axes:ax.grid(alpha=.15,axis='x' if ax==axes[1] else 'y')
    fig.suptitle('Six-city daily-high temperature study · retrospective research',fontsize=13,fontweight='bold')
    fig.tight_layout();fig.savefig(OUT/'sample_expansion.png',dpi=160);plt.close(fig)
    summary.update(weather_dates=d.weather_date.nunique(),cities=d.city.nunique(),
                   out_of_sample_weather_dates=pred.weather_date.nunique(),
                   out_of_sample_city_dates=pred.event_id.nunique(),
                   out_of_sample_start=str(pred.entry_time.min()),out_of_sample_end=str(pred.entry_time.max()),
                   primary_comparison=infer[0],block_bootstrap_7_days=infer[2],block_bootstrap_14_days=infer[3])
    summary['limitations'].extend([
        'Six cities are still one exchange and one daily-temperature product family; no general market-wide claim.',
        'January through October 7 does not cover a full year or multiple years.',
        'The earlier Chicago Aug-Oct sample was already inspected; the expansion is retrospective, not a pristine final holdout.',
        'Calendar-day clusters retain cross-city dependence; block sensitivity checks do not eliminate seasonality or nonstationarity.',
        'Recorded settlement-source changes are described, not causally separated from time or city effects.',
        'Individual binary calibration does not enforce coherent probabilities summing to one across exhaustive outcome buckets.'
    ])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2),flush=True)
    return d,tables,pred,trades,equity,summary

if __name__=='__main__':
    analyze()
