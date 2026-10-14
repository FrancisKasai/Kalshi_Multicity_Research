import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from .data import validate
from .analysis import calibration_table,brier_summary,walk_forward,forecast_comparison
from .backtest import simulate


def run(frame,outdir='outputs/demo'):
    d=validate(frame);out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    kinds=set(d.get('data_kind',pd.Series(['UNKNOWN'])).dropna().astype(str))
    if 'SYNTHETIC' in kinds and kinds!={'SYNTHETIC'}: raise ValueError('Do not mix real and synthetic observations')
    label='SYNTHETIC DEMO — NOT MARKET FINDINGS' if kinds=={'SYNTHETIC'} else 'RESEARCH SAMPLE — AUDIT REQUIRED'
    pred=walk_forward(d)
    tables={'brier_overall':brier_summary(d),'brier_by_venue':brier_summary(d,['venue']),
        'brier_by_category':brier_summary(d,['venue','category']),
        'calibration':calibration_table(d),'calibration_by_venue':calibration_table(d,['venue']),
        'calibration_by_category':calibration_table(d,['venue','category']),
        'out_of_sample_brier':brier_summary(pred,['venue']),
        'out_of_sample_calibration':calibration_table(pred,['venue']),
        'forecast_comparison':forecast_comparison(pred)}
    ledger,curve,base=simulate(pred)
    ledger.to_csv(out/'trades.csv',index=False);curve.to_csv(out/'equity.csv');pred.to_csv(out/'predictions.csv',index=False)
    sensitivity=[]
    for spread in [0,.02,.04]:
        for k in [.1,.25,.5,.75,1.]:
            _,_,s=simulate(pred,fraction=k,full_spread=spread)
            s['strategy']='kelly';sensitivity.append(s)
    _,flatcurve,flat=simulate(pred,flat_contracts=100)
    flat['strategy']='flat_100_contracts';sensitivity.append(flat)
    tables['sensitivity']=pd.DataFrame(sensitivity)
    for name,table in tables.items():table.to_csv(out/(name+'.csv'),index=False)
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140,'font.size':10})
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    colors={'kalshi':'#275DAD','polymarket':'#DF7837'}
    for venue,g in tables['calibration_by_venue'].groupby('venue'):
        axes[0].plot(g.mean_price,g.observed_rate,'o-',label=venue,color=colors[venue])
        axes[1].errorbar(g.mean_price,g.bias,yerr=1.96*g.se,fmt='o-',label=venue,color=colors[venue],capsize=3)
    axes[0].plot([0,1],[0,1],'--',color='gray');axes[1].axhline(0,ls='--',color='gray')
    axes[0].set(xlabel='Mean quoted probability',ylabel='Observed YES frequency',title='Calibration (full sample)')
    axes[1].set(xlabel='Mean quoted probability',ylabel='Price − outcome frequency',title='Bias ± 1.96 clustered SE')
    for ax in axes: ax.legend();ax.grid(alpha=.15)
    fig.suptitle(label,fontsize=12,fontweight='bold');fig.tight_layout();fig.savefig(out/'calibration.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5))
    ax.plot(curve.index,curve.equity,label='Quarter Kelly');ax.plot(flatcurve.index,flatcurve.equity,label='Flat 100 contracts',alpha=.8)
    ax.set(title=label+'\nSettlement-accounted equity (holdings valued at entry cost)',ylabel='Dollars');ax.legend();ax.grid(alpha=.15)
    locator=mdates.AutoDateLocator(minticks=4,maxticks=7)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.tight_layout();fig.savefig(out/'equity.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for spread,g in tables['sensitivity'].query("strategy == 'kelly'").groupby('full_spread'):
        axes[0].plot(g.kelly_fraction,g.settlement_daily_sharpe,'o-',label=f'Spread {spread:.2f}')
        axes[1].plot(g.kelly_fraction,-100*g.settlement_max_drawdown,'o-',label=f'Spread {spread:.2f}')
    axes[0].set(ylabel='Settlement-accounted daily Sharpe',xlabel='Kelly multiplier')
    axes[1].set(ylabel='Settlement-accounted max drawdown (%)',xlabel='Kelly multiplier')
    for ax in axes: ax.legend();ax.grid(alpha=.15)
    fig.suptitle(label+'\nSizing and spread scenarios — not a parameter-selection exercise',fontsize=11)
    fig.tight_layout();fig.savefig(out/'sensitivity.png');plt.close(fig)
    prices=np.linspace(.01,.99,99); probs=np.linspace(.01,.99,99)
    c,p=np.meshgrid(prices,probs); f=np.maximum(0,(p-c)/(1-c))
    fig,ax=plt.subplots(figsize=(7,5))
    mesh=ax.pcolormesh(c,p,f,cmap='Blues',shading='auto',vmin=0,vmax=1)
    fig.colorbar(mesh,ax=ax,label='Fraction of bankroll spent')
    ax.plot(prices,prices,'--',color='#DF7837',label='Zero edge')
    ax.set(xlabel='All-in YES contract cost',ylabel='Estimated YES probability',title='Full Kelly for a single binary contract')
    ax.legend();fig.tight_layout();fig.savefig(out/'kelly.png');plt.close(fig)
    summary={'data_label':label,'observations':len(d),'unique_events':d.event_id.nunique(),
        'out_of_sample_observations':len(pred),'baseline':base,
        'limitations':[('Synthetic demo is not evidence of bias or profitability.' if kinds=={'SYNTHETIC'} else 'Real observations use a retrospective cutoff proxy; schedule history and execution are not fully verified.'),
        'Settlement accounting is not mark-to-market; its Sharpe/drawdown are illustrative.',
        'Historical quote fills, depth, slippage, and exact venue fees are not established.',
        'Calibration/comparison clusters use weather dates across cities when present; serial dependence is checked separately.',
        'Cross-venue comparisons are descriptive unless event samples and price types are matched.']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'README.txt').write_text(label+'\nAll CSV/PNG files in this directory have this data provenance.\n'+ '\n'.join(summary['limitations']))
    return tables,pred,ledger,curve,summary
