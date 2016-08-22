# -*- coding: utf-8 -*-
"""
Copyright 2014-2016 Jean-Sebastien Gosselin
email: jnsebgosselin@gmail.com

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


# STANDARD LIBRARY IMPORTS :

from sys import argv
from time import clock
import csv
import os
import datetime

# THIRD PARTY IMPORTS :

import numpy as np
from PySide import QtGui, QtCore

import matplotlib as mpl
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT
import matplotlib.pyplot as plt

# from xlrd import xldate_as_tuple
from xlrd.xldate import xldate_from_date_tuple

# PERSONAL IMPORTS :

from custom_widgets import VSep, MyQToolButton
import database as db
import meteo
from waterlvldata import WaterlvlData
from gwrecharge_calc2 import SynthHydrograph

mpl.use('Qt4Agg')
mpl.rcParams['backend.qt4'] = 'PySide'


class Tooltips():

    def __init__(self, language):  # ------------------------------- ENGLISH --

        # Toolbar :

        self.undo = 'Undo'
        self.clearall = 'Clear all extremum from the graph'
        self.home = 'Reset original view.'
        self.delPeak = ('Toggle edit mode to manually remove extremums '
                        'from the graph')
        self.pan = 'Pan axes with left mouse, zoom with right'
        self.MRCalc = ('Calculate the Master Recession Curve (MRC) for the '
                       'selected time pertiods')
        self.editPeak = ('Toggle edit mode to manually add extremums '
                         'to the graph')
        self.toggle_layout_mode = ('Toggle between layout and computation '
                                   'mode (EXPERIMENTAL FEATURE)')
        self.find_peak = ('Automated search for local '
                          'extremum (EXPERIMENTAL FEATURE)')
        self.btn_Waterlvl_lineStyle = ('Show water lvl data as dots instead '
                                       'of a continuous line')
        self.btn_strati = ('Toggle on and off the display of the soil'
                           ' stratigraphic layers')
        self.btn_save_interp = 'Save Calculated MRC to file.'
        self.mrc2rechg = ('Compute recharge from the water level time series'
                          ' using the MRC calculated and the water-table'
                          ' fluctuation principle')
        self.btn_dateFormat = ('x axis label time format: '
                               'date or MS Excel numeric')
        self.btn_recharge = ('Show window for recharge estimation')

        if language == 'French':  # --------------------------------- FRENCH --

            pass


###############################################################################


class WLCalc(QtGui.QWidget):                                         # WLCalc #

    """
    This is the interface where are plotted the water level time series. It is
    possible to dynamically zoom and span the data, change the display,
    i.e. display the data as a continuous line or individual dot, perform a
    MRC and ultimately estimate groundwater recharge.
    """

    def __init__(self, parent=None):  # =======================================
        super(WLCalc, self).__init__(parent)

        self.isGraphExists = False
        self.__figbckground = None  # figure background

        # Water Level Time series :

        self.waterLvl_data = WaterlvlData()

        self.time = []
        self.txls = []  # time in Excel format
        self.tmpl = []  # time in matplotlib format
        self.water_lvl = []

        # Weather Data :

        self.meteo_data = meteo.MeteoObj()

        # Date System :

        t1 = xldate_from_date_tuple((2000, 1, 1), 0)  # time in Excel
        t2 = mpl.dates.date2num(datetime.datetime(2000, 1, 1))  # Time in
        self.dt4xls2mpl = t2-t1  # Delta between the datum of both date system

        # Date format: can either be 0 for Excel format or 1 for Matplotlib
        # format.

        self.dformat = 1

        # Recession Curve Parameters :

        self.A = None
        self.B = None
        self.RMSE = None
        self.hrecess = []

        self.peak_indx = np.array([]).astype(int)
        self.peak_memory = [np.array([]).astype(int)]
        print(len(self.peak_memory))

        # Soil Profiles :

        self.soilFilename = []
        self.SOILPROFIL = SoilProfil()

        # Recharge :

        self.rechg_setup_win = RechgSetupWin()

        self.synth_hydro_widg = SynthHydroWidg()
        self.synth_hydro_widg.hide()
        self.synth_hydro_widg.newHydroParaSent.connect(self.plot_synth_hydro)

        self.synth_hydrograph = SynthHydrograph()

        # INIT UI :

        self.__initFig__()
        self.__initUI__()

    def __initFig__(self):  # =================================================

        # ----------------------------------------------------------- CANVAS --

        # Create a Qt figure canvas :

        self.fig = mpl.figure.Figure(facecolor='white')
        self.canvas = FigureCanvasQTAgg(self.fig)

        self.canvas.mpl_connect('button_press_event', self.onclick)
        self.canvas.mpl_connect('resize_event', self.setup_ax_margins)
        self.canvas.mpl_connect('motion_notify_event', self.mouse_vguide)

        # ------------------------------------------------------------ FRAME --

        # Put figure canvas in a QFrame widget.

        fig_frame_grid = QtGui.QGridLayout()
        self.fig_frame_widget = QtGui.QFrame()

        fig_frame_grid.addWidget(self.canvas, 0, 0)

        self.fig_frame_widget.setLayout(fig_frame_grid)
        fig_frame_grid.setContentsMargins(0, 0, 0, 0)  # [L, T, R, B]

        self.fig_frame_widget.setFrameStyle(db.styleUI().frame)
        self.fig_frame_widget.setLineWidth(2)
        self.fig_frame_widget.setMidLineWidth(1)

        # ------------------------------------------------------------- AXES --

        # Water Level (Host) :
        ax0 = self.fig.add_axes([0, 0, 1, 1], zorder=100)
        ax0.patch.set_visible(False)
        ax0.invert_yaxis()

        # Precipitation :
        ax1 = ax0.twinx()
        ax1.patch.set_visible(False)
        ax1.set_zorder(50)
        ax1.set_navigate(False)
        ax1.invert_yaxis()
        ax1.axis(ymin=100, ymax=0)

        # ----------------------------------------------------------- XTICKS --

        ax0.xaxis.set_ticks_position('bottom')
        ax0.tick_params(axis='x', direction='out')

        # ----------------------------------------------------------- YTICKS --

        ax0.yaxis.set_ticks_position('left')
        ax0.tick_params(axis='y', direction='out')

        ax1.yaxis.set_ticks_position('right')
        ax1.tick_params(axis='y', direction='out')

        # ----------------------------------------------------------- LABELS --

        ax0.set_ylabel('Water level (mbgs)', fontsize=14, labelpad=25,
                       va='top', color='black')
        ax0.set_xlabel('Time (days)', fontsize=14, labelpad=25,
                       va='bottom', color='black')
        ax1.set_ylabel('Precipitation (mm)', fontsize=14, labelpad=25,
                       va='top', color='black', rotation=270)

        # -------------------------------------------------- Setup Gridlines --

        ax0.grid(axis='x', color=[0.65, 0.65, 0.65], ls=':')
        ax0.set_axisbelow(True)

        # ---------------------------------------------------------- ARTISTS --

        # Water level :
        self.h1_ax0, = ax0.plot([], [], color='blue', clip_on=True, ls='-',
                                zorder=10, marker='None')

        # Rain :
        self.h_rain, = ax1.plot([], [])

        # Vertical guide line under cursor :
        self.vguide = ax0.axvline(-1, color='red', zorder=40)
        self.vguide.set_xdata(-1)

        # ---------------------------------------------------------- MARGINS --

        self.setup_ax_margins(None)

    def __initUI__(self):  # ==================================================

        iconDB = db.Icons()
        ttipDB = Tooltips('English')

        self.setWindowTitle('Master Recession Curve Estimation')

        # ---------------------------------------------------------- TOOLBAR --

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.hide()

        # Toolbar Buttons :

        self.btn_layout_mode = MyQToolButton(
            iconDB.toggleMode, ttipDB.toggle_layout_mode, autoRaise=False)

        self.btn_undo = MyQToolButton(iconDB.undo, ttipDB.undo, enabled=False)
        self.btn_undo.clicked.connect(self.undo)

        self.btn_clearPeak = MyQToolButton(
            iconDB.clear_search, ttipDB.clearall)
        self.btn_clearPeak.clicked.connect(self.clear_all_peaks)

        self.btn_home = MyQToolButton(iconDB.home, ttipDB.home)
        self.btn_home.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_editPeak = MyQToolButton(iconDB.add_point, ttipDB.editPeak)
        self.btn_editPeak.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_delPeak = MyQToolButton(iconDB.erase, ttipDB.delPeak)
        self.btn_delPeak.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_pan = MyQToolButton(iconDB.pan, ttipDB.pan)
        self.btn_pan.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_MRCalc = MyQToolButton(iconDB.MRCalc, ttipDB.MRCalc)
        self.btn_MRCalc.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_strati = MyQToolButton(iconDB.stratigraphy, ttipDB.btn_strati)
        self.btn_strati.clicked.connect(self.btn_strati_isClicked)

        self.btn_Waterlvl_lineStyle = MyQToolButton(
            iconDB.showDataDots, ttipDB.btn_Waterlvl_lineStyle)
        self.btn_Waterlvl_lineStyle.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_save_interp = MyQToolButton(
            iconDB.save, ttipDB.btn_save_interp)
        self.btn_save_interp.clicked.connect(self.aToolbarBtn_isClicked)

        self.btn_dateFormat = MyQToolButton(
              iconDB.calendar, ttipDB.btn_dateFormat, autoRaise=1-self.dformat)
        self.btn_dateFormat.clicked.connect(self.aToolbarBtn_isClicked)
        # dformat: 0 -> Excel Numeric Date Format
        #          1 -> Matplotlib Date Format

        self.btn_recharge = MyQToolButton(
            iconDB.page_setup, ttipDB.btn_recharge)
        self.btn_recharge.clicked.connect(self.rechg_setup_win.show)

        self.btn_synthHydro = MyQToolButton(
            iconDB.page_setup, 'Show synthetic hydrograph')
        self.btn_synthHydro.clicked.connect(self.synth_hydro_widg.toggleOnOff)

#        self.btn_findPeak = toolBarBtn(iconDB.findPeak2, ttipDB.find_peak)
#        self.btn_findPeak.clicked.connect(self.find_peak)
#        self.btn_mrc2rechg = toolBarBtn(iconDB.mrc2rechg, ttipDB.mrc2rechg)
#        self.btn_mrc2rechg.clicked.connect(self.btn_mrc2rechg_isClicked)

        # Grid Layout :

        btn_list = [self.btn_layout_mode, VSep(), self.btn_undo,
                    self.btn_clearPeak, self.btn_editPeak, self.btn_delPeak,
                    VSep(), self.btn_home, self.btn_pan, VSep(),
                    self.btn_MRCalc, self.btn_save_interp, VSep(),
                    self.btn_Waterlvl_lineStyle, self.btn_dateFormat,
                    self.btn_recharge, self.btn_synthHydro]

        subgrid_toolbar = QtGui.QGridLayout()
        toolbar_widget = QtGui.QWidget()

        for col, btn in enumerate(btn_list):
            subgrid_toolbar.addWidget(btn, 0, col)
        subgrid_toolbar.setColumnStretch(col+1, 500)

        subgrid_toolbar.setSpacing(5)
        subgrid_toolbar.setContentsMargins(0, 0, 0, 0)

        toolbar_widget.setLayout(subgrid_toolbar)

        # --------------------------------------------------- MRC PARAMETERS --

        self.MRC_type = QtGui.QComboBox()
        self.MRC_type.addItems(['Linear', 'Exponential'])
        self.MRC_type.setCurrentIndex(1)

        self.MRC_ObjFnType = QtGui.QComboBox()
        self.MRC_ObjFnType.addItems(['RMSE', 'MAE'])
        self.MRC_ObjFnType.setCurrentIndex(0)

        self.MRC_results = QtGui.QTextEdit()
        self.MRC_results.setReadOnly(True)
        self.MRC_results.setFixedHeight(100)

        grid_MRCparam = QtGui.QGridLayout()
        self.widget_MRCparam = QtGui.QFrame()
#        self.widget_MRCparam.setFrameStyle(StyleDB.frame)

        row = 0
        grid_MRCparam.addWidget(QtGui.QLabel('MRC Type :'), row, 0)
        grid_MRCparam.addWidget(self.MRC_type, row, 1)
#        row += 1
#        grid_MRCparam.addWidget(self.MRC_ObjFnType, row, col)
        row += 1
        grid_MRCparam.addWidget(self.MRC_results, row, 0, 1, 2)

        grid_MRCparam.setSpacing(5)
        grid_MRCparam.setContentsMargins(0, 0, 0, 0)  # (L, T, R, B)
        grid_MRCparam.setColumnStretch(1, 500)

        self.widget_MRCparam.setLayout(grid_MRCparam)

        # -------------------------------------------------------- MAIN GRID --

        mainGrid = QtGui.QGridLayout()

        items = [toolbar_widget, self.fig_frame_widget, self.synth_hydro_widg]
        for row, item in enumerate(items):
            mainGrid.addWidget(item, row, 0)

        mainGrid.setContentsMargins(0, 0, 0, 0)  # Left, Top, Right, Bottom
        mainGrid.setRowStretch(1, 500)

        self.setLayout(mainGrid)

    def __save_figbckground__(self):  # =======================================
        ax = self.fig.axes[0]
        if self.vguide.get_xdata() != -1:
            self.vguide.set_visible(False)
            self.canvas.draw()
            self.__figbckground = self.fig.canvas.copy_from_bbox(ax.bbox)
            self.vguide.set_visible(True)
            self.canvas.draw()
        else:
            self.canvas.draw()
            self.__figbckground = self.fig.canvas.copy_from_bbox(ax.bbox)

    def emit_error_message(self, error_text):  # ==============================

        msgError = QtGui.QMessageBox()
        msgError.setIcon(QtGui.QMessageBox.Warning)
        msgError.setWindowTitle('Error Message')
        msgError.setWindowIcon(db.Icons().WHAT)

        msgError.setText(error_text)
        msgError.exec_()

    def load_weather_data(self, filename):  # =================================
        self.meteo_data.load_and_format(filename)
        x = self.meteo_data.TIME
        y = self.meteo_data.DATA[:, -1]

        self.h_rain.set_data(x, y)
        self.canvas.draw()

    def load_waterLvl_data(self, filename):  # ================================

        # Load Water Level Data :

        self.waterLvl_data.load(filename)

        self.water_lvl = self.waterLvl_data.lvl
        self.time = self.waterLvl_data.time
        self.soilFilename = self.waterLvl_data.soilFilename

        self.init_hydrograph()
        self.load_MRC_interp()

        # Reset UI :

        self.btn_Waterlvl_lineStyle.setAutoRaise(True)

    def load_MRC_interp(self):  # =============================================

        # ---- Load .wif file ----

        isWif = self.waterLvl_data.load_interpretation_file()
        if isWif is False:  # No .wif file has been created yet for this well
            return

        # ---- Extract Local Extremum Times ----

        tr = self.waterLvl_data.trecess
        hr = self.waterLvl_data.hrecess

        tb = []  # Time boundary for recession segments
        for i in range(len(tr)):
            if not np.isnan(hr[i]):
                try:
                    if np.isnan(hr[i-1]) or np.isnan(hr[i+1]):
                        tb.append(tr[i])
                except IndexError:
                    tb.append(tr[i])

        # ---- Convert Time to Indexes ----
        time = self.waterLvl_data.time
        self.peak_indx = np.zeros(len(tb)).astype(int)

        for i in range(len(tb)):
            close = np.isclose(tb[i], time, rtol=0, atol=10**-6)
            indx = np.where(close == True)[0][0]
            self.peak_indx[i] = indx

        # ---- Recalculate and Plot Results ----

        self.peak_memory[0] = self.peak_indx
        self.plot_peak()
        self.btn_MRCalc_isClicked()

    def aToolbarBtn_isClicked(self):  # =======================================

        # slot that redirects all clicked actions from the toolbar buttons

        if not self.waterLvl_data.wlvlFilename:
            msg = 'Please select a valid Water Level Data File first.'
            print(msg)
            self.emit_error_message('<b>%s</b>' % msg)
            return

        if self.sender() == self.btn_MRCalc:
            self.btn_MRCalc_isClicked()
        elif self.sender() == self.btn_Waterlvl_lineStyle:
            self.change_waterlvl_lineStyle()
        elif self.sender() == self.btn_home:
            self.home()
        elif self.sender() == self.btn_save_interp:
            self.save_interp()
        elif self.sender() == self.btn_editPeak:
            self.add_peak()
        elif self.sender() == self.btn_delPeak:
            self.delete_peak()
        elif self.sender() == self.btn_pan:
            self.pan_graph()
        elif self.sender() == self.btn_dateFormat:
            self.switch_date_format()

    def btn_MRCalc_isClicked(self):  # ========================================

        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        A, B, hp, RMSE = mrc_calc(self.time, self.water_lvl, self.peak_indx,
                                  self.MRC_type.currentIndex())

        print(A, B)
        if A is None:
            QtGui.QApplication.restoreOverrideCursor()
            return

        # Display result :

        txt = u'∂h/∂t (mm/d) = -%0.2f h + %0.2f' % (A*1000, B*1000)
        self.MRC_results.setText(txt)
        txt = '\n%s = %f m' % (self.MRC_ObjFnType.currentText(), RMSE)
        self.MRC_results.append(txt)

        # Plot result :

        self.h3_ax0.set_ydata(hp)
        self.h3_ax0.set_xdata(self.time + self.dt4xls2mpl * self.dformat)
        self.canvas.draw()

        # Store results in class attributes :

        self.A = A
        self.B = B
        self.RMSE = RMSE
        self.hrecess = hp

        # Compute Recharge :

        if os.path.exists(self.soilFilename):

            self.SOILPROFIL.load_info(self.soilFilename)

            rechg = mrc2rechg(self.time, self.water_lvl, self.A, self.B,
                              self.SOILPROFIL.zlayer, self.SOILPROFIL.Sy)

            rechg_tot = np.sum(rechg) * 1000
            dt = self.time[-1] - self.time[0]
            rechg_yrly = rechg_tot / dt * 365

            txt = '\nRecharge = %0.0f mm / y' % (rechg_yrly)
            self.MRC_results.append(txt)

        QtGui.QApplication.restoreOverrideCursor()

    def save_interp(self):  # =================================================

        print('Saving MRC interpretation...')

        wlvlFilename = self.waterLvl_data.wlvlFilename
        fileName, fileExtension = os.path.splitext(wlvlFilename)

        interpFilename = fileName + '.wif'

        if self.A is not None:
            print('No MRC interpretation to save.')
            return False

        fcontent = [['Well Name :', self.waterLvl_data.name_well],
                    ['Latitude :', self.waterLvl_data.LAT],
                    ['Longitude :', self.waterLvl_data.LON],
                    ['Altitude :', self.waterLvl_data.ALT],
                    ['Municipality :', self.waterLvl_data.municipality],
                    [],
                    ['*** MRC Parameters => dh/dt(m/d) = -A * h + B ***'],
                    [],
                    ['A (1/d) :', self.A],
                    ['B (m/d) :', self.B],
                    ['RMSE (m):', '%0.4f' % self.RMSE],
                    [],
                    ['*** Model Parameters ***'],
                    [],
                    ['Sy :', ''],
                    ['RASmax :', ''],
                    ['Cru :', ''],
                    [],
                    ['*** Observed and Predicted Water Level ***'],
                    [],
                    ['Time', 'hrcs(mbgs)', 'hobs(mbgs)', 'hpre(mbgs)']]

        for i in range(len(self.time)):
            fcontent.append([self.time[i],
                             '%0.2f' % self.hrecess[i],
                             '%0.2f' % self.water_lvl[i]])

        with open(interpFilename, 'w') as f:
            writer = csv.writer(f, delimiter='\t', lineterminator='\n')
            writer.writerows(fcontent)

        print('MRC interpretation Saved.')

        return True

    def btn_mrc2rechg_isClicked(self):  # =====================================

        if not self.A and not self.B:
            print('Need to calculate MRC equation first.')
            return

        if not os.path.exists(self.soilFilename):
            print('A ".sol" file is needed for the calculation of' +
                  ' groundwater recharge from the MRC')
            return

        self.SOILPROFIL.load_info(self.soilFilename)
        mrc2rechg(self.time, self.water_lvl, self.A, self.B,
                  self.SOILPROFIL.zlayer, self.SOILPROFIL.Sy)

    def plot_peak(self):  # ===================================================

        if len(self.peak_memory) == 1:
            self.btn_undo.setEnabled(False)
        else:
            self.btn_undo.setEnabled(True)

        if self.isGraphExists is True:

            x = self.time[self.peak_indx] + (self.dt4xls2mpl * self.dformat)
            y = self.water_lvl[self.peak_indx]
            self.h2_ax0.set_data(x, y)

            # Take a screenshot of the background :
            self.__save_figbckground__()

    def find_peak(self):  # ===================================================

        n_j, n_add = local_extrema(self.water_lvl, 4 * 5)

        # Removing first and last point if necessary to always start with a
        # maximum and end with a minimum.

        # WARNING: y axis is inverted. Consequently, the logic needs to be
        #          inverted also

        if n_j[0] > 0:
            n_j = np.delete(n_j, 0)

        if n_j[-1] < 0:
            n_j = np.delete(n_j, -1)

        self.peak_indx = np.abs(n_j).astype(int)
        self.peak_memory.append(self.peak_indx)

        self.plot_peak()

    def add_peak(self):  # ===================================================

        # slot connected when the button to add new peaks is clicked.

        if self.isGraphExists is False:
            print('Graph is empty')
            self.emit_error_message(
              '<b>Please select a valid Water Level Data File first.</b>')
            return

        if self.btn_editPeak.autoRaise():

            # Activate <add_peak> :
            self.btn_editPeak.setAutoRaise(False)

            # Deactivate <pan_graph> :
            # http://stackoverflow.com/questions/17711099
            self.btn_pan.setAutoRaise(True)
            if self.toolbar._active == "PAN":
                self.toolbar.pan()

            # Deactivate <delete_peak> :
            self.btn_delPeak.setAutoRaise(True)

            # Save background :
            self.__save_figbckground__()
        else:

            # Deactivate <add_peak> and hide guide line
            self.btn_editPeak.setAutoRaise(True)
            self.vguide.set_xdata(-1)
            self.canvas.draw()

    def delete_peak(self):  # =================================================

        if self.btn_delPeak.autoRaise():

            # Activate <delete_peak> :
            self.btn_delPeak.setAutoRaise(False)

            # Deactivate <pan_graph> :
            # http://stackoverflow.com/questions/17711099
            self.btn_pan.setAutoRaise(True)
            if self.toolbar._active == "PAN":
                self.toolbar.pan()

            # Deactivate <add_peak> and hide guide line :
            self.btn_editPeak.setAutoRaise(True)
            self.vguide.set_xdata(-1)
            self.canvas.draw()

        else:
            # Deactivate <delete_peak> :
            self.btn_delPeak.setAutoRaise(True)

    def pan_graph(self):  # ===================================================

        if self.btn_pan.autoRaise():

            # Deactivate <add_peak> and hide guide line
            self.btn_editPeak.setAutoRaise(True)
            self.vguide.set_xdata(-1)
            self.canvas.draw()

            # Deactivate <delete_peak>
            self.btn_delPeak.setAutoRaise(True)

            # Activate <pan_graph>
            self.btn_pan.setAutoRaise(False)
            self.toolbar.pan()

        else:
            self.btn_pan.setAutoRaise(True)
            self.toolbar.pan()

    def home(self):  # ========================================================

        if self.isGraphExists is False:
            print('Graph is empty')
            return

        self.toolbar.home()
        self.__save_figbckground__()

    def undo(self):  # ========================================================

        if self.isGraphExists is False:
            print('Graph is empty')
            self.emit_error_message(
                '<b>Please select a valid Water Level Data File first.</b>')
            return

        if len(self.peak_memory) > 1:
            self.peak_indx = self.peak_memory[-2]
            del self.peak_memory[-1]

            self.plot_peak()

            print('undo')
        else:
            pass

    def clear_all_peaks(self):  # =============================================

        if self.isGraphExists is False:
            print('Graph is empty')
            msg = '<b>Please select a valid Water Level Data File first.</b>'
            self.emit_error_message(msg)
            return

        self.peak_indx = np.array([]).astype(int)
        self.peak_memory.append(self.peak_indx)

        self.plot_peak()

    def setup_ax_margins(self, event):  # =====================================

        # Update axes :

        fheight = self.fig.get_figheight()
        fwidth = self.fig.get_figwidth()

        left_margin = 1. / fwidth
        right_margin = 1. / fwidth
        bottom_margin = 1. / fheight
        top_margin = 0.25 / fheight

        x0 = left_margin
        y0 = bottom_margin
        w = 1 - (left_margin + right_margin)
        h = 1 - (bottom_margin + top_margin)

        for axe in self.fig.axes:
            axe.set_position([x0, y0, w, h])

        self.__save_figbckground__()

    def switch_date_format(self):  # ==========================================

        ax0 = self.fig.axes[0]

        # Change UI and System Variable State :

        if self.dformat == 0:    # 0 for Excel numeric date format
            self.btn_dateFormat.setAutoRaise(False)
            self.dformat = 1     # 1 for Matplotlib format
            print('switching to matplotlib date format')
        elif self.dformat == 1:  # 1 for Matplotlib format
            self.btn_dateFormat.setAutoRaise(True)
            self.dformat = 0     # 0 for Excel numeric date format
            print('switching to Excel numeric date format')

        # Change xtick Labels Date Format :

        if self.dformat == 1:
            xloc = mpl.dates.AutoDateLocator()
            ax0.xaxis.set_major_locator(xloc)
            xfmt = mpl.dates.AutoDateFormatter(xloc)
            ax0.xaxis.set_major_formatter(xfmt)
        elif self.dformat == 0:
            xfmt = mpl.ticker.ScalarFormatter()
            ax0.xaxis.set_major_formatter(xfmt)
            ax0.get_xaxis().get_major_formatter().set_useOffset(False)

        # Adjust Axis Range :

        xlim = ax0.get_xlim()
        if self.dformat == 1:
            ax0.set_xlim(xlim[0] + self.dt4xls2mpl, xlim[1] + self.dt4xls2mpl)
        elif self.dformat == 0:
            ax0.set_xlim(xlim[0] - self.dt4xls2mpl, xlim[1] - self.dt4xls2mpl)

        # Adjust Water Levels, Peak and MRC Time Frame :

        t = self.time + self.dt4xls2mpl * self.dformat

        self.h1_ax0.set_xdata(t)  # Water Levels

        if len(self.hrecess) > 0:  # MRC
            self.h3_ax0.set_xdata(t)

        if len(self.peak_indx) > 0:  # Peaks
            self.h2_ax0.set_xdata(self.time[self.peak_indx] +
                                  self.dt4xls2mpl * self.dformat)

        self.canvas.draw()

    def init_hydrograph(self):  # =============================================

        ax0 = self.fig.axes[0]
#        ax0.cla()

        # --------------------------------------------------------- RESET UI --

        self.peak_indx = np.array([]).astype(int)
        self.peak_memory = [np.array([]).astype(int)]
        self.btn_undo.setEnabled(False)

        # --------------------------------------------------------- PLOTTING --

        # Water Levels :

        y = self.water_lvl
        t = self.time + self.dt4xls2mpl * self.dformat

        self.h1_ax0.set_data(t, y)

        self.plt_wlpre, = ax0.plot([], [], color='red', clip_on=True,
                                   ls='-', zorder=10, marker='None')

        # Peaks :

        self.h2_ax0, = ax0.plot([], [], color='red', clip_on=True,
                                zorder=30, marker='o', linestyle='None')

        # Cross Remove Peaks :

        self.xcross, = ax0.plot(1, 0, color='red', clip_on=True,
                                zorder=20, marker='x', linestyle='None',
                                markersize=15, markeredgewidth=3)

        # Recession :

        self.h3_ax0, = ax0.plot([], [], color='red', clip_on=True,
                                zorder=15, marker='None', linestyle='--')

        # Strati :

        if not self.btn_strati.autoRaise():
            self.display_soil_layer()

        # Setup Axis Range :

        y = self.water_lvl
        t = self.time + self.dt4xls2mpl * self.dformat

        delta = 0.05
        Xmin0 = np.min(t) - (np.max(t) - np.min(t)) * delta
        Xmax0 = np.max(t) + (np.max(t) - np.min(t)) * delta

        indx = np.where(~np.isnan(y))
        Ymin0 = np.min(y[indx]) - (np.max(y[indx]) - np.min(y[indx])) * delta
        Ymax0 = np.max(y[indx]) + (np.max(y[indx]) - np.min(y[indx])) * delta

        ax0.axis([Xmin0, Xmax0, Ymax0, Ymin0])
#        ax0.invert_yaxis()

        # Setup xtick Labels Date Format :

        if self.dformat == 1:
            xloc = mpl.dates.AutoDateLocator()
            ax0.xaxis.set_major_locator(xloc)
            xfmt = mpl.dates.AutoDateFormatter(xloc)
            ax0.xaxis.set_major_formatter(xfmt)
        elif self.dformat == 0:
            xfmt = mpl.ticker.ScalarFormatter()
            ax0.xaxis.set_major_formatter(xfmt)
            ax0.get_xaxis().get_major_formatter().set_useOffset(False)

        # Draw the Graph :

        self.isGraphExists = True
        self.canvas.draw()

    def plot_synth_hydro(self, parameters):  # ================================
        print(parameters)
        Cro = parameters['Cro']
        RASmax = parameters['RASmax']
        Sy = parameters['Sy']
#        parameters['jack']

        # compute recharge :
        rechg, _, _, _, _ = \
            self.synth_hydrograph.surf_water_budget(Cro, RASmax)

        # compute water levels :

        tweatr = self.meteo_data.TIME + 10  # Here we introduce the time lag
        twlvl = self.time

        ts = np.where(twlvl[0] == tweatr)[0][0]
        te = np.where(twlvl[-1] == tweatr)[0][0]

        WLpre = self.synth_hydrograph.calc_hydrograph(rechg[ts:te], Sy)

        # plot water levels :

        self.plt_wlpre.set_data(self.synth_hydrograph.DATE, WLpre/1000.)

        self.canvas.draw()

    def btn_strati_isClicked(self):  # ========================================

        # Checks :

        if self.isGraphExists is False:
            print('Graph is empty.')
            self.btn_strati.setAutoRaise(True)
            return

        # Attribute Action :

        if self.btn_strati.autoRaise():
            self.btn_strati.setAutoRaise(False)
            self.display_soil_layer()
        else:
            self.btn_strati.setAutoRaise(True)
            self.hide_soil_layer()

    def hide_soil_layer(self):  # =============================================

        for i in range(len(self.zlayer)):
            self.layers[i].remove()
            self.stratLines[i].remove()
        self.stratLines[i+1].remove()

        self.canvas.draw()

    def display_soil_layer(self):  # ==========================================

        # Check :

        if not os.path.exists(self.soilFilename):
            print('No ".sol" file found for this well.')
            self.btn_strati.setAutoRaise(True)
            return

        # Load soil column info :

        with open(self.soilFilename, 'r') as f:
            reader = list(csv.reader(f, delimiter="\t"))

        NLayer = len(reader)

        self.zlayer = np.empty(NLayer).astype(float)
        self.soilName = np.empty(NLayer).astype(str)
        self.Sy = np.empty(NLayer).astype(float)
        self.soilColor = np.empty(NLayer).astype(str)

        for i in range(NLayer):
            self.zlayer[i] = reader[i][0]
            self.soilName[i] = reader[i][1]
            self.Sy[i] = reader[i][2]
            try:
                self.soilColor[i] = reader[i][3]
                print(reader[i][3])
            except:
                self.soilColor[i] = '#FFFFFF'

        print(self.soilColor)

        # Plot layers and lines :

        self.layers = [0] * len(self.zlayer)
        self.stratLines = [0] * (len(self.zlayer)+1)

        up = 0
        self.stratLines[0], = self.ax0.plot([0, 99999], [up, up],
                                            color="black",
                                            linewidth=1)
        for i in range(len(self.zlayer)):

            down = self.zlayer[i]

            self.stratLines[i+1], = self.ax0.plot([0, 99999], [down, down],
                                                  color="black",
                                                  linewidth=1)
            try:
                self.layers[i] = self.ax0.fill_between(
                    [0, 99999], up, down, color=self.soilColor[i], zorder=0)
            except:
                self.layers[i] = self.ax0.fill_between(
                    [0, 99999], up, down, color='#FFFFFF', zorder=0)

            up = down

        self.canvas.draw()

    def change_waterlvl_lineStyle(self):  # ===================================

        if self.btn_Waterlvl_lineStyle.autoRaise():

            self.btn_Waterlvl_lineStyle.setAutoRaise(False)

            plt.setp(self.h1_ax0, markerfacecolor='blue', markersize=5,
                     markeredgecolor='blue', markeredgewidth=1.5,
                     linestyle='none', marker='.')

        else:

            self.btn_Waterlvl_lineStyle.setAutoRaise(True)

            plt.setp(self.h1_ax0, marker='None', linestyle='-')

        self.canvas.draw()

    def mouse_vguide(self, event):  # =========================================

        ax0 = self.fig.axes[0]
        fig = self.fig

        # http://matplotlib.org/examples/pylab_examples/cursor_demo.html
        if not self.btn_editPeak.autoRaise():
            # Trace a red vertical guide (line) that folows the mouse marker.
            x = event.xdata
            if x:
                # update the line positions
                self.vguide.set_xdata(x)
            else:
                self.vguide.set_xdata(-1)
            fig.canvas.restore_region(self.__figbckground)
            ax0.draw_artist(self.vguide)
            self.fig.canvas.update()

        elif not self.btn_delPeak.autoRaise() and len(self.peak_indx) > 0:

            # For deleting peak in the graph. Will put a cross on top of the
            # peak to delete if some proximity conditions are met.

            x = event.x
            y = event.y

            xt = np.empty(len(self.peak_indx))
            yt = np.empty(len(self.peak_indx))
            xpeak = self.time[self.peak_indx] + self.dt4xls2mpl * self.dformat
            ypeak = self.water_lvl[self.peak_indx]

            for i in range(len(self.peak_indx)):
                xt[i], yt[i] = ax0.transData.transform(
                    (xpeak[i], ypeak[i]))

            r = ((xt - x)**2 + (yt - y)**2)**0.5

            if np.min(r) < 15:  # put the cross over the nearest peak

                indx = np.where(r == np.min(r))[0][0]

                self.xcross.set_xdata(xpeak[indx])
                self.xcross.set_ydata(ypeak[indx])

                self.canvas.draw()

            else:  # hide the cross outside of the plotting area

                self.xcross.set_xdata(-1)
                self.canvas.draw()
        else:
            pass

    def onclick(self, event):  # ==============================================

        ax0 = self.fig.axes[0]

        x = event.x
        y = event.y

        if x is None or y is None:
            return

        # ---------------------------------------------------- DELETE A PEAK --

        # www.github.com/eliben/code-for-blog/blob/master/2009/qt_mpl_bars.py

        if not self.btn_delPeak.autoRaise():

            if len(self.peak_indx) == 0:
                return

            xt = np.empty(len(self.peak_indx))
            yt = np.empty(len(self.peak_indx))
            xpeak = self.time[self.peak_indx] + self.dt4xls2mpl * self.dformat
            ypeak = self.water_lvl[self.peak_indx]

            for i in range(len(self.peak_indx)):
                xt[i], yt[i] = ax0.transData.transform((xpeak[i], ypeak[i]))

            r = ((xt - x)**2 + (yt - y)**2)**0.5

            if np.min(r) < 15:

                indx = np.where(r == np.min(r))[0][0]

                # Update the plot
                self.xcross.set_xdata(xpeak[indx])
                self.xcross.set_ydata(ypeak[indx])

                # Remove peak from peak index sequence
                self.peak_indx = np.delete(self.peak_indx, indx)
                self.peak_memory.append(self.peak_indx)

                xpeak = np.delete(xpeak, indx)
                ypeak = np.delete(ypeak, indx)

                # hide the cross outside of the plotting area
                self.xcross.set_xdata(1)
                self.plot_peak()
            else:
                pass

        # ------------------------------------------------------- ADD A PEAK --

        elif not self.btn_editPeak.autoRaise():

            # print(event.xdata, event.ydata)

            xclic = event.xdata
            if xclic is None:
                return

            # http://matplotlib.org/examples/pylab_examples/cursor_demo.html

            x = self.time + self.dt4xls2mpl * self.dformat
            y = self.water_lvl

            indxmin = np.where(x < xclic)[0]
            indxmax = np.where(x > xclic)[0]
            if len(indxmax) == 0:

                # Marker is outside the water level time series, to the right.
                # The last data point is added to "peak_indx".

                self.peak_indx = np.append(self.peak_indx, len(x)-1)
                self.peak_memory.append(self.peak_indx)

            elif len(indxmin) == 0:

                # Marker is outside the water level time series, to the left.
                # The first data point is added to "peak_indx".

                self.peak_indx = np.append(self.peak_indx, 0)
                self.peak_memory.append(self.peak_indx)

            else:

                # Marker is between two data point. The closest data point to
                # the marker is then selected.

                indxmin = indxmin[-1]
                indxmax = indxmax[0]

                dleft = xclic - x[indxmin]
                dright = x[indxmax] - xclic

                if dleft < dright:

                    self.peak_indx = np.append(self.peak_indx, indxmin)
                    self.peak_memory.append(self.peak_indx)

                else:

                    self.peak_indx = np.append(self.peak_indx, indxmax)
                    self.peak_memory.append(self.peak_indx)

            self.plot_peak()


def local_extrema(x, Deltan):  # ==============================================
    """
    Code adapted from a MATLAB script at
    www.ictp.acad.ro/vamos/trend/local_extrema.htm

    LOCAL_EXTREMA Determines the local extrema of a given temporal scale.

    ---- OUTPUT ----

    n_j = The positions of the local extrema of a partition of scale Deltan
          as defined at p. 82 in the book [ATE] C. Vamos and M. Craciun,
          Automatic Trend Estimation, Springer 2012.
          The positions of the maxima are positive and those of the minima
          are negative.

    kadd = n_j(kadd) are the local extrema with time scale smaller than Deltan
           which are added to the partition such that an alternation of maxima
           and minima is obtained.
    """

    N = len(x)

    ni = 0
    nf = N - 1

    # ------------------------------------------------------------ PLATEAU ----

    # Recognize the plateaus of the time series x defined in [ATE] p. 85
    # [n1[n], n2[n]] is the interval with the constant value equal with x[n]
    # if x[n] is not contained in a plateau, then n1[n] = n2[n] = n
    #
    # Example with a plateau between indices 5 and 8:
    #  x = [1, 2, 3, 4, 5, 6, 6, 6, 6, 7, 8,  9, 10, 11, 12]
    # n1 = [0, 1, 2, 3, 4, 5, 5, 5, 5, 9, 10, 11, 12, 13, 14]
    # n2 = [0, 1, 2, 3, 4, 8, 8, 8, 8, 9, 10, 11, 12, 13, 14]

    n1 = np.arange(N)
    n2 = np.arange(N)

    dx = np.diff(x)
    if np.any(dx == 0):
        print('At least 1 plateau has been detected in the data')
        for i in range(N-1):
            if x[i+1] == x[i]:
                n1[i+1] = n1[i]
                n2[n1[i+1]:i+1] = i+1

    # ------------------------------------------------------ MAIN FUNCTION ----

    # the iterative algorithm presented in Appendix E of [ATE]

    nc = 0    # the time step up to which the time series has been
              # analyzed ([ATE] p. 127)
    Jest = 0  # number of local extrema of the partition of scale DeltaN
    iadd = 0  # number of additional local extrema
    flagante = 0
    kadd = []  # order number of the additional local extrema between all the
               # local extrema
    n_j = []   # positions of the local extrema of a partition of scale Deltan

    while nc < nf:

        # the next extremum is searched within the interval [nc, nlim]

        nlim = min(nc + Deltan, nf)

        # ------------------------------------------------- SEARCH FOR MIN ----

        xmin = np.min(x[nc:nlim+1])
        nmin = np.where(x[nc:nlim+1] == xmin)[0][0] + nc

        nlim1 = max(n1[nmin] - Deltan, ni)
        nlim2 = min(n2[nmin] + Deltan, nf)

        xminn = np.min(x[nlim1:nlim2+1])
        nminn = np.where(x[nlim1:nlim2+1] == xminn)[0][0] + nlim1

        # if flagmin = 1 then the minimum at nmin satisfies condition (6.1)
        if nminn == nmin:
            flagmin = 1
        else:
            flagmin = 0

        # --------------------------------------------------- SEARCH FOR MAX --

        xmax = np.max(x[nc:nlim+1])
        nmax = np.where(x[nc:nlim+1] == xmax)[0][0] + nc

        nlim1 = max(n1[nmax] - Deltan, ni)
        nlim2 = min(n2[nmax] + Deltan, nf)

        xmaxx = np.max(x[nlim1:nlim2+1])
        nmaxx = np.where(x[nlim1:nlim2+1] == xmaxx)[0][0] + nlim1

        # If flagmax = 1 then the maximum at nmax satisfies condition (6.1)
        if nmaxx == nmax:
            flagmax = 1
        else:
            flagmax = 0

        # ------------------------------------------------------- MIN or MAX --

        # The extremum closest to nc is kept for analysis
        if flagmin == 1 and flagmax == 1:
            if nmin < nmax:
                flagmax = 0
            else:
                flagmin = 0

        # ---------------------------------------------- ANTERIOR EXTREMUM ----

        if flagante == 0:  # No ANTERIOR extremum

            if flagmax == 1:  # CURRENT extremum is a MAXIMUM

                nc = n1[nmax] + 1
                flagante = 1
                n_j = np.append(n_j, np.floor((n1[nmax] + n2[nmax]) / 2.))
                Jest += 1

            elif flagmin == 1:  # CURRENT extremum is a MINIMUM

                nc = n1[nmin] + 1
                flagante = -1
                n_j = np.append(n_j, -np.floor((n1[nmin] + n2[nmin]) / 2.))
                Jest += 1

            else:  # No extremum

                nc = nc + Deltan

        elif flagante == -1:  # ANTERIOR extremum is an MINIMUM

            tminante = np.abs(n_j[-1])
            xminante = x[tminante]

            if flagmax == 1:  # CURRENT extremum is a MAXIMUM

                if xminante < xmax:

                    nc = n1[nmax] + 1
                    flagante = 1
                    n_j = np.append(n_j, np.floor((n1[nmax] + n2[nmax]) / 2.))
                    Jest += 1

                else:

                    # CURRENT MAXIMUM is smaller than the ANTERIOR MINIMUM
                    # an additional maximum is added ([ATE] p. 82 and 83)

                    xmaxx = np.max(x[tminante:nmax+1])
                    nmaxx = np.where(x[tminante:nmax+1] == xmaxx)[0][0]
                    nmaxx += tminante

                    nc = n1[nmaxx] + 1
                    flagante = 1
                    n_j = np.append(n_j, np.floor((n1[nmaxx] + n2[nmaxx]) / 2.))
                    Jest += 1

                    kadd = np.append(kadd, Jest-1)
                    iadd += 1

            elif flagmin == 1: # CURRENT extremum is also a MINIMUM
                               # an additional maximum is added ([ATE] p. 82)

                nc = n1[nmin]
                flagante = 1

                xmax = np.max(x[tminante:nc+1])
                nmax = np.where(x[tminante:nc+1] == xmax)[0][0] + tminante

                n_j = np.append(n_j, np.floor((n1[nmax] + n2[nmax]) / 2.))
                Jest += 1

                kadd = np.append(kadd, Jest-1)
                iadd += 1

            else:
                nc = nc + Deltan

        else:  # ANTERIOR extremum is a MAXIMUM

            tmaxante = np.abs(n_j[-1])
            xmaxante = x[tmaxante]

            if flagmin == 1:  # CURRENT extremum is a MINIMUM

                if xmaxante > xmin:

                    nc = n1[nmin] + 1
                    flagante = -1

                    n_j = np.append(n_j, -np.floor((n1[nmin] + n2[nmin]) / 2.))
                    Jest += 1

                else:
                    # CURRENT MINIMUM is larger than the ANTERIOR MAXIMUM:
                    # an additional minimum is added ([ATE] p. 82 and 83)

                    xminn = np.min(x[tmaxante:nmin+1])
                    nminn = np.where(x[tmaxante:nmin+1] == xminn)[0][0]
                    nminn += tmaxante

                    nc = n1[nminn] + 1
                    flagante = -1

                    n_j = np.append(n_j, -np.floor((n1[nminn] + n2[nminn]) / 2.))
                    Jest = Jest + 1

                    kadd = np.append(kadd, Jest-1)
                    iadd += 1

            elif flagmax == 1: # CURRENT extremum is also an MAXIMUM:
                               # an additional minimum is added ([ATE] p. 82)
                nc = n1[nmax]
                flagante = -1

                xmin = np.min(x[tmaxante:nc+1])
                nmin = np.where(x[tmaxante:nc+1] == xmin)[0]
                nmin += tmaxante

                n_j = np.append(n_j, -np.floor((n1[nmin] + n2[nmin]) / 2.))
                Jest += 1

                kadd = np.append(kadd, Jest-1)
                iadd += 1

            else:
                nc = nc + Deltan

#    # x(ni) is not included in the partition of scale Deltan
#    nj1 = np.abs(n_j[0])
#    if nj1 > ni:
#        if n1[nj1] > ni: # the boundary ni is not included in the plateau
#                         # containing the first local extremum at n_j[1] and it
#                         # is added as an additional local extremum ([ATE] p. 83)
#            n_j = np.hstack((-np.sign(n_j[0]) * ni, n_j))
#            Jest += 1
#
#            kadd = np.hstack((0, kadd + 1))
#            iadd += 1
#
#        else: # the boundary ni is included in the plateau containing
#              # the first local extremum at n_j(1) and then the first local
#              # extremum is moved at the boundary of the plateau
#            n_j[0] = np.sign(n_j[0]) * ni


#    # the same situation as before but for the other boundary nf
#    njJ = np.abs(n_j[Jest])
#    if njJ < nf:
#        if n2[njJ] < nf:
#            n_j = np.append(n_j, -np.sign(n_j[Jest]) * nf)
#            Jest += 1
#
#            kadd = np.append(kadd, Jest)
#            iadd += 1
#        else:
#            n_j[Jest] = np.sign(n_j[Jest]) * nf

    return n_j, kadd


##==============================================================================
#def xls2mpl(time):
#
#    """
#    Create a date series readable by mpl from a numeric time series (time).
#    """
#
#    mpldate = [0] * len(time)
#    for i, t in enumerate(time):
#
#        d = xldate_as_tuple(t, 0)
#        mpldate[i] = datetime.datetime(d[0], d[1], d[2], 0)
#
#    return mpldate
#
#def mpl2xls(date):
#    """
#    Create a numeric time series readable by excell from a matplotlib
#    date series.
#    """
#    time = mpl.dates.date2num(date)

