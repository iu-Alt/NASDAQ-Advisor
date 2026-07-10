import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.data import fetcher


class FetcherTests(unittest.TestCase):
    def test_dxy_cache_uses_incremental_update_when_cache_exists(self):
        existing = pd.DataFrame(
            {"close": [100.0]},
            index=pd.to_datetime(["2024-01-01"]),
        )
        new_data = pd.DataFrame(
            {"close": [101.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )
        combined = pd.concat([existing, new_data])

        with patch.object(fetcher, "get_missing_range", return_value=("2024-01-01", "2024-01-03")) as missing, \
             patch.object(fetcher, "load_cache", return_value=existing) as load_cache, \
             patch.object(fetcher, "_safe_yf_download", return_value=new_data) as download, \
             patch.object(fetcher, "update_cache", return_value=combined) as update_cache:

            result = fetcher.fetch_dxy_data()

        missing.assert_called_once()
        load_cache.assert_called_once()
        download.assert_called_once_with("DX-Y.NYB", "2024-01-01", "2024-01-03")
        update_cache.assert_called_once()
        self.assertEqual(len(result), 2)

    def test_dxy_cache_returns_existing_when_up_to_date(self):
        existing = pd.DataFrame(
            {"close": [100.0]},
            index=pd.to_datetime(["2024-01-01"]),
        )

        with patch.object(fetcher, "get_missing_range", return_value=(None, None)), \
             patch.object(fetcher, "load_cache", return_value=existing), \
             patch.object(fetcher, "_safe_yf_download") as download:

            result = fetcher.fetch_dxy_data()

        download.assert_not_called()
        self.assertIs(result, existing)


if __name__ == "__main__":
    unittest.main()
