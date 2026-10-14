"""Cash-constrained, event-driven hold-to-settlement research simulation."""
import heapq
import numpy as np
import pandas as pd


def kelly_fraction(probability, cost):
    """Fraction of bankroll SPENT on a $1 binary payoff, inclusive entry cost."""
    if not 0<cost<1 or not 0<=probability<=1:
        return 0.0
    return max(0.0,min(1.0,(probability-cost)/(1-cost)))


def simulate(pred, fraction=.25, full_spread=.02, fee_per_contract=.005,
             initial_cash=10000., position_cap=.02, gross_cap=.5,event_cap=.04,
             observed_quotes=False, flat_contracts=None, weather_day_cap=None):
    """Fee/spread are user-defined scenarios, NOT exchange fee schedules.

    Open holdings remain valued at entry cost; returns/drawdown/Sharpe therefore
    describe a settlement-accounted curve, NOT daily mark-to-market performance.
    Capital is locked until outcome_available_at. Entries at the same timestamp
    share an unchanged bankroll base. Event cap uses globally matched event IDs.
    Optional weather_day_cap aggregates locked entry cost across city events
    sharing weather_date, with release at settlement. It is a pre-trade cap,
    not a forced-liquidation rule after subsequent declines in bankroll.
    """
    if not 0<fraction<=1 or min(full_spread,fee_per_contract)<0:
        raise ValueError('Invalid fraction or costs')
    if not 0<position_cap<=gross_cap<=1 or not 0<event_cap<=gross_cap or initial_cash<=0:
        raise ValueError('Invalid capital limits')
    if flat_contracts is not None and flat_contracts<=0:
        raise ValueError('flat_contracts must be positive')
    if weather_day_cap is not None:
        if not 0<weather_day_cap<=gross_cap or 'weather_date' not in pred or pred.weather_date.isna().any():
            raise ValueError('Weather-day cap requires valid weather_date and 0 < cap <= gross cap')
    day_exposure={}
    cash=float(initial_cash); locked=0.; heap=[]; counter=0; event_exposure={}; ledger=[]; points=[]
    def record(t):
        points.append(dict(time=t,equity=cash+locked,cash=cash,locked=locked))
    def settle(t):
        nonlocal cash,locked
        while heap and heap[0][0]<=t:
            when,_,cost,payout,event,day=heapq.heappop(heap)
            cash+=payout; locked-=cost; event_exposure[event]-=cost
            day_exposure[day]-=cost
            record(when)
    x=pred.sort_values(['entry_time','venue','market_id'])
    if x.empty:
        raise ValueError('No predictions to backtest')
    record(x.entry_time.min()-pd.Timedelta(seconds=1))
    for t,batch in x.groupby('entry_time',sort=True):
        settle(t); wealth=cash+locked
        for r in batch.itertuples():
            if observed_quotes:
                bid=getattr(r,'yes_bid',np.nan); ask=getattr(r,'yes_ask',np.nan)
                if not np.isfinite([bid,ask]).all():
                    raise ValueError('Observed-quote mode requires bid/ask on every row')
                yes_cost=ask+fee_per_contract; no_cost=1-bid+fee_per_contract
            else:
                yes_cost=r.price+full_spread/2+fee_per_contract
                no_cost=1-r.price+full_spread/2+fee_per_contract
            fy=kelly_fraction(r.p_model,yes_cost); fn=kelly_fraction(1-r.p_model,no_cost)
            if fy==0 and fn==0: continue
            yes=fy>=fn; f=fy if yes else fn; cost=yes_cost if yes else no_cost
            intended=(fraction*f*wealth if flat_contracts is None else flat_contracts*cost)
            event=str(r.event_id)
            day=str(getattr(r,'weather_date',event))
            day_budget=(float('inf') if weather_day_cap is None else
                        weather_day_cap*wealth-day_exposure.get(day,0))
            budget=max(0,min(intended,position_cap*wealth,cash,
                gross_cap*wealth-locked,event_cap*wealth-event_exposure.get(event,0),day_budget))
            qty=int(np.floor((budget+1e-10)/cost))
            if qty<1: continue
            spent=qty*cost; payout=qty*(r.outcome if yes else 1-r.outcome)
            cash-=spent; locked+=spent; event_exposure[event]=event_exposure.get(event,0)+spent
            day_exposure[day]=day_exposure.get(day,0)+spent
            heapq.heappush(heap,(r.outcome_available_at,counter,spent,payout,event,day));counter+=1
            ledger.append(dict(venue=r.venue,market_id=r.market_id,event_id=event,entry_time=t,
                settlement_time=r.outcome_available_at,side='YES' if yes else 'NO',contracts=qty,
                unit_cost=cost,spent=spent,payout=payout,pnl=payout-spent,
                p_model=r.p_model,price=r.price,full_kelly=f,weather_date=day,
                entry_bankroll=wealth,weather_day_locked_after=day_exposure[day]))
        record(t)
    if heap: settle(max(h[0] for h in heap))
    curve=pd.DataFrame(points).set_index('time').sort_index().groupby(level=0).last()
    daily=curve.equity.resample('D').last().ffill(); returns=daily.pct_change().dropna()
    vol=returns.std(ddof=1)
    sharpe=float(np.sqrt(365)*returns.mean()/vol) if len(returns)>1 and vol>0 else np.nan
    drawdown=curve.equity/curve.equity.cummax()-1
    stats=dict(kelly_fraction=fraction,full_spread=full_spread,fee_per_contract=fee_per_contract,
        trades=len(ledger),ending_equity=cash,total_return=cash/initial_cash-1,
        settlement_max_drawdown=float(drawdown.min()),settlement_daily_sharpe=sharpe)
    return pd.DataFrame(ledger),curve,stats