#==============================================================================
def mrc_calc(t, h, ipeak, MRCTYPE=1):
    """
    Calculate the equation parameters of the Master Recession Curve (MRC) of
    the aquifer from the water level time series using a modified Gauss-Newton
    optimization method.

    INPUTS
    ------
    h : water level time series in mbgs
    t : time in days
    ipeak: sequence of indices where the maxima and minima are located in h

    MRCTYPE: MRC equation type

             MODE = 0 -> linear (dh/dt = b)
             MODE = 1 -> exponential (dh/dt = -a*h + b)

    """
#==============================================================================

    A, B, hp, RMSE = None, None, None, None

    #---------------------------------------------------------- Check MinMax --

    if len(ipeak) == 0:
        print('No extremum selected')
        return A, B, hp, RMSE

    ipeak = np.sort(ipeak)
    maxpeak = ipeak[:-1:2]
    minpeak = ipeak[1::2]
    dpeak = (h[maxpeak] - h[minpeak]) * -1 # WARNING: Don't forget it is mbgs

    if np.any(dpeak < 0):
        print('There is a problem with the pair-ditribution of min-max')
        return A, B, hp, RMSE

    #---------------------------------------------------------- Optimization --

    print('\n---- MRC calculation started ----\n')
    print('MRCTYPE = %s\n' % (['Linear', 'Exponential'][MRCTYPE]))

    tstart = clock()

    # If MRCTYPE is 0, then the parameter A is kept to a value of 0 throughout
    # the entire optimization process and only paramter B is optimized.

    dt = np.diff(t)
    tolmax = 0.001

    A = 0.
    B = np.mean((h[maxpeak] - h[minpeak]) / (t[maxpeak] - t[minpeak]))

    hp = calc_synth_hydrograph(A, B, h, dt, ipeak)
    tindx = np.where(~np.isnan(hp))

    RMSE = (np.mean((h[tindx] - hp[tindx])**2))**0.5
    print('A = %0.3f ; B= %0.3f; RMSE = %f' % (A, B, RMSE))

    # NP: number of parameters
    if MRCTYPE == 0:
        NP = 1
    elif MRCTYPE ==1:
        NP = 2

    while 1:

        # ---- Calculating Jacobian (X) Numerically ----

        hdB = calc_synth_hydrograph(A, B + tolmax, h, dt, ipeak)
        XB = (hdB[tindx] - hp[tindx]) / tolmax

        if MRCTYPE == 1:
            hdA = calc_synth_hydrograph(A + tolmax, B, h, dt, ipeak)
            XA = (hdA[tindx] - hp[tindx]) / tolmax

            Xt  = np.vstack((XA, XB))
        elif MRCTYPE == 0:
            Xt = XB

        X = Xt.transpose()

        #---- Solving Linear System ----

        dh = h[tindx] - hp[tindx]
        XtX = np.dot(Xt, X)
        Xtdh = np.dot(Xt, dh)

        #---- Scaling ----

        C = np.dot(Xt, X) * np.identity(NP)
        for j in range(NP):
            C[j, j] = C[j, j] ** -0.5

        Ct = C.transpose()
        Cinv = np.linalg.inv(C)

        #---- Constructing right hand side ----

        CtXtdh = np.dot(Ct, Xtdh)

        #---- Constructing left hand side ----

        CtXtX = np.dot(Ct, XtX)
        CtXtXC = np.dot(CtXtX, C)

        m = 0
        while 1: # loop for the Marquardt parameter (m)

            #---- Constructing left hand side (continued) ----

            CtXtXCImr = CtXtXC + np.identity(NP) * m
            CtXtXCImrCinv = np.dot(CtXtXCImr, Cinv)

            #---- Calculating parameter change vector ----

            dr = np.linalg.tensorsolve(CtXtXCImrCinv, CtXtdh, axes=None)

            #---- Checking Marquardt condition ----

            NUM = np.dot(dr.transpose(), CtXtdh)
            DEN1 = np.dot(dr.transpose(), dr)
            DEN2 = np.dot(CtXtdh.transpose(), CtXtdh)

            cos = NUM / (DEN1 * DEN2)**0.5
            if np.abs(cos) < 0.08:
                m = 1.5 * m + 0.001
            else:
                break

        #---- Storing old parameter values ----

        Aold = np.copy(A)
        Bold = np.copy(B)
        RMSEold = np.copy(RMSE)

        while 1: # Loop for Damping (to prevent overshoot)

            #---- Calculating new paramter values ----

            if MRCTYPE == 1:
                A = Aold + dr[0]
                B = Bold + dr[1]
            elif MRCTYPE == 0:
                B = Bold + dr[0, 0]

            #---- Applying parameter bound-constraints ----

            A = np.max((A, 0)) # lower bound

            #---- Solving for new parameter values ----

            hp = calc_synth_hydrograph(A, B, h, dt, ipeak)
            RMSE = (np.mean((h[tindx] - hp[tindx])**2))**0.5

            #---- Checking overshoot ----

            if (RMSE - RMSEold) > 0.001:
                dr = dr * 0.5
            else:
                break

