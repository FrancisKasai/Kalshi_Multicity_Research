"""Calibration diagnostics and event-cluster-aware uncertainty."""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import logit
from sklearn.linear_model import LogisticRegression


def holm(pvalues):
    p=np.asarray(pvalues, dtype=float)
    out=np.full(len(p),np.nan)
    valid=np.flatnonzero(np.isfinite(p))
    order=valid[np.argsort(p[valid])]
    if len(order):
        out[order]=np.minimum(1,np.maximum.accumulate(p[order]*(len(order)-np.arange(len(order)))))
    return out


def clustered_mean_test(values, clusters):
    """Intercept-only cluster-robust SE; t reference with G-1 degrees of freedom."""
    x=np.asarray(values,float); n=len(x); mean=float(x.mean())
    sums=pd.DataFrame({'resid':x-mean,'cluster':np.asarray(clusters)}).groupby('cluster').resid.sum()
    g=len(sums)
    if g<2:
        return mean,np.nan,np.nan,np.nan,np.nan,g
    se=float(np.sqrt(g/(g-1)*np.square(sums).sum()/n**2))
    critical=stats.t.ppf(.975,g-1)
    p=float(2*stats.t.sf(abs(mean/se),g-1)) if se>0 else np.nan
    return mean,se,mean-critical*se,mean+critical*se,p,g


def calibration_table(d, group_cols=(), min_clusters=30):
    x=d.copy(); x['bin']=np.minimum((x.price*10).astype(int),9)
    rows=[]
    keys=[*group_cols,'bin']
    for key,g in x.groupby(keys,observed=True):
        key=key if isinstance(key,tuple) else (key,)
        # Across-city contracts on the same weather date share one cluster.
        cluster=g.weather_date if 'weather_date' in g else g.event_id
        bias,se,lo,hi,p,nclusters=clustered_mean_test(g.price-g.outcome,cluster)
        rows.append(dict(zip(keys,key),n=len(g),n_events=nclusters,mean_price=g.price.mean(),
            observed_rate=g.outcome.mean(),bias=bias,se=se,ci_low=lo,ci_high=hi,
            p_value=p if nclusters>=min_clusters else np.nan,
            sufficient_clusters=nclusters>=min_clusters))
    out=pd.DataFrame(rows)
    out['p_holm']=holm(out.p_value)
    return out


def brier_summary(d, group_cols=()):
    groups=d.groupby(list(group_cols),observed=True) if group_cols else [((),d)]
    rows=[]
    for key,g in groups:
        key=key if isinstance(key,tuple) else (key,)
        row=dict(zip(group_cols,key),n=len(g),n_events=g.event_id.nunique(),
            mean_price=g.price.mean(),observed_rate=g.outcome.mean(),
            market_brier=np.square(g.price-g.outcome).mean(),
            constant_half_brier=.25)
        if 'p_model' in g:
            row['model_brier']=np.square(g.p_model-g.outcome).mean()
        if 'p_base' in g:
            row['historical_base_brier']=np.square(g.p_base-g.outcome).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def walk_forward(d, min_train=150, block_days=30):
    """Venue-specific sigmoid calibration on logit(price); refit every block.

    Training requires outcome availability strictly before block start, and
    excludes event IDs appearing in the prediction block (including other venues).
    No outcome from the prediction block is used to fit its model.
    """
    x=d.copy(); origin=x.entry_time.min()
    x['block']=((x.entry_time-origin).dt.total_seconds()//(86400*block_days)).astype(int)
    out=[]
    for block,whole_test in x.groupby('block',sort=True):
        cutoff=whole_test.entry_time.min()
        past=x[(x.outcome_available_at<cutoff)&(~x.event_id.isin(whole_test.event_id))]
        for venue,test in whole_test.groupby('venue'):
            train=past[past.venue==venue]
            if len(train)<min_train or train.outcome.nunique()<2:
                continue
            model=LogisticRegression(C=1.0,solver='lbfgs',max_iter=1000)
            feature=lambda a: logit(np.clip(np.asarray(a),1e-6,1-1e-6)).reshape(-1,1)
            model.fit(feature(train.price),train.outcome)
            t=test.copy(); t['p_model']=model.predict_proba(feature(t.price))[:,1]
            t['p_base']=train.outcome.mean(); t['n_train']=len(train)
            t['fit_cutoff']=cutoff; t['latest_training_outcome']=train.outcome_available_at.max()
            t['calibration_intercept']=model.intercept_[0]; t['calibration_slope']=model.coef_[0,0]
            out.append(t)
    if not out:
        raise ValueError('Insufficient earlier resolved data; collect more or reduce min_train explicitly')
    return pd.concat(out).sort_values(['entry_time','venue','market_id']).reset_index(drop=True)


def forecast_comparison(pred):
    delta=np.square(pred.p_model-pred.outcome)-np.square(pred.price-pred.outcome)
    cluster=pred.weather_date if 'weather_date' in pred else pred.event_id
    mean,se,lo,hi,p,g=clustered_mean_test(delta,cluster)
    return pd.DataFrame([dict(model_minus_market_brier=mean,se=se,ci_low=lo,ci_high=hi,p_value=p,n_events=g)])
