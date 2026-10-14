"""Reconcile accepted rows to saved source candles and the earlier pilot."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from pmresearch.data import validate
from collect_multicity import dollar_close

ROOT=Path(__file__).resolve().parent

def audit():
    d=validate(pd.read_csv(ROOT/'real.csv'))
    checked=0
    for source,g in d.groupby('quote_source_file'):
        raw=json.loads((ROOT/'raw'/source).read_text())
        if 'markets' in raw['body']:
            markets={m['market_ticker']:m['candlesticks'] for m in raw['body']['markets']}
        else:
            assert g.market_id.nunique()==1
            markets={g.market_id.iloc[0]:raw['body']['candlesticks']}
        for row in g.itertuples():
            timestamp=int(row.quote_time.timestamp())
            candles=[c for c in markets[row.market_id] if c['end_period_ts']==timestamp]
            assert any(np.isclose(dollar_close(c['yes_bid']),row.yes_bid,rtol=0,atol=1e-12)
                       and np.isclose(dollar_close(c['yes_ask']),row.yes_ask,rtol=0,atol=1e-12)
                       for c in candles), row.market_id
            assert np.isclose(row.price,(row.yes_bid+row.yes_ask)/2,rtol=0,atol=1e-12)
            checked+=1
    old=pd.read_csv(ROOT/'reference'/'chicago_previous_401.csv')
    overlap=old.merge(d,on='market_id',suffixes=('_old','_new'))
    assert len(overlap)==len(old), 'Prior accepted Chicago contract disappeared from the expansion'
    assert overlap.outcome_old.eq(overlap.outcome_new).all()
    assert np.allclose(overlap.price_old,overlap.price_new,rtol=0,atol=1e-12)
    for field in ['entry_time','quote_time']:
        assert pd.to_datetime(overlap[field+'_old'],utc=True).eq(pd.to_datetime(overlap[field+'_new'],utc=True)).all()
    result=dict(accepted_rows_reconciled_to_raw_candles=checked,
                previous_chicago_rows_reconciled=len(overlap),
                unchanged_prior_prices_outcomes_and_timestamps=True,
                duplicate_accepted_contracts=int(d.market_id.duplicated().sum()),
                scope='Source, unit, timestamp and prior-sample reconciliation; not historical-schedule or execution verification')
    (ROOT/'validation_summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':audit()