#        print(u'A = %0.3f ; B= %0.3f; RMSE = %f ; Cos_theta = %0.3f'
#              % (A, B, RMSE, cos))

        #---- Checking tolerance ----

        tolA = np.abs(A - Aold)
        tolB = np.abs(B - Bold)

        tol = np.max((tolA, tolB))

        if tol < tolmax:
            break

    tend = clock()
    print('\nTIME = %0.3f sec' % (tend-tstart))
    print('\n---- FIN ----\n')

    return A, B, hp, RMSE


def calc_synth_hydrograph(A, B, h, dt, ipeak):
    """
    Compute synthetic hydrograph with a time-forward implicit numerical scheme
    during periods where the water level recedes identified by the "ipeak"
    pointers.

    This is documented in logbook#10 p.79-80, 106.
    """

    maxpeak = ipeak[:-1:2]  # Time indexes delimiting period where water level
    minpeak = ipeak[1::2]   # recedes.

    nsegmnt = len(minpeak)  # Number of segments of the time series that were
                            # identified as period where the water level
                            # recedes.

    hp = np.ones(len(h)) * np.nan

    for i in range(nsegmnt):
        hp[maxpeak[i]] = h[maxpeak[i]]

        for j in range(minpeak[i] - maxpeak[i]):

            imax = maxpeak[i]

            LUMP1 = (1 - A * dt[imax+j] / 2)
            LUMP2 = B * dt[imax+j]
            LUMP3 = (1 + A * dt[imax+j] / 2) ** -1

            hp[imax+j+1] = (LUMP1 * hp[imax+j] + LUMP2) * LUMP3

    return hp

