# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © GWHAT Project Contributors
# https://github.com/jnsebgosselin/gwhat
#
# This file is part of GWHAT (Ground-Water Hydrograph Analysis Toolbox).
# Licensed under the terms of the GNU General Public License.
# -----------------------------------------------------------------------------


# ---- Standard library imports
import csv
import datetime as dt
import os
import os.path as osp
import re
from time import strftime
from collections import OrderedDict
from collections.abc import Mapping
from abc import abstractmethod

# ---- Third party imports
import numpy as np
import pandas as pd
import xlrd
from xlrd.xldate import xldate_from_datetime_tuple, xldate_as_datetime

# ---- Local library imports
from gwhat.meteo.evapotranspiration import calcul_thornthwaite
from gwhat.common.utils import save_content_to_file
from gwhat.utils.math import nan_as_text_tolist
from gwhat import __namever__


PRECIP_VARIABLES = ['Ptot', 'Rain', 'Snow']
TEMP_VARIABLES = ['Tmax', 'Tavg', 'Tmin', 'PET']
METEO_VARIABLES = PRECIP_VARIABLES + TEMP_VARIABLES
VARLABELS_MAP = {'Ptot': 'Ptot (mm)',
                 'Rain': 'Rain (mm)',
                 'Snow': 'Snow (mm)',
                 'Tmax': 'Tmax (\u00B0C)',
                 'Tavg': 'Tavg (\u00B0C)',
                 'Tmin': 'Tmin (\u00B0C)',
                 'PET': 'PET (mm)'}
FILE_EXTS = ['.out', '.csv', '.xls', '.xlsx']


# ---- API
class WXDataFrameBase(Mapping):
    """
    A daily weather data frame base class.
    """

    def __init__(self, *args, **kwargs):
        super(WXDataFrameBase, self).__init__(*args, **kwargs)
        self.metadata = {
            'filename': '',
            'Station Name': '',
            'Station ID': '',
            'Location': '',
            'Latitude': 0,
            'Longitude': 0,
            'Elevation': 0}
        self.data = pd.DataFrame([], columns=METEO_VARIABLES)
        self.missing_value_indexes = {
            var: pd.DatetimeIndex([]) for var in METEO_VARIABLES}

    @abstractmethod
    def __load_dataset__(self):
        """Loads the dataset and save it in a store."""
        pass

    def export_dataset_to_file(self, filename, time_frame):
        """
        Exports the dataset to file using a daily, monthly or yearly format.
        The extension of the file determine in which file type the data will
        be saved (xls or xlsx for Excel, csv for coma-separated values text
        file, or tsv for tab-separated values text file).
        """
        if time_frame == 'daily':
            data = self.data.copy()
            data.insert(0, 'Year', data.index.year)
            data.insert(1, 'Month', data.index.month)
            data.insert(2, 'Day', data.index.day)
        elif time_frame == 'monthly':
            data = self.get_monthly_values()
            data.insert(0, 'Year', data.index.get_level_values(0))
            data.insert(1, 'Month', data.index.get_level_values(1))
        elif time_frame == 'yearly':
            data = self.get_yearly_values()
            data.insert(0, 'Year', data.index)
        else:
            raise ValueError('"time_frame" must be either "yearly", "monthly"'
                             ' or "daily".')

        fcontent = [['Station Name', self.metadata['Station Name']],
                    ['Station ID', self.metadata['Station ID']],
                    ['Location', self.metadata['Location']],
                    ['Latitude (\u00B0)', self.metadata['Latitude']],
                    ['Longitude (\u00B0)', self.metadata['Longitude']],
                    ['Elevation (m)', self.metadata['Elevation']],
                    ['', ''],
                    ['Start Date ', self.data.index[0].strftime("%Y-%m-%d")],
                    ['End Date ', self.data.index[-1].strftime("%Y-%m-%d")],
                    ['', ''],
                    ['Created by', __namever__],
                    ['Created on', strftime("%Y-%m-%d")],
                    ['', '']
                    ]
        fcontent.append(
            [VARLABELS_MAP.get(col, col) for col in data.columns])
        fcontent.extend(nan_as_text_tolist(data.values))
        save_content_to_file(filename, fcontent)

    def get_data_period(self):
        """
        Return the year range for which data are available for this
        dataset.
        """
        return (self.data.index.min().year, self.data.index.max().year)

    def get_xldates(self):
        """
        Return a numpy array containing the Excel numerical dates
        corresponding to the dates of the dataset.
        """
        print('Converting datetimes to xldates...', end=' ')
        timedeltas = self.data.index - xldate_as_datetime(4000, 0)
        xldates = timedeltas.total_seconds() / (3600 * 24) + 4000
        print('done')
        return xldates.values

    # ---- utilities
    def strftime(self):
        """
        Return a list of formatted strings corresponding to the datetime
        indexes of this dataset.
        """
        return self.data.index.strftime("%Y-%m-%dT%H:%M:%S").values.tolist()

    # ---- Monthly and yearly values
    def get_monthly_values(self):
        """
        Return the monthly mean or cummulative values for the weather
        variables saved in this data frame.
        """
        group = self.data.groupby(
            [self.data.index.year, self.data.index.month])
        df = pd.concat(
            [group[PRECIP_VARIABLES].sum(), group[TEMP_VARIABLES].mean()],
            axis=1)
        df.index.rename(['Year', 'Month'], inplace=True)
        return df

    def get_yearly_values(self):
        """
        Return the yearly mean or cummulative values for the weather
        variables saved in this data frame.
        """
        group = self.data.groupby(self.data.index.year)
        df = pd.concat(
            [group[PRECIP_VARIABLES].sum(), group[TEMP_VARIABLES].mean()],
            axis=1)
        df.index.rename('Year', inplace=True)
        return df

    # ---- Normals
    def get_monthly_normals(self, year_range=None):
        """
        Return the monthly normals for the weather variables saved in this
        data frame.
        """
        df = self.get_monthly_values()
        if year_range:
            df = df.loc[(df.index.get_level_values(0) >= year_range[0]) &
                        (df.index.get_level_values(0) <= year_range[1])]
        df = df.groupby(level=[1]).mean()
        df.index.rename('Month', inplace=True)
        return df

    def get_yearly_normals(self, year_range=None):
        """
        Return the yearly normals for the weather variables saved in this
        data frame.
        """
        df = self.get_yearly_values()
        if year_range:
            df = df.loc[(df.index >= year_range[0]) &
                        (df.index <= year_range[1])]
        return df.mean()


