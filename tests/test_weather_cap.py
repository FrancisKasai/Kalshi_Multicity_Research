import unittest
import pandas as pd
from pmresearch.backtest import simulate

class WeatherCapTests(unittest.TestCase):
    def records(self):
        t=pd.Timestamp('2026-01-01',tz='UTC')
        return pd.DataFrame([dict(venue='kalshi',market_id=str(i),event_id=f'city-{i}',
             weather_date='2026-01-01',entry_time=t+pd.Timedelta(hours=i),
             outcome_available_at=t+pd.Timedelta(days=1),price=.5,p_model=.9,outcome=1)
             for i in range(3)])

    def test_combines_different_cities_and_entry_times(self):
        d=self.records()
        trades,_,_=simulate(d,initial_cash=10000,fraction=1,full_spread=0,fee_per_contract=0,
                            position_cap=.03,event_cap=.04,weather_day_cap=.04)
        self.assertEqual(len(trades),2)
        self.assertAlmostEqual(trades.spent.sum(),400)
        self.assertAlmostEqual(trades.weather_day_locked_after.max(),400)

    def test_releases_group_exposure_only_at_settlement(self):
        d=self.records().iloc[:2].copy()
        d.loc[0,'outcome_available_at']=d.loc[1,'entry_time']
        trades,_,_=simulate(d,initial_cash=10000,fraction=1,full_spread=0,fee_per_contract=0,
                            position_cap=.04,weather_day_cap=.04)
        self.assertEqual(len(trades),2)
        self.assertAlmostEqual(trades.spent.iloc[0],400)
        self.assertAlmostEqual(trades.spent.iloc[1],416)
        self.assertAlmostEqual(trades.weather_day_locked_after.iloc[1],416)

    def test_rejects_missing_group_identifier(self):
        with self.assertRaises(ValueError):
            simulate(self.records().drop(columns='weather_date'),weather_day_cap=.04)

if __name__=='__main__':unittest.main()