#==============================================================================
class SoilProfil():
    """
    zlayer = Position of the layer boundaries in mbgs where 0 is the ground
             surface. There is one more element in zlayer than the total number
             of layer.

    soilName = Soil texture description.

    Sy = Soil specific yield.
    """
#==============================================================================

    def __init__(self):

        self.zlayer = []
        self.soilName = []
        self.Sy = []
        self.color = []

    def load_info(self, filename):

        #---- load soil column info ----

        with open(filename,'r') as f:
            reader = list(csv.reader(f, delimiter="\t"))

        NLayer = len(reader)

        self.zlayer = np.empty(NLayer+1).astype(float)
        self.soilName = np.empty(NLayer).astype(str)
        self.Sy = np.empty(NLayer).astype(float)
        self.color = np.empty(NLayer).astype(str)

        self.zlayer[0] = 0
        for i in range(NLayer):
            self.zlayer[i+1] = reader[i][0]
            self.soilName[i] = reader[i][1]
            self.Sy[i] = reader[i][2]
            try:
                self.color[i] = reader[i][3]
            except:
                self.color[i] = '#FFFFFF'


#===============================================================================
def mrc2rechg(t, ho, A, B, z, Sy):
    """
    Calculate groundwater recharge from the Master Recession Curve (MRC)
    equation defined by the parameters A and B, the water level time series
    in mbgs (t and ho) and the soil column description (z and Sy), using
    the water-level fluctuation principle.

    INPUTS
    ------
    {1D array} t : Time in days
    {1D array} ho = Observed water level in mbgs
    {float}    A = Model parameter of the MRC
    {float}    B = Model parameter of the MRC
    {1D array} z = Depth of the soil layer limits
    {1D array} Sy = Specific yield for each soil layer
    {1D array} indx = Time index defining the periods over which recharge
                      is to be computed. Odd index numbers are for the
                      beginning of periods while even index numbers are for
                      the end of periods.

    OUTPUTS
    -------
    {1D array} RECHG = Groundwater recharge time series in m

    Note: This is documented in logbook #11, p.23.
    """

    print(z)
    print(Sy)

    #---- Check Data Integrity ----

    if np.min(ho) < 0:
        print('Water level rise above ground surface. Please check your data.')
        return

    dz = np.diff(z)  # Tickness of soil layer
    print(dz)

    dt = np.diff(t)
    RECHG = np.zeros(len(dt))

    # !Do not forget it is mbgs. Everything is upside down!

    for i in range(len(dt)):

        # Calculate projected water level at i+1

        LUMP1 = 1 - A * dt[i] / 2
        LUMP2 = B * dt[i]
        LUMP3 = (1 + A * dt[i] / 2) ** -1

        hp = (LUMP1 * ho[i] + LUMP2) * LUMP3

        # Calculate resulting recharge over dt (See logbook #11, p.23)

        hup = min(hp, ho[i+1])
        hlo = max(hp, ho[i+1])

        iup = np.where(hup >= z)[0][-1]
        ilo = np.where(hlo >= z)[0][-1]

        RECHG[i] = np.sum(dz[iup:ilo+1] * Sy[iup:ilo+1])
        RECHG[i] -= (z[ilo+1] - hlo) * Sy[ilo]
        RECHG[i] -= (hup - z[iup]) * Sy[iup]

        RECHG[i] *= np.sign(hp - ho[i+1])

        # RECHG[i] will be positive in most cases. In theory, it should always
        # be positive, but error in the MRC and noise in the data can cause hp
        # to be above ho in some cases.

    print("Recharge = %0.2f m" % np.sum(RECHG))

    return RECHG

