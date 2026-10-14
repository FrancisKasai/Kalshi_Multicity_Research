import unittest
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from pmresearch.data import synthetic_data,validate
from pmresearch.analysis import walk_forward,holm,calibration_table
from pmresearch.backtest import simulate,kelly_fraction
from pmresearch.collect import latest_quote,fetch_quotes,candle_price,MANIFEST

class ResearchTests(unittest.TestCase):
    def test_kelly_matches_log_wealth_optimum(self):
        for p,c in [(.6,.5),(.95,.9),(.08,.04)]:
            loss=lambda f:-(p*np.log(1+f*(1-c)/c)+(1-p)*np.log(1-f))
            opt=minimize_scalar(loss,bounds=(0,.999999),method='bounded').x
            self.assertAlmostEqual(kelly_fraction(p,c),opt,places=5)
        self.assertEqual(kelly_fraction(.4,.5),0)
        self.assertAlmostEqual(kelly_fraction(.6,.5),.2)
    def test_rejects_bad_time_and_duplicates(self):
        d=synthetic_data(10)
        with self.assertRaises(ValueError):validate(pd.concat([d,d]))
        d.loc[0,'quote_time']=d.loc[0,'event_time']
        with self.assertRaises(ValueError):validate(d)
    def test_staleness(self):
        d=synthetic_data(10);d['quote_time']-=pd.Timedelta(hours=3)
        with self.assertRaises(ValueError):validate(d)
    def test_future_labels_do_not_change_earlier_predictions(self):
        d=synthetic_data(700);p=walk_forward(d)
        lastblock=p.block.max();first=p[p.block==lastblock].entry_time.min()
        modified=d.copy();mask=modified.entry_time>=first
        modified.loc[mask,'outcome']=1-modified.loc[mask,'outcome']
        q=walk_forward(modified)
        np.testing.assert_allclose(p.p_model,q.p_model)
        self.assertTrue((p.latest_training_outcome<p.fit_cutoff).all())
        self.assertTrue((p.fit_cutoff<=p.entry_time).all())
    def test_training_counts_exclude_shared_events(self):
        d=synthetic_data(700);p=walk_forward(d)
        for (_,v),g in p.groupby(['block','venue']):
            cutoff=g.fit_cutoff.iloc[0];events=p[p.block==g.block.iloc[0]].event_id
            eligible=d[(d.venue==v)&(d.outcome_available_at<cutoff)&(~d.event_id.isin(events))]
            self.assertEqual(g.n_train.iloc[0],len(eligible))
    def test_clusters_and_holm(self):
        table=calibration_table(synthetic_data(100))
        self.assertTrue((table.n_events<=table.n).all())
        np.testing.assert_allclose(holm([.01,.04,.03]),[.03,.06,.06])
    def test_cash_conservation_and_locked_capital(self):
        d=synthetic_data(3);d['entry_time']=d.entry_time.min();d['quote_time']=d.entry_time
        d['p_model']=.99;d['price']=.5
        ledger,curve,s=simulate(d,initial_cash=100,position_cap=.5,gross_cap=.5,event_cap=.5,fee_per_contract=0,full_spread=0)
        self.assertGreater(len(ledger),0)
        self.assertLessEqual(ledger.spent.sum(),50+1e-8)
        self.assertTrue((curve.cash>=-1e-8).all())
        self.assertAlmostEqual(s['ending_equity'],100+ledger.pnl.sum())
        self.assertAlmostEqual(curve.locked.iloc[-1],0)
    def test_no_edge_no_trades(self):
        d=synthetic_data(10);d['p_model']=d.price
        ledger,curve,s=simulate(d)
        self.assertEqual(len(ledger),0);self.assertEqual(s['ending_equity'],10000)
    def test_no_side(self):
        d=synthetic_data(1).iloc[:1].copy();d['price']=.8;d['p_model']=.4
        ledger,_,_=simulate(d)
        self.assertEqual(ledger.side.iloc[0],'NO')
    def test_selects_only_past_quote(self):
        t=pd.Timestamp('2025-01-01',tz='UTC')
        points=[dict(quote_time=t-pd.Timedelta(minutes=1),price=.4),dict(quote_time=t+pd.Timedelta(seconds=1),price=.9)]
        self.assertEqual(latest_quote(points,t,2)['price'],.4)
        with self.assertRaises(ValueError):latest_quote(points[1:],t,2)
    def test_price_units(self):
        self.assertEqual(candle_price({'yes_bid':{'close_dollars':'0.45'}},'yes_bid'),.45)
        self.assertEqual(candle_price({'yes_bid':{'close':45}},'yes_bid'),.45)
    def test_collect_fixture_and_approval(self):
        class Fake:
            def get(self,*args,**kwargs):
                return {'history':[{'t':1735689600,'p':.3},{'t':1735689601,'p':.99}]}
        row={k:'' for k in MANIFEST}
        row.update(venue='polymarket',market_id='1',event_id='event1',category='sports',
            yes_token_id='1234567890123456789',event_time='2025-01-03T00:00:00Z',
            outcome_available_at='2025-01-03T02:00:00Z',outcome=1,approved=True,audit_notes='Fixture')
        good,bad=fetch_quotes(pd.DataFrame([row]),Fake())
        self.assertEqual(len(bad),0);self.assertEqual(good.price.iloc[0],.3)
        row['approved']=False
        good,bad=fetch_quotes(pd.DataFrame([row]),Fake())
        self.assertEqual(len(good),0);self.assertEqual(len(bad),1)

if __name__=='__main__':unittest.main()