class WXDataFrame(WXDataFrameBase):
    """A daily weather dataset container that loads its data from a file."""

    def __init__(self, filename, *args, **kwargs):
        super(WXDataFrame, self).__init__(*args, **kwargs)
        self.__load_dataset__(filename)

    def __getitem__(self, key):
        raise NotImplementedError

    def __setitem__(self, key, value):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError

    def __len__(self, key):
        raise NotImplementedError

    def __load_dataset__(self, filename):
        """Loads the dataset from a file and saves it in the store."""
        print('-' * 78)
        print('Reading weather data from "%s"...' % os.path.basename(filename))

        # Import data.
        self.metadata, self.data = read_weather_datafile(filename)

        # Import the missing data log if it exist.
        root, ext = osp.splitext(filename)
        finfo = root + '.log'
        if os.path.exists(finfo):
            print('Reading gapfill data from "%s"...' % osp.basename(finfo))
            var_labels = [('Tmax', 'Max Temp (deg C)'),
                          ('Tmin', 'Min Temp (deg C)'),
                          ('Tavg', 'Mean Temp (deg C)'),
                          ('Ptot', 'Total Precip (mm)')]
            for var, label in var_labels:
                self.missing_value_indexes[var] = (
                    self.missing_value_indexes[var]
                    .append(load_weather_log(finfo, label))
                    .drop_duplicates()
                    )

        # Make the daily time series continuous.
        self.data = self.data.resample('1D').asfreq()

        # Store the time indexes where data are missing.
        for var in METEO_VARIABLES:
            if var in self.data.columns:
                self.missing_value_indexes[var] = (
                    self.missing_value_indexes[var]
                    .append(self.data.index[pd.isnull(self.data[var])])
                    .drop_duplicates()
                    )

        # Fill missing with values with in-stations linear interpolation for
        # temperature based variables.
        for var in TEMP_VARIABLES:
            if var in self.data.columns:
                self.data[var] = self.data[var].interpolate()

        # We fill the remaining missing value with 0.
        self.data = self.data.fillna(0)

        # Generate rain and snow daily series if it was not present in the
        # datafile.
        if 'Rain' not in self.data.columns:
            self.data['Rain'] = calcul_rain_from_ptot(
                self.data['Tavg'], self.data['Ptot'], Tcrit=0)
            self.data['Snow'] = self.data['Ptot'] - self.data['Rain']
            print("Rain and snow estimated from Ptot.")

        # Calculate potential evapotranspiration if missing.
        if 'PET' not in self.data.columns:
            self.data['PET'] = calcul_thornthwaite(
                self.data['Tavg'], self.metadata['Latitude'])
            print("Potential evapotranspiration evaluated with Thornthwaite.")

        isnull = self.data.isnull().any()
        if isnull.any():
            print("Warning: There is missing values remaining in the data "
                  "for {}.".format(', '.join(isnull[isnull].index.tolist())))
        print('-' * 78)


