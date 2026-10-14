import unittest
import numpy as np
import pandas as pd
from collect_multicity import dollar_close
from expanded_analysis import moving_block_interval, comparison
from pmresearch.analysis import calibration_table

class ExpansionTests(unittest.TestCase):
    def test_fixed_point_prices_and_ambiguous_legacy_rejection(self):
        self.assertEqual(dollar_close({'close_dollars':'0.45'}),.45)
        self.assertEqual(dollar_close({'close':'0.4500'}),.45)
        self.assertIsNone(dollar_close({'close':45}))
        self.assertIsNone(dollar_close({'close':'45'}))

    def fixture(self):
        days=np.repeat(pd.date_range('2026-01-01',periods=35).strftime('%Y-%m-%d'),6)
        return pd.DataFrame(dict(weather_date=days,event_id=[f'event-{i}' for i in range(len(days))],
                                 price=.2,p_model=.2,outcome=np.arange(len(days))%2))

    def test_shared_day_not_city_day_is_inference_unit(self):
        d=self.fixture()
        table=calibration_table(d)
        self.assertEqual(table.n_events.iloc[0],35)
        c=comparison(d,d.weather_date)
        self.assertEqual(c['n_clusters'],35)
        self.assertEqual(c['n_city_dates'],210)

    def test_identical_forecasts_have_zero_bootstrap_difference(self):
        for block in [7,14]:
            c=moving_block_interval(self.fixture(),block_days=block,repetitions=100)
            self.assertEqual(c['ci_low'],0)
            self.assertEqual(c['ci_high'],0)

    def test_bootstrap_reproduces_constant_difference(self):
        d=self.fixture();d['outcome']=0;d['price']=.2;d['p_model']=.3
        c=moving_block_interval(d,repetitions=100)
        self.assertAlmostEqual(c['model_minus_market_brier'],.05)
        self.assertAlmostEqual(c['ci_low'],.05)
        self.assertAlmostEqual(c['ci_high'],.05)

if __name__=='__main__':unittest.main()
