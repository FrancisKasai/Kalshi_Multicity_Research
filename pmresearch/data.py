"""One pre-event observation per binary contract; explicit label availability."""
import numpy as np
import pandas as pd
from scipy.special import expit, logit

TIMES = ['quote_time', 'entry_time', 'event_time', 'outcome_available_at']
REQUIRED = ['venue','market_id','event_id','category','price','outcome',*TIMES]

def validate(frame, max_staleness_hours=2):
    d = frame.copy()
    missing = set(REQUIRED) - set(d)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    if d.empty:
        raise ValueError('No observations. Inspect collection failures; do not substitute terminal prices.')
    for c in TIMES:
        d[c] = pd.to_datetime(d[c], utc=True, errors='raise')
    for c in ['price', 'outcome']:
        d[c] = pd.to_numeric(d[c], errors='raise')
    if d[REQUIRED].isna().any().any():
        raise ValueError('Required fields contain missing values')
    if not d.venue.isin(['kalshi','polymarket']).all():
        raise ValueError('venue must be kalshi or polymarket')
    if not d.price.between(0,1,inclusive='neither').all():
        raise ValueError('Prices must be strictly between 0 and 1')
    if not d.outcome.isin([0,1]).all():
        raise ValueError('Only finalized binary outcomes 0/1 are supported')
    if d.duplicated(['venue','market_id']).any():
        raise ValueError('Use one observation per venue/contract; duplicate IDs found')
    if not ((d.quote_time <= d.entry_time) & (d.entry_time < d.event_time)
            & (d.event_time <= d.outcome_available_at)).all():
        raise ValueError('Invalid time order: quote <= entry < event <= outcome availability required')
    age = (d.entry_time-d.quote_time).dt.total_seconds()/3600
    if (age > max_staleness_hours).any():
        raise ValueError('Stale quotes exceed the configured tolerance')
    for c in ['venue','market_id','event_id','category']:
        d[c] = d[c].astype(str)
        if d[c].str.strip().eq('').any():
            raise ValueError(f'Blank {c}')
    if {'yes_bid','yes_ask'} <= set(d):
        partial = d.yes_bid.notna() ^ d.yes_ask.notna()
        q = d.dropna(subset=['yes_bid','yes_ask'])
        if partial.any() or not ((q.yes_bid>=0)&(q.yes_ask<=1)&(q.yes_bid<=q.yes_ask)).all():
            raise ValueError('Invalid bid/ask quotes')
    return d.sort_values(['entry_time','venue','market_id']).reset_index(drop=True)

def synthetic_data(n_events=1600, seed=42):
    """Deliberately biased, paired-venue SYNTHETIC data, never empirical evidence."""
    rng = np.random.default_rng(seed)
    rows=[]
    start = pd.Timestamp('2023-01-01', tz='UTC')
    for i in range(n_events):
        p_true=float(rng.beta(.7,.7))
        y=int(rng.random()<p_true)
        entry=start+pd.Timedelta(hours=6*i)
        event=entry+pd.Timedelta(hours=48)
        available=event+pd.Timedelta(hours=int(rng.integers(1,24)))
        category=['sports','politics','economics'][i%3]
        for venue,slope in [('kalshi',.78),('polymarket',.65)]:
            p=float(np.clip(expit(slope*logit(np.clip(p_true,.001,.999))+rng.normal(0,.06)),.005,.995))
            rows.append(dict(venue=venue,market_id=f'{venue}-{i}',event_id=f'event-{i}',
                category=category,price=p,outcome=y,quote_time=entry,entry_time=entry,
                event_time=event,outcome_available_at=available,yes_bid=max(0,p-.01),
                yes_ask=min(1,p+.01),price_kind='synthetic_mid',data_kind='SYNTHETIC'))
    return validate(pd.DataFrame(rows))