# ---- Base functions: file and data manipulation
def open_weather_datafile(filename):
    """
    Open the csv datafile and try to guess the delimiter.
    Return None if this fails.
    """
    root, ext = os.path.splitext(filename)
    if ext not in FILE_EXTS:
        raise ValueError("Supported file format are: ", FILE_EXTS)
    else:
        print('Loading daily weather time series from "%s"...' %
              osp.basename(filename))

    if ext in ['.csv', '.out']:
        for dlm in ['\t', ',', ';']:
            with open(filename, 'r') as csvfile:
                reader = list(csv.reader(csvfile, delimiter=dlm))
            for row in reader:
                if re.search(r'(time|datetime|year)',
                             ''.join(row).replace(" ", "").replace("_", ""),
                             re.IGNORECASE):
                    if len(row) >= 2:
                        return reader
                    else:
                        break
        else:
            print("Failed to open %s." % os.path.basename(filename))
            return None
    elif ext in ['.xls', '.xlsx']:
        with xlrd.open_workbook(filename, on_demand=True) as wb:
            sheet = wb.sheet_by_index(0)
            reader = [sheet.row_values(rowx, start_colx=0, end_colx=None) for
                      rowx in range(sheet.nrows)]
            return reader


def read_weather_datafile(filename):
    metadata = {'filename': filename,
                'Station Name': '',
                'Station ID': '',
                'Location': '',
                'Latitude': 0,
                'Longitude': 0,
                'Elevation': 0,
                }
    # Data is a pandas dataframe with the following required columns:
    # (1) Tmax, (2) Tavg, (3) Tmin, (4) Ptot.
    # The dataframe can also have these optional columns:
    # (5) Rain, (6) Snow, (7) PET
    # The dataframe must use a datetime index.

    # Get info from header and grab the data from the file.
    reader = open_weather_datafile(filename)
    if reader is None:
        return None, None

    HEADER_REGEX = {
        'Station Name': r'(stationname|name)',
        'Station ID': r'(stationid|id|climateidentifier)',
        'Latitude': r'(latitude)',
        'Longitude': r'(longitude)',
        'Location': r'(location|province)',
        'Elevation': r'(elevation|altitude)'
        }
    HEADER_TYPE = {
        'Station Name': str,
        'Station ID': str,
        'Location': str,
        'Latitude': float,
        'Longitude': float,
        'Elevation': float
        }

    for i, row in enumerate(reader):
        if len(row) == 0:
            continue

        label = row[0].replace(" ", "").replace("_", "")
        for key, regex in HEADER_REGEX.items():
            if re.search(regex, label, re.IGNORECASE):
                try:
                    metadata[key] = HEADER_TYPE[key](row[1])
                except ValueError:
                    # The default value will be kept.
                    print('Wrong format for entry "%s".' % key)
        else:
            if re.search(r'(time|datetime|year)', label, re.IGNORECASE):
                istart = i + 1
                break

    # Fetch the valid columns from the data header.
    COL_REGEX = OrderedDict([
        ('Year', r'(year)'),
        ('Month', r'(month)'),
        ('Day', r'(day)'),
        ('Tmax', r'(maxtemp)'),
        ('Tmin', r'(mintemp)'),
        ('Tavg', r'(meantemp)'),
        ('Ptot', r'(totalprecip)'),
        ('PET', r'(etp|evapo)'),
        ('Rain', r'(rain)'),
        ('Snow', r'(snow)')
        ])
    columns = []
    indexes = []
    for i, label in enumerate(row):
        label = label.replace(" ", "").replace("_", "")
        for column, regex in COL_REGEX.items():
            if re.search(regex, label, re.IGNORECASE):
                columns.append(column)
                indexes.append(i)
                break

    # Format the numerical data.
    data = np.array(reader[istart:])[:, indexes]
    data = np.char.strip(data, ' ')
    data[data == ''] = np.nan
    data = np.char.replace(data, ',', '.')
    data = data.astype('float')
    data = clean_endsof_file(data)

    # Format the data into a pandas dataframe.
    data = pd.DataFrame(data, columns=columns)
    for col in ['Year', 'Month', 'Day']:
        data[col] = data[col].astype(int)
    for col in ['Tmax', 'Tmin', 'Tavg', 'Ptot']:
        data[col] = data[col].astype(float)

    # We now create the time indexes for the dataframe form the year,
    # month, and day data.
    data = data.set_index(pd.to_datetime(dict(
        year=data['Year'], month=data['Month'], day=data['Day'])))
    data.drop(labels=['Year', 'Month', 'Day'], axis=1, inplace=True)

    # We print some comment if optional data was loaded from the file.
    if 'PET' in columns:
        print('Potential evapotranspiration imported from datafile.')
    if 'Rain' in columns:
        print('Rain data imported from datafile.')
    if 'Snow' in columns:
        print('Snow data imported from datafile.')

    return metadata, data