#==============================================================================

class SynthHydroWidg(QtGui.QWidget):            # Synthetic Hydrograph Widget #

#==============================================================================

    newHydroParaSent = QtCore.Signal(dict)

    def __init__(self, parent=None): #================================= Init ==
        super(SynthHydroWidg, self).__init__(parent)

        self.initUI()

    def initUI(self): #============================================= Init UI ==
#        self.QSy_max = MyQDSpin(0.005, 0.005, 0.95)


        class HSep(QtGui.QFrame): # horizontal separators for the toolbar
            def __init__(self, parent=None):
                super(HSep, self).__init__(parent)
                self.setFrameStyle(db.styleUI().HLine)

        class MyQDSpin(QtGui.QDoubleSpinBox):
            def __init__(self, step, min, max, dec, val,
                         suffix=None, parent=None):
                super(MyQDSpin, self).__init__(parent)

                self.setSingleStep(step)
                self.setMinimum(min)
                self.setMaximum(max)
                self.setDecimals(dec)
                self.setValue(val)
                self.setAlignment(QtCore.Qt.AlignCenter)
                if suffix:
                    self.setSuffix(' %s' % suffix)
                if parent:
                    self.valueChanged.connect(parent.param_changed)

        self.QSy = MyQDSpin(0.001, 0.005, 0.95, 3, 0.2, parent=self)
        self.QRAS = MyQDSpin(1, 0, 1000, 0, 100, 'mm', parent=self)
        self.CRO = MyQDSpin(0.001, 0, 1, 3, 0.3, parent=self)

        self.Tcrit = MyQDSpin(0.1, -25, 25, 1, 0, u'°C', parent=self)
        self.Tmelt = MyQDSpin(0.1, -25, 25, 1, 0, u'°C', parent=self)
        self.CM = MyQDSpin(0.1, 0, 100, 1, 2.7,u'mm/°C', parent=self)

        main_grid = QtGui.QGridLayout()

        items = [QtGui.QLabel('Sy:'), self.QSy,
                 QtGui.QLabel('Rasmax:'), self.QRAS,
                 QtGui.QLabel('Cro:'), self.CRO,
                 QtGui.QLabel('Tcrit:'), self.Tcrit,
                 QtGui.QLabel('Tmelt:'), self.Tmelt,
                 QtGui.QLabel('CM:'), self.CM]

        for col, item in enumerate(items):
            main_grid.addWidget(item, 1, col)
