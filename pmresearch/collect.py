"""Read-only API collection with cached provenance; no credentials or trading.

Discovery produces candidates, not an automatically trusted research universe.
An audited manifest is necessary because close time, event time, and settlement
availability are different concepts. Public snapshots can contain revised dates.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import pandas as pd
from .data import validate

KALSHI='https://api.elections.kalshi.com/trade-api/v2'
GAMMA='https://gamma-api.polymarket.com'
CLOB='https://clob.polymarket.com'
MANIFEST=['venue','market_id','event_id','category','series_ticker','yes_token_id',
          'event_time','outcome_available_at','outcome','archived','approved','audit_notes']

class Client:
    def __init__(self, cache='data/raw', delay=.15):
        self.cache=Path(cache); self.cache.mkdir(parents=True,exist_ok=True);self.delay=delay
    def get(self, url, **params):
        params={k:v for k,v in params.items() if v is not None}
        full=url+('?' + urlencode(params) if params else '')
        path=self.cache/(hashlib.sha256(full.encode()).hexdigest()+'.json')
        if path.exists(): return json.loads(path.read_text())['body']
        for attempt in range(4):
            try:
                time.sleep(self.delay)
                with urlopen(Request(full,headers={'User-Agent':'PredictionMarketResearch/1.0'}),timeout=25) as r:
                    body=json.load(r)
                path.write_text(json.dumps({'url':full,'fetched_at':pd.Timestamp.now(tz='UTC').isoformat(),'body':body},indent=2))
                return body
            except HTTPError as exc:
                if exc.code not in [429,500,502,503,504] or attempt==3: raise
                wait=min(float(exc.headers.get('Retry-After',2**attempt)),30)
                time.sleep(wait)
            except (URLError,TimeoutError):
                if attempt==3: raise
                time.sleep(2**attempt)


def array(value):
    return json.loads(value) if isinstance(value,str) else (value or [])


def discover(venue, client, pages=1, series=None, archived=False):
    """Bounded pagination. archived and live Kalshi catalogs must be fetched separately."""
    rows=[];cursor=None
    for page in range(pages):
        if venue=='kalshi':
            if archived and series:
                raise ValueError('Historical discovery does not accept series filtering here; omit --series')
            path='/historical/markets' if archived else '/markets'
            payload=client.get(KALSHI+path,limit=100,cursor=cursor,
                status=None if archived else 'settled',series_ticker=series)
            markets=payload.get('markets',[]); next_cursor=payload.get('cursor')
        else:
            markets=client.get(GAMMA+'/markets',closed='true',limit=100,offset=100*page)
            if not isinstance(markets,list): raise ValueError('Unexpected Gamma response schema')
            next_cursor=None
        for m in markets:
            r={k:'' for k in MANIFEST};r.update(venue=venue,approved=False,archived=archived)
            if venue=='kalshi':
                r.update(market_id=m['ticker'],event_id=m.get('event_ticker',''),
                    series_ticker=series or '',category=m.get('category','unclassified'),
                    event_time=m.get('close_time',''),
                    outcome_available_at=m.get('settlement_ts',''),
                    outcome={'yes':1,'no':0}.get(m.get('result'),''))
            else:
                outcomes=array(m.get('outcomes')); tokens=array(m.get('clobTokenIds'))
                if len(outcomes)!=2 or set(str(o).lower() for o in outcomes)!={'yes','no'}: continue
                yes_index=[str(o).lower() for o in outcomes].index('yes')
                if len(tokens)!=2: continue
                events=m.get('events') or []
                r.update(market_id=str(m['id']),event_id=str(events[0]['id']) if events else '',
                    yes_token_id=str(tokens[yes_index]),category=m.get('category','unclassified'),
                    event_time=m.get('endDate',''))
                # Do not infer final outcomes or availability from outcomePrices/updatedAt.
            r['audit_notes']='UNREVIEWED: verify outcome, event clock, settlement availability, category, global event ID'
            rows.append(r)
        if not markets: break
        if venue=='kalshi':
            if not next_cursor or next_cursor==cursor: break
            cursor=next_cursor
        elif len(markets)<100: break
    return pd.DataFrame(rows,columns=MANIFEST)


def candle_price(c, field):
    obj=c.get(field) or {}
    if obj.get('close_dollars') is not None: return float(obj['close_dollars'])
    if obj.get('close') is not None: return float(obj['close'])/100
    return None


def latest_quote(points, entry, max_age_hours):
    eligible=[p for p in points if p['quote_time']<=entry
              and entry-p['quote_time']<=pd.Timedelta(hours=max_age_hours)
              and 0<p['price']<1]
    if not eligible: raise ValueError('No valid pre-entry quote within staleness tolerance')
    return max(eligible,key=lambda p:p['quote_time'])


def fetch_quotes(manifest, client, horizon_hours=48,max_age_hours=2):
    if horizon_hours<=0 or max_age_hours<=0: raise ValueError('Positive horizon and staleness required')
    missing=set(MANIFEST)-set(manifest)
    if missing: raise ValueError(f'Missing manifest columns: {sorted(missing)}')
    rows=[]; failures=[]
    for r in manifest.to_dict('records'):
        try:
            if str(r['approved']).lower() not in ['true','1']: raise ValueError('Manifest row has not been audited/approved')
            for field in ['event_id','audit_notes','outcome_available_at','event_time']:
                if pd.isna(r[field]) or not str(r[field]).strip(): raise ValueError('Missing audited '+field)
            event=pd.to_datetime(r['event_time'],utc=True); entry=event-pd.Timedelta(hours=horizon_hours)
            start=int((entry-pd.Timedelta(hours=max_age_hours)).timestamp());end=int(entry.timestamp())
            points=[]
            if r['venue']=='kalshi':
                ticker=quote(str(r['market_id']),safe='')
                archived=str(r['archived']).lower() in ['true','1']
                if archived: path=f'/historical/markets/{ticker}/candlesticks'
                else:
                    if pd.isna(r['series_ticker']) or not str(r['series_ticker']).strip():
                        raise ValueError('series_ticker required for live-tier Kalshi history')
                    path=f'/series/{quote(str(r["series_ticker"]),safe="")}/markets/{ticker}/candlesticks'
                raw=client.get(KALSHI+path,start_ts=start,end_ts=end,period_interval=1)
                for c in raw.get('candlesticks',[]):
                    bid=candle_price(c,'yes_bid');ask=candle_price(c,'yes_ask')
                    if bid is None or ask is None or not 0<=bid<=ask<=1: continue
                    points.append(dict(price=(bid+ask)/2,yes_bid=bid,yes_ask=ask,
                        quote_time=pd.to_datetime(c['end_period_ts'],unit='s',utc=True),price_kind='quote_mid'))
            elif r['venue']=='polymarket':
                if pd.isna(r['yes_token_id']): raise ValueError('Missing YES token ID')
                raw=client.get(CLOB+'/prices-history',market=str(r['yes_token_id']),startTs=start,endTs=end,fidelity=1)
                for p in raw.get('history',[]):
                    points.append(dict(price=float(p['p']),quote_time=pd.to_datetime(p['t'],unit='s',utc=True),
                        yes_bid=float('nan'),yes_ask=float('nan'),price_kind='historical_price_proxy'))
            else: raise ValueError('Unknown venue')
            row={**r,**latest_quote(points,entry,max_age_hours),'entry_time':entry,'event_time':event,'data_kind':'REAL'}
            # Validate each row so malformed data is captured in the failure report.
            rows.append(validate(pd.DataFrame([row]),max_age_hours).iloc[0].to_dict())
        except (ValueError,KeyError,TypeError,HTTPError,URLError,TimeoutError) as exc:
            failures.append(dict(venue=r.get('venue'),market_id=r.get('market_id'),error=str(exc)))
    good=validate(pd.DataFrame(rows),max_age_hours) if rows else pd.DataFrame(columns=MANIFEST+['price','quote_time','entry_time','data_kind'])
    return good,pd.DataFrame(failures,columns=['venue','market_id','error'])


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    d=s.add_parser('discover');d.add_argument('--venue',choices=['kalshi','polymarket'],required=True)
    d.add_argument('--pages',type=int,default=1);d.add_argument('--series');d.add_argument('--archived',action='store_true')
    d.add_argument('--out',default='data/candidates.csv')
    f=s.add_parser('fetch');f.add_argument('--manifest',required=True);f.add_argument('--out',default='data/real.csv')
    f.add_argument('--horizon-hours',type=float,default=48);f.add_argument('--max-age-hours',type=float,default=2)
    a=p.parse_args();client=Client();Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    if a.command=='discover':
        if a.pages<1: p.error('--pages must be positive')
        result=discover(a.venue,client,a.pages,a.series,a.archived);result.to_csv(a.out,index=False)
        print(f'{len(result)} UNREVIEWED candidates saved to {a.out}. Audit before fetching.')
    else:
        manifest=pd.read_csv(a.manifest,dtype={'market_id':str,'event_id':str,'yes_token_id':str,'series_ticker':str})
        result,errors=fetch_quotes(manifest,client,a.horizon_hours,a.max_age_hours)
        result.to_csv(a.out,index=False);errors.to_csv(a.out+'.failures.csv',index=False)
        print(f'{len(result)} accepted, {len(errors)} rejected. Failures: {a.out}.failures.csv')
        if result.empty: raise SystemExit('No accepted observations; nothing is ready for analysis.')

if __name__=='__main__': main()
