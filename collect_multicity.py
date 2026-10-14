"""Read-only, cached real-market collector. Run from any working directory.

Sources are current finalized metadata plus historical quote candles. The clock
is a retrospective recorded-close proxy, not a verified historical schedule.
"""
import asyncio, json, time, hashlib
from collections import deque, defaultdict
from pathlib import Path
from urllib.parse import urlencode
import aiohttp
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
CFG = json.loads((ROOT / 'study_config.json').read_text())
BASE = 'https://api.elections.kalshi.com/trade-api/v2'

def event_date(m):
    return pd.to_datetime(m['event_ticker'].split('-')[1], format='%y%b%d').strftime('%Y-%m-%d')

def dollar_close(field):
    """Live uses close_dollars; archive uses fixed-point dollar strings.

    Never infer units from magnitude: reject ambiguous integer legacy values.
    """
    value = field.get('close_dollars')
    if value is not None:
        return float(value)
    value = field.get('close')
    if isinstance(value, str) and '.' in value:
        return float(value)
    return None

async def main():
    semaphore = asyncio.Semaphore(32)
    rate_lock = asyncio.Lock()
    request_starts = deque()
    cooldown_until = 0.0
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=45),
                                    headers={'User-Agent': 'PredictionMarketResearch/2.0'}) as session:
        async def request(path, params, filename):
            nonlocal cooldown_until
            url = BASE + path + '?' + urlencode(params)
            cache = RAW / filename
            if cache.exists():
                saved = json.loads(cache.read_text())
                if saved.get('url') == url:
                    return saved['body']
            for attempt in range(5):
                try:
                    async with semaphore:
                        # At most 4 request starts/second; concurrency absorbs
                        # network latency, while retries respect rate limits.
                        async with rate_lock:
                            if cooldown_until > time.monotonic():
                                await asyncio.sleep(cooldown_until-time.monotonic())
                            while request_starts and time.monotonic()-request_starts[0] >= 1:
                                request_starts.popleft()
                            if len(request_starts) >= 4:
                                await asyncio.sleep(max(0,1-(time.monotonic()-request_starts[0])))
                                while request_starts and time.monotonic()-request_starts[0] >= 1:
                                    request_starts.popleft()
                            request_starts.append(time.monotonic())
                        async with session.get(url) as response:
                            if response.status == 429:
                                cooldown_until = max(cooldown_until,time.monotonic()+min(4*2**attempt,30))
                            if response.status in (429, 500, 502, 503, 504):
                                raise RuntimeError('Retryable HTTP ' + str(response.status))
                            response.raise_for_status()
                            body = await response.json()
                    payload = dict(url=url, fetched_at=pd.Timestamp.now(tz='UTC').isoformat(), body=body)
                    cache.write_text(json.dumps(payload, separators=(',', ':')))
                    return body
                except Exception:
                    if attempt == 4:
                        raise
                    await asyncio.sleep(min(2 ** (attempt + 1), 8))

        async def catalog(series, tier):
            result = []; cursor = None
            for page in range(30):
                params = dict(series_ticker=series, limit=1000)
                if tier == 'live':
                    params['status'] = 'settled'
                if cursor:
                    params['cursor'] = cursor
                body = await request('/historical/markets' if tier == 'historical' else '/markets',
                                     params, f'{series}_{tier}_{page}.json')
                markets = body.get('markets', [])
                dates = []
                for market in markets:
                    day = event_date(market); dates.append(day)
                    if CFG['weather_date_start'] <= day <= CFG['weather_date_end']:
                        result.append((market, series, tier, day))
                cursor = body.get('cursor')
                if not cursor or (dates and max(dates) < CFG['weather_date_start']):
                    print('Catalog', series, tier, len(result), 'eligible dates', flush=True)
                    return result
            raise RuntimeError('Pagination safety limit reached: catalog incomplete')

        catalogs = await asyncio.gather(*(catalog(s, t) for s in CFG['cities'] for t in ['live', 'historical']))
        candidates = {}
        for records in catalogs:
            for record in records:
                ticker = record[0]['ticker']
                if ticker in candidates and candidates[ticker][0]['result'] != record[0]['result']:
                    raise ValueError('Conflicting duplicate outcome: ' + ticker)
                candidates[ticker] = record
        candidates = list(candidates.values())
        (ROOT / 'candidates.json').write_text(json.dumps(candidates, separators=(',', ':')))
        print('Metadata ready:', len(candidates), 'candidate contracts', flush=True)

        # The documented batch endpoint serves live-catalog markets only.
        # Preserve its complete raw response and map each returned ticker;
        # never present a derived component as an individual HTTP response.
        batch_quotes = {}
        live_groups = defaultdict(list)
        for m, series, tier, day in candidates:
            if tier != 'live':
                continue
            entry = pd.Timestamp(m['close_time'])-pd.Timedelta(hours=CFG['entry_hours_before_recorded_close'])
            params = dict(start_ts=int((entry-pd.Timedelta(hours=CFG['max_quote_age_hours'])).timestamp()),
                          end_ts=int(entry.timestamp()),period_interval=1)
            expected = BASE+'/series/'+series+'/markets/'+m['ticker']+'/candlesticks?'+urlencode(params)
            cached = RAW/(m['ticker']+'.json')
            if cached.exists() and json.loads(cached.read_text()).get('url') == expected:
                continue
            live_groups[int(entry.timestamp())].append(m['ticker'])

        async def prefetch(entry_ts, tickers):
            tickers = sorted(tickers)
            params = dict(start_ts=entry_ts-CFG['max_quote_age_hours']*3600,end_ts=entry_ts,
                          period_interval=1,market_tickers=','.join(tickers))
            digest = hashlib.sha256(params['market_tickers'].encode()).hexdigest()[:12]
            filename=f'batch_{entry_ts}_{digest}.json'
            try:
                response=await request('/markets/candlesticks',params,filename)
                for market in response.get('markets',[]):
                    ticker=market['market_ticker']
                    if ticker in tickers:
                        batch_quotes[ticker]=(market,filename)
            except Exception as exc:
                print('Batch unavailable; falling back to individual read:',filename,str(exc),flush=True)

        await asyncio.gather(*(prefetch(t,tickers[i:i+60]) for t,tickers in live_groups.items()
                               for i in range(0,len(tickers),60)))
        print('Live quotes supplied by saved batch responses:',len(batch_quotes),flush=True)

        async def process(record):
            m, series, tier, day = record
            try:
                if m.get('status') != 'finalized' or m.get('result') not in ('yes', 'no'):
                    raise ValueError('Not finalized binary')
                outcome = int(m['result'] == 'yes')
                if float(m['settlement_value_dollars']) != outcome:
                    raise ValueError('Nonbinary payout')
                close, opened, settled = (pd.Timestamp(m[k]) for k in ['close_time','open_time','settlement_ts'])
                entry = close - pd.Timedelta(hours=CFG['entry_hours_before_recorded_close'])
                if not opened <= entry < close <= settled:
                    raise ValueError('Invalid opening/entry/close/settlement order')
                params = dict(start_ts=int((entry-pd.Timedelta(hours=CFG['max_quote_age_hours'])).timestamp()),
                              end_ts=int(entry.timestamp()), period_interval=1)
                path = ('/historical/markets/' + m['ticker'] if tier == 'historical'
                        else '/series/' + series + '/markets/' + m['ticker']) + '/candlesticks'
                if m['ticker'] in batch_quotes:
                    response, source_file = batch_quotes[m['ticker']]
                else:
                    source_file = m['ticker'] + '.json'
                    response = await request(path, params, source_file)
                quotes = []
                open_ts, entry_ts = opened.timestamp(), entry.timestamp()
                max_age_seconds = CFG['max_quote_age_hours']*3600
                for candle in response.get('candlesticks', []):
                    bid = dollar_close(candle.get('yes_bid') or {})
                    ask = dollar_close(candle.get('yes_ask') or {})
                    if bid is None or ask is None:
                        continue
                    quote = candle['end_period_ts']
                    if (0 <= bid <= ask <= 1 and 0 < (bid+ask)/2 < 1 and open_ts <= quote <= entry_ts
                            and entry_ts-quote <= max_age_seconds):
                        quotes.append((quote, bid, ask))
                if not quotes:
                    raise ValueError('No valid recent bid/ask candle')
                quote, bid, ask = max(quotes)
                quote = pd.to_datetime(quote, unit='s', utc=True)
                rules = m.get('rules_primary', '')
                source = ('National Weather Service' if 'National Weather Service' in rules
                          else 'The Weather Company' if 'Weather Company' in rules else 'Other/unspecified')
                return dict(venue='kalshi',market_id=m['ticker'],event_id=m['event_ticker'],category='weather',
                            series=series,city=CFG['cities'][series],weather_date=day,archive_tier=tier,
                            quote_source_file=source_file,
                            settlement_source=source,price=(bid+ask)/2,outcome=outcome,
                            quote_time=quote,entry_time=entry,event_time=close,outcome_available_at=settled,
                            open_time=opened,yes_bid=bid,yes_ask=ask,full_spread=ask-bid,
                            price_kind='quote_mid',data_kind='REAL',horizon_hours=24,
                            clock_basis='24h before recorded close; historical schedule not verified'), None
            except Exception as exc:
                return None, dict(market_id=m['ticker'],city=CFG['cities'][series],weather_date=day,error=str(exc))

        rows, errors = [], []
        start = time.monotonic()
        for i, future in enumerate(asyncio.as_completed([process(r) for r in candidates]), 1):
            row, error = await future
            if row: rows.append(row)
            else: errors.append(error)
            if i % 250 == 0:
                print(f'Quotes {i}/{len(candidates)}; accepted {len(rows)}; exclusions {len(errors)}; elapsed {time.monotonic()-start:.0f}s', flush=True)
        if not rows:
            raise RuntimeError('No accepted records')
        d = pd.DataFrame(rows).sort_values(['entry_time','market_id'])
        d.to_csv(ROOT/'real.csv', index=False)
        pd.DataFrame(errors, columns=['market_id','city','weather_date','error']).to_csv(ROOT/'failures.csv',index=False)
        all_candidates = pd.DataFrame([dict(market_id=m['ticker'],event_id=m['event_ticker'],city=CFG['cities'][s],
                                               weather_date=day,archive_tier=tier) for m,s,tier,day in candidates])
        all_candidates['accepted'] = all_candidates.market_id.isin(d.market_id)
        all_candidates.to_csv(ROOT/'candidate_coverage.csv', index=False)
        summary = dict(candidates=len(candidates),contracts=len(d),events=d.event_id.nunique(),
                       weather_dates=d.weather_date.nunique(),cities=d.city.nunique(),exclusions=len(errors),
                       entry_start=str(d.entry_time.min()),entry_end=str(d.entry_time.max()),
                       max_quote_age_minutes=float((d.entry_time-d.quote_time).dt.total_seconds().max()/60),
                       settlements=d.settlement_source.value_counts().to_dict())
        (ROOT/'collection_summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary), flush=True)

if __name__ == '__main__':
    asyncio.run(main())
