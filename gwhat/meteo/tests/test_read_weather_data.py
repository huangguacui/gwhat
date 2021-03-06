# -*- coding: utf-8 -*-

# Copyright © 2014-2018 GWHAT Project Contributors
# https://github.com/jnsebgosselin/gwhat
#
# This file is part of GWHAT (Ground-Water Hydrograph Analysis Toolbox).
# Licensed under the terms of the GNU General Public License.

# ---- Standard library imports
import os
import datetime as dt
import os.path as osp

# ---- Third party imports
import numpy as np
import pandas as pd
import pytest

# ---- Local library imports
from gwhat.meteo.weather_reader import WXDataFrame
from gwhat.utils.dates import datetimeindex_to_xldates


@pytest.mark.parametrize("ext", ['.csv', '.xls', '.xlsx'])
def test_read_weather_data(ext):
    fmeteo = osp.join(osp.dirname(__file__), "sample_weather_datafile" + ext)
    wxdset = WXDataFrame(fmeteo)

    # Assert that the dataset was loaded correctly and that the 3 lines that
    # were removed manually from the dataset were added back. The lines were
    # removed for december 18, 19, and 20 of 2017.

    assert len(wxdset.data) == 2188 + 3
    assert np.all(np.diff(wxdset.data.index) == np.timedelta64(1, 'D'))
    assert wxdset.get_data_period() == (2010, 2015)

    assert np.array_equal(datetimeindex_to_xldates(wxdset.data.index),
                          np.arange(40179, 42369 + 1))
    assert np.array_equal(wxdset.data.index,
                          pd.date_range(start=dt.datetime(2010, 1, 1),
                                        end=dt.datetime(2015, 12, 31),
                                        freq='D'))
    assert np.array_equal(wxdset.data.index.year.unique(),
                          np.arange(2010, 2015 + 1))
    assert np.array_equal(wxdset.data.index.month.unique(),
                          np.arange(1, 13))

    # Assert the data for a sample of the dataset.
    assert np.array_equal(wxdset.data['Ptot'][-15:-10],
                          np.array([14, 0, 0, 0, 8.5]))
    assert np.array_equal(wxdset.data['Rain'][-15:-10],
                          np.array([14, 0, 0, 0, 0]))
    assert np.array_equal(wxdset.data['Snow'][-15:-10],
                          np.array([0, 0, 0, 0, 8.5]))
    assert np.array_equal(np.round(wxdset.data['Tavg'][-15:-10], 3),
                          np.array([4.300, 3.100, 1.900, 0.700, -0.500]))
    assert np.array_equal(np.round(wxdset.data['Tmax'][-15:-10], 3),
                          np.array([9.000, 7.750, 6.500, 5.250, 4.000]))
    assert np.array_equal(np.round(wxdset.data['Tmin'][-15:-10], 3),
                          np.array([-0.500, -1.125, -1.750, -2.375, -3.00]))


if __name__ == "__main__":
    pytest.main(['-x', os.path.basename(__file__), '-v', '-rw'])
