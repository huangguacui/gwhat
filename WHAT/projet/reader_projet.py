# -*- coding: utf-8 -*-
"""
Copyright 2014-2017 Jean-Sebastien Gosselin
email: jean-sebastien.gosselin@ete.inrs.ca

This file is part of WHAT (Well Hydrograph Analysis Toolbox).

WHAT is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""

from __future__ import division, unicode_literals

# Standard library imports :

import os
import csv

# Third party imports :

import h5py
import numpy as np


class ProjetReader(object):
    def __init__(self, filename):
        self.__db = None
        self.load_projet(filename)

    def __del__(self):
        self.close_projet()

    @property
    def db(self):  # project data base
        return self.__db

    @property
    def filename(self):
        return self.db.filename

    # =========================================================================

    def load_projet(self, filename):
        self.close_projet()

        print('\nLoading "%s"...' % os.path.basename(filename))

        try:
            self.__db = h5py.File(filename, mode='a')
        except:
            self.convert_projet_format(filename)

        # for newly created project and backward compatibility :

        for key in ['name', 'author', 'created', 'modified', 'version']:
            if key not in list(self.db.attrs.keys()):
                self.db.attrs[key] = 'None'

        for key in ['latitude', 'longitude']:
            if key not in list(self.db.attrs.keys()):
                self.db.attrs[key] = 0

        for key in ['wldsets', 'wxdsets']:
            if key not in list(self.db.keys()):
                self.db.create_group(key)

        print('Project "%s" loaded succesfully\n' % self.name)

    def convert_projet_format(self, filename):
        try:
            print('Old file format. Converting to the new format...')
            with open(filename, 'r', encoding='utf-8') as f:
                reader = list(csv.reader(f, delimiter='\t'))

                name = reader[0][1]
                author = reader[1][1]
                created = reader[2][1]
                modified = reader[3][1]
                version = reader[4][1]
                lat = float(reader[6][1])
                lon = float(reader[7][1])
        except:
            self.__db = None
            raise ValueError('Project file is not valid!')
        else:
            os.remove(filename)

            self.__db = db = h5py.File(filename, mode='w')

            db.attrs['name'] = name
            db.attrs['author'] = author
            db.attrs['created'] = created
            db.attrs['modified'] = modified
            db.attrs['version'] = version
            db.attrs['latitude'] = lat
            db.attrs['longitude'] = lon

            print('Projet converted to the new format successfully.')

    def close_projet(self):
        try:
            self.db.close()
        except:
            pass  # projet is None or already closed

    # =========================================================================

    @property
    def name(self):
        return self.db.attrs['name']

    @name.setter
    def name(self, x):
        self.db.attrs['name'] = x

    @property
    def author(self):
        return self.db.attrs['author']

    @author.setter
    def author(self, x):
        self.db.attrs['author'] = x

    @property
    def created(self):
        return self.db.attrs['created']

    @created.setter
    def created(self, x):
        self.db.attrs['created'] = x

    @property
    def modified(self):
        return self.db.attrs['modified']

    @modified.setter
    def modified(self, x):
        self.db.attrs['modified'] = x

    @property
    def version(self):
        return self.db.attrs['version']

    @version.setter
    def version(self, x):
        self.db.attrs['version'] = x

    # -------------------------------------------------------------------------

    @property
    def lat(self):
        return self.db.attrs['latitude']

    @lat.setter
    def lat(self, x):
        self.db.attrs['latitude'] = x

    @property
    def lon(self):
        return self.db.attrs['longitude']

    @lon.setter
    def lon(self, x):
        self.db.attrs['longitude'] = x

    # ======================================================== water level ====

    @property
    def wldsets(self):
        return list(self.db['wldsets'].keys())

    def get_wldset(self, name):
        if name in self.wldsets:
            return WLDataFrame(self.db['wldsets/%s' % name])
        else:
            return None

    def add_wldset(self, name, df):
        grp = self.db['wldsets'].create_group(name)

        grp.create_dataset('Time', data=df['Time'])
        grp.create_dataset('WL', data=df['WL'])
        grp.create_dataset('BP', data=df['BP'])
        grp.create_dataset('ET', data=df['ET'])

        grp.attrs['filename'] = df['filename']
        grp.attrs['Well'] = df['Well']
        grp.attrs['Latitude'] = df['Latitude']
        grp.attrs['Longitude'] = df['Longitude']
        grp.attrs['Elevation'] = df['Elevation']
        grp.attrs['Municipality'] = df['Municipality']

        grp.create_group('brf')
        grp.create_group('layout')

        mmeas = grp.create_group('manual')
        mmeas.create_dataset('Time', data=np.array([]), maxshape=None)
        mmeas.create_dataset('WL', data=np.array([]), maxshape=None)

        print('New dataset created sucessfully')

        self.db.flush()

        return WLDataFrame(grp)

    def del_wldset(self, name):
        del self.db['wldsets/%s' % name]

    # =========================================================== weather =====

    @property
    def wxdsets(self):
        return list(self.db['wxdsets'].keys())

    def get_wxdset(self, name):
        if name in self.wxdsets:
            return WXDataFrame(self.db['wxdsets/%s' % name])
        else:
            return None

    def add_wxdset(self, name, df):
        grp = self.db['wxdsets'].create_group(name)

        grp.attrs['filename'] = df['filename']
        grp.attrs['Station Name'] = df['Station Name']
        grp.attrs['Latitude'] = df['Latitude']
        grp.attrs['Longitude'] = df['Longitude']
        grp.attrs['Elevation'] = df['Elevation']
        grp.attrs['Province'] = df['Province']
        grp.attrs['Climate Identifier'] = df['Climate Identifier']

        grp.create_dataset('Time', data=df['Time'])
        grp.create_dataset('Year', data=df['Year'])
        grp.create_dataset('Month', data=df['Month'])
        grp.create_dataset('Day', data=df['Day'])
        grp.create_dataset('Tmax', data=df['Tmax'])
        grp.create_dataset('Tavg', data=df['Tavg'])
        grp.create_dataset('Tmin', data=df['Tmin'])
        grp.create_dataset('Ptot', data=df['Ptot'])
        grp.create_dataset('Rain', data=df['Rain'])
        grp.create_dataset('PET', data=df['PET'])

        grp.create_dataset('Monthly Year', data=df['Monthly Year'])
        grp.create_dataset('Monthly Month', data=df['Monthly Month'])
        grp.create_dataset('Monthly Tmax', data=df['Monthly Tmax'])
        grp.create_dataset('Monthly Tmin', data=df['Monthly Tmin'])
        grp.create_dataset('Monthly Tavg', data=df['Monthly Tavg'])
        grp.create_dataset('Monthly Ptot', data=df['Monthly Ptot'])
        grp.create_dataset('Monthly Rain', data=df['Monthly Rain'])
        grp.create_dataset('Monthly PET', data=df['Monthly PET'])

        grp_norm = grp.create_group('normals')
        grp_norm.create_dataset('Tmax', data=df['normals']['Tmax'])
        grp_norm.create_dataset('Tmin', data=df['normals']['Tmin'])
        grp_norm.create_dataset('Tavg', data=df['normals']['Tavg'])
        grp_norm.create_dataset('Ptot', data=df['normals']['Ptot'])
        grp_norm.create_dataset('Rain', data=df['normals']['Rain'])
        grp_norm.create_dataset('PET', data=df['normals']['PET'])

        grp.create_dataset('Missing Tmax', data=df['Missing Tmax'])
        grp.create_dataset('Missing Tmin', data=df['Missing Tmin'])
        grp.create_dataset('Missing Tavg', data=df['Missing Tavg'])
        grp.create_dataset('Missing Ptot', data=df['Missing Ptot'])

        print('New dataset created sucessfully')

        self.db.flush()

    def del_wxdset(self, name):
        del self.db['wxdsets/%s' % name]


# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


class WLDataFrame(dict):
    # This is a wrapper around the h5py group that is used to store
    # water level datasets.
    def __init__(self, dset, *args, **kwargs):
        super(WLDataFrame, self).__init__(*args, **kwargs)
        self.dset = dset

    def __getitem__(self, key):
        if key in list(self.dset.attrs.keys()):
            return self.dset.attrs[key]
        else:
            return self.dset[key].value

    @property
    def name(self):
        return self.dset.name

    # =========================================================================

    def write_wlmeas(self, time, wl):
        self.dset['manual/Time'][:] = time
        self.dset['manual/WL'][:] = wl

    def get_write_wlmeas(self):
        grp = self.dset.require_group('manual')
        return grp['Time'].value, grp['WL'].value

    # =========================================================================

    def save_layout(self, layout):
        grp = self.dset['layout']
        for key in list(layout.keys()):
            if key == 'colors':
                grp_colors = grp.require_group(key)
                for color in layout['colors'].keys():
                    grp_colors.attrs[color] = layout['colors'][color]
            else:
                grp.attrs[key] = layout[key]

    def get_layout(self):
        if 'TIMEmin' not in self.dset['layout'].attrs.keys():
            return None

        layout = {}
        for key in list(self.dset['layout'].attrs.keys()):
            if key in ['legend_on', 'title_on', 'trend_line']:
                layout[key] = (self.dset['layout'].attrs[key] == 'True')
            else:
                layout[key] = self.dset['layout'].attrs[key]

        layout['colors'] = {}
        grp_colors = self.dset['layout'].require_group('colors')
        for key in list(grp_colors.attrs.keys()):
            layout['colors'][key] = grp_colors.attrs[key].tolist()

        return layout


# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


class WXDataFrame(dict):
    # This is a wrapper around the h5py group that is used to store
    # weather datasets.
    def __init__(self, dset, *args, **kwargs):
        super(WXDataFrame, self).__init__(*args, **kwargs)
        self.dset = dset

    def __getitem__(self, key):
        if key in list(self.dset.attrs.keys()):
            return self.dset.attrs[key]
        elif key == 'normals':
            grp = self.dset['normals']
            x = {'Tmax': grp['Tmax'].value,
                 'Tmin': grp['Tmin'].value,
                 'Tavg': grp['Tavg'].value,
                 'Ptot': grp['Ptot'].value,
                 'Rain': grp['Rain'].value,
                 'PET': grp['PET'].value}
            return x
        else:
            return self.dset[key].value

    @property
    def name(self):
        return os.path.basename(self.dset.name)

    # def __setitem__(self, key, val):
    #    dict.__setitem__(self, key, val)


if __name__ == '__main__':
    f = 'C:/Users/jnsebgosselin/Desktop/Project4Testing/Project4Testing.what'
    pr = ProjetReader(f)