#        main_grid.addWidget(HSep(), 0, 0, 1, col+1)

        main_grid.setColumnStretch(col+1, 100)
        main_grid.setContentsMargins(0, 0, 0, 0)

        self.setLayout(main_grid)

    def get_parameters(self): #======================== Get Parameter Values ==
        parameters = {'Sy': self.QSy.value(),
                      'RASmax': self.QRAS.value(),
                      'Cro': self.CRO.value()}

        return parameters

    def param_changed(self): # =========================== Parameter Changed ==
        self.newHydroParaSent.emit(self.get_parameters())


    def toggleOnOff(self): # ====================== Toggle Visibility On/Off ==
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.newHydroParaSent.emit(self.get_parameters())


###############################################################################


class RechgSetupWin(QtGui.QWidget):                   # Recharge Setup Window #

    def __init__(self, parent=None):  # =============================== Init ==
        super(RechgSetupWin, self).__init__(parent)

        self.setWindowTitle('Recharge Calibration Setup')
        self.setWindowFlags(QtCore.Qt.Window)

        self.initUI()

    def initUI(self):  # =========================================== Init UI ==

        class QRowLayout(QtGui.QWidget):
            def __init__(self, items, parent=None):
                super(QRowLayout, self).__init__(parent)

                layout = QtGui.QGridLayout()
                for col, item in enumerate(items):
                    layout.addWidget(item, 0, col)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setColumnStretch(0, 100)
                self.setLayout(layout)

        class MyQDSpin(QtGui.QDoubleSpinBox):
            def __init__(self, step, min, max, suffix=None, parent=None):
                super(MyQDSpin, self).__init__(parent)

                self.setSingleStep(step)
                self.setMinimum(min)
                self.setMaximum(max)
                self.setAlignment(QtCore.Qt.AlignCenter)
                if suffix:
                    self.setSuffix(' %s' % suffix)

        class HSep(QtGui.QFrame): # vertical separators for the toolbar
            def __init__(self, parent=None):
                super(HSep, self).__init__(parent)
                self.setFrameStyle(db.styleUI().HLine)

        #----------------------------------------------------------- Toolbar --

        toolbar_widget = QtGui.QWidget()

        btn_calib = QtGui.QPushButton('Calibrate')
        btn_calib.clicked.connect(self.btn_calibrate_isClicked)

        btn_cancel = QtGui.QPushButton('Cancel')
        btn_cancel.clicked.connect(self.close)

        toolbar_layout = QtGui.QGridLayout()

        toolbar_layout.addWidget(btn_calib, 0, 0)
        toolbar_layout.addWidget(btn_cancel, 0, 1)

        toolbar_layout.setColumnStretch(2, 100)
        toolbar_layout.setContentsMargins(0, 15, 0, 0) # (L, T, R, B)

        toolbar_widget.setLayout(toolbar_layout)

        #-------------------------------------------------------- Parameters --

        self.QSy_max = MyQDSpin(0.005, 0.005, 0.95)
        self.QSy_min = MyQDSpin(0.005, 0.005, 0.95)

        self.QRAS_max = MyQDSpin(1, 0, 1000, 'mm')
        self.QRAS_min = MyQDSpin(1, 0, 1000, 'mm')

        self.CRO_max = MyQDSpin(0.01, 0, 1)
        self.CRO_min = MyQDSpin(0.01, 0, 1)

        self.Tcrit = MyQDSpin(0.1, -25, 25, u'°C')
        self.Tmelt = MyQDSpin(0.1, -25, 25, u'°C')
        self.CM = MyQDSpin(0.1, 0, 100, u'mm/°C')

        QTitle = QtGui.QLabel('Calibration Range')
        QTitle.setAlignment(QtCore.Qt.AlignCenter)

        self.btn_calibrate = QtGui.QPushButton('Calibrate')

        mainLayout = QtGui.QGridLayout()

        row = 0
        mainLayout.addWidget(QtGui.QLabel('Parameter'), row, 0)
        mainLayout.addWidget(QTitle, row, 2, 1, 3)
        row += 1
        mainLayout.addWidget(HSep(), row, 0, 1, 5)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('Sy :'), row, 0)
        mainLayout.addWidget(self.QSy_min, row, 2)
        mainLayout.addWidget(QtGui.QLabel('to'), row, 3)
        mainLayout.addWidget(self.QSy_max, row, 4)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('RASmax :'), row, 0)
        mainLayout.addWidget(self.QRAS_min, row, 2)
        mainLayout.addWidget(QtGui.QLabel('to'), row, 3)
        mainLayout.addWidget(self.QRAS_max, row, 4)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('Cro :'), row, 0)
        mainLayout.addWidget(self.CRO_min, row, 2)
        mainLayout.addWidget(QtGui.QLabel('to'), row, 3)
        mainLayout.addWidget(self.CRO_max, row, 4)
        row += 1
        mainLayout.addWidget(HSep(), row, 0, 1, 5)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('Tcrit :'), row, 0)
        mainLayout.addWidget(self.Tcrit, row, 2)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('Tmelt :'), row, 0)
        mainLayout.addWidget(self.Tmelt, row, 2)
        row += 1
        mainLayout.addWidget(QtGui.QLabel('Tmelt :'), row, 0)
        mainLayout.addWidget(self.CM, row, 2)
        row += 1
        mainLayout.addWidget(toolbar_widget, row, 0, 1, 5)

        self.setLayout(mainLayout)

    def closeEvent(self, event):  # ===========================================
        super(RechgSetupWin, self).closeEvent(event)
        print('Closing Window')

    def btn_calibrate_isClicked(self):  # ======================== Calibrate ==
        print('Calibration started')

    def show(self):  # ========================================================

        self.activateWindow()
        self.raise_()

        qr = self.frameGeometry()
        if self.parentWidget():
            parent = self.parentWidget()

            wp = parent.frameGeometry().width()
            hp = parent.frameGeometry().height()
            cp = parent.mapToGlobal(QtCore.QPoint(wp/2., hp/2.))
        else:
            cp = QtGui.QDesktopWidget().availableGeometry().center()

        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.setFixedSize(self.size())

        super(RechgSetupWin, self).show()


if __name__ == '__main__':

    app = QtGui.QApplication(argv)

    # Create and show widgets :

    w = WLCalc()
    w.show()
    w.widget_MRCparam.show()

    # Define paths :

    dirname = os.path.join(
        os.path.dirname(os.getcwd()), 'Projects', 'Pont-Rouge')
    fmeteo = os.path.join(
        dirname, 'Meteo', 'Output', 'STE CHRISTINE (7017000)_1960-2015.out')
    fwaterlvl = os.path.join(dirname, 'Water Levels', '5080001.xls')

    # Load and plot data :

    w.load_waterLvl_data(fwaterlvl)
    w.load_weather_data(fmeteo)

    # Calcul recharge :

#    w.synth_hydrograph.load_data(fmeteo, fwaterlvl)

    app.exec_()
