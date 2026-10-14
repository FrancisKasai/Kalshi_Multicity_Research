# Source and observation construction

Data retrieved read-only from Kalshi's public API during this study. Raw response
envelopes retain the requested URL, retrieval timestamp and complete JSON body.
No account credentials or order endpoints are used.

## Official API documentation

- [Historical markets](https://docs.kalshi.com/api-reference/historical/get-historical-markets)
- [Historical candles](https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks)
- [Live-market candles](https://docs.kalshi.com/api-reference/market/get-market-candlesticks)
- [Batch live-market candles](https://docs.kalshi.com/api-reference/market/batch-get-market-candlesticks)
- [Series list](https://docs.kalshi.com/api-reference/market/get-series-list)

The collector uses the responding public base
`https://api.elections.kalshi.com/trade-api/v2`. The documentation may show another
official hostname. It queries both live and archived catalogs by series, follows
pagination, and deduplicates contract tickers across catalogs.
For live-catalog contracts, the documented batch endpoint reduces duplicate
network calls. Complete batch responses are retained, and `quote_source_file`
identifies the exact raw response supporting each accepted record. Archive
quotes use the individual historical endpoint. Valid responses already
collected for the earlier Chicago study are reused with their original
retrieval timestamps and URLs.

## Fixed sample definition

The six daily-high temperature series are KXHIGHCHI, KXHIGHNY, KXHIGHLAX,
KXHIGHMIA, KXHIGHDEN and KXHIGHAUS. Eligible weather dates run from January 1
through October 7, 2026, inclusive. The cities and dates were fixed before the
expanded sample's results were calculated. This is a geographically varied
convenience sample, not a random draw from all prediction markets.

Each contract contributes at most one observation. Entry is 24 hours before
the **recorded exchange close**. The latest valid minute-candle bid/ask at or
before entry is selected, with at most two hours of staleness. The quote must
also follow market opening. A bid/ask midpoint strictly between zero and one
is the forecasting input. Terminal market prices are never substituted for
missing quote history. Historical `close` fields contain fixed-point dollar
strings; live candle responses use `close_dollars`. Ambiguous integer legacy
price fields are rejected instead of guessing their units.

Finalized yes/no outcomes must agree with binary settlement payouts. The
recorded settlement timestamp is the label-availability time. Model training
only uses labels available strictly before each fit cutoff. Source labels
are parsed from `rules_primary`; full rules remain in the raw catalog responses.

## What this construction does not establish

Recorded close times and rules come from current finalized metadata. We have
not reconstructed historical schedule versions or all rule changes as they
were known at entry. Entry can already fall within the weather measurement
day. This is not a forecast taken 24 hours before the weather day begins.

Candles establish historical quoted values, not fillability, depth, queue
position or exact trading costs. Quarter-Kelly results use the unchanged
assumed two-cent full spread and half-cent fee per contract. They are
illustrative simulated outcomes, not realized or execution-verified returns.

The pre-existing Chicago August–October subset was already inspected. The
broader study reuses it and is not a completely untouched final holdout.
Any strategy choices made after reviewing this expansion require a new
future holdout before making claims about prospective performance.