def open_weather_log(fname):
    """
    Open the csv file and try to guess the delimiter.
    Return None if this fails.
    """
    for dlm in [',', '\t']:
        with open(fname, 'r') as f:
            reader = list(csv.reader(f, delimiter=dlm))
            if reader[0][0] == 'Station Name':
                return reader[36:]
    else:
        return None


def load_weather_log(fname, varname):
    reader = open_weather_log(fname)
    datetimes = []
    for i in range(len(reader)):
        if reader[i][0] == varname:
            year = int(float(reader[i][1]))
            month = int(float(reader[i][2]))
            day = int(float(reader[i][3]))
            datetimes.append(dt.datetime(year, month, day))
    return pd.DatetimeIndex(datetimes)


def clean_endsof_file(data):
    """
    Remove nan values at the beginning and end of the record if any.
    """

    # ---- Beginning ----

    n = len(data[:, 0])
    while True:
        if len(data[:, 0]) == 0:
            print('Dataset is empty.')
            return None

        if np.all(np.isnan(data[0, 3:])):
            data = np.delete(data, 0, axis=0)
        else:
            break

    if n < len(data[:, 0]):
        print('%d empty' % (n - len(data[:, 0])) +
              ' rows of data removed at the beginning of the dataset.')

    # ---- End ----

    n = len(data[:, 0])
    while True:
        if np.all(np.isnan(data[-1, 3:])):
            data = np.delete(data, -1, axis=0)
        else:
            break

    if n < len(data[:, 0]):
        print('%d empty' % (n - len(data[:, 0])) +
              ' rows of data removed at the end of the dataset.')

    return data


# ----- Base functions: secondary variables
def calcul_rain_from_ptot(Tavg, Ptot, Tcrit=0):
    rain = Ptot.copy(deep=True)
    rain[Tavg < Tcrit] = 0

    # np.copy(Ptot)
    # rain[np.where(Tavg < Tcrit)[0]] = 0
    return rain


# ---- Utility functions
def generate_weather_HTML(staname, prov, lat, climID, lon, alt):

    # HTML table with the info related to the weather station.

    FIELDS = [['Station', staname],
              ['Latitude', '%0.3f°' % lat],
              ['Longitude', '%0.3f°' % lon],
              ['Altitude', '%0.1f m' % alt],
              ['Clim. ID', climID],
              ['Province', prov]
              ]

    table = '<table border="0" cellpadding="2" cellspacing="0" align="left">'
    for row in FIELDS:
        table += '''
                 <tr>
                   <td width=10></td>
                   <td align="left">%s</td>
                   <td align="left" width=20>:</td>
                   <td align="left">%s</td>
                   </tr>
                 ''' % (row[0], row[1])
    table += '</table>'

    return table


# %% if __name__ == '__main__'

if __name__ == '__main__':
    fmeteo = ("D:/Desktop/Meteo_station_1973a2019.csv")
    wxdset = WXDataFrame(fmeteo)
    data = wxdset.data

    monthly_values = wxdset.get_monthly_values()
    yearly_values = wxdset.get_yearly_values()

    monthly_normals = wxdset.get_monthly_normals()
    yearly_normals = wxdset.get_yearly_normals()

    print(monthly_normals, end='\n\n')
    print(yearly_normals)
