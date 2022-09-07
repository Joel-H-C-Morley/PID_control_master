import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog

import pyqtgraph as pg
import nidaqmx
#from pyqtgraph import PlotWidget
import numpy as np

from TLPM import TLPM
from ctypes import cdll, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_double, sizeof, c_voidp

Ui_Power_monitor, baseClass = uic.loadUiType('power_monitor.ui')

class PowerMonitor(baseClass):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ui = Ui_Power_monitor()
        self.ui.setupUi(self)
        self.show()

        # Connect to power meter
        resourceName = create_string_buffer(1024)
        self.tlPM = TLPM()
        deviceCount = c_uint32()
        self.tlPM.findRsrc(byref(deviceCount))
        self.tlPM.getRsrcName(c_int(0), resourceName)
        print(c_char_p(resourceName.raw).value)
        self.tlPM.open(resourceName, c_bool(True), c_bool(True))

        # Connect to DAQ board
        self.task = nidaqmx.Task()
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao1",'mychannel',0,1)
        self.task.start()
        print("--NI DAQ connected--")

        # Setup GUI signals
        self.settings = qtc.QSettings('Qt_apps','Power_monitor')
        self.ui.close_button.clicked.connect(self.close_gui)
        self.setpoint = self.ui.sp_doubleSpinBox.value()
        self.ui.sp_doubleSpinBox.valueChanged.connect(self.write_power)
        self.ui.start_button.clicked.connect(self.start_timer)
        self.ui.stop_button.clicked.connect(self.stop_timer)
        self.ui.save_button.clicked.connect(self.save_data)
        self.ui.load_button.clicked.connect(self.load_data)
        self.ui.dt_SpinBox.setProperty("value", self.settings.value('dt'))
        self.ui.win_SpinBox.setProperty("value", self.settings.value('win'))
        self.dt = self.ui.dt_SpinBox.value()
        self.win = self.ui.win_SpinBox.value()
        self.ui.dt_SpinBox.valueChanged.connect(self.start_timer)
        self.ui.inf_checkBox.stateChanged.connect(self.start_timer)

        self.ui.graphwidget.setBackground('w')
        styles = {'color':'r', 'font-size':'20px'}
        self.ui.graphwidget.setLabel('left', 'Power (mW)', **styles)
        self.ui.graphwidget.setLabel('bottom', '', **styles)
        pen = pg.mkPen(color=(0, 0, 255), width = 2)
        self.x = list(np.zeros(self.win))
        self.y = list(np.zeros(self.win))
        self.data_line = self.ui.graphwidget.plot(self.x, self.y, pen=pen)
        self.show()

        self.Calib = 2.27

    def start_timer(self):
        self.dt = self.ui.dt_SpinBox.value()
        self._bufsize = int(self.win)
        self.timer = qtc.QTimer()
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start(self.dt)
 
    def stop_timer(self):
        self.timer.stop()

    def write_power(self, pow_in):
        v_output = 2.27*pow_in
        self.task.write(v_output)

    def readTLPM(self):
        #Read Value from DAQ device
        power_c =  c_double()
        self.tlPM.measPower(byref(power_c))
        Power = power_c.value
        return (float(Power))

    def update_plot_data(self):
        pow = self.readTLPM()
        self.win = self.ui.win_SpinBox.value()
        diff = self.win-len(self.x)
        if self.ui.inf_checkBox.isChecked() == True:
            self.x.append(self.x[-1] + 1)  # Add a new value 1 higher than the last.
            self.y.append(pow)  # Add a new power value.
        else:
            if diff == 0:
                self.x = self.x[1:]  # Remove the first y element.
                self.x.append(self.x[-1] + 1)  # Add a new value 1 higher than the last.
                self.y = self.y[1:]  # Remove the first
                self.y.append(pow)  # Add a new power value.
            elif diff > 0:
                #self.x = self.x[1:]  # Remove the first y element.
                self.x.append(self.x[-1] + 1)  # Add a new value 1 higher than the last.
                #self.y = self.y[1:]  # Remove the first
                self.y.append(pow)  # Add a new power value.
            elif diff < 0:
                self.x = self.x[2:]  # Remove the first y element.
                self.x.append(self.x[-1] + 1)  # Add a new value 1 higher than the last.
                self.y = self.y[2:]  # Remove the first
                self.y.append(pow)  # Add a new power value.
        self.data_line.setData(self.x, self.y)  # Update the data. 

    def save_data(self):
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ =QFileDialog.getSaveFileName(self,"Save File Window Title","PowerLog.txt","All Files (*)",options=option)
        file = open(filename,'w')
        #file.write(np.array2string(np.column_stack([self.x,self.y])))
        np.savetxt(file,np.column_stack([self.x,self.y]))
        file.close()

    def load_data(self):
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self,"Load File Window Title","","Text Files (*.txt)",options=option)
        #file = open(filename,'r')
        #print(file.read())
        #file.close()
        array = np.loadtxt(filename,dtype=float)
        self.x=array[:,0]
        self.y=array[:,1]
        self.data_line.setData(self.x, self.y)  # Update the data.

    def close_gui(self):
        self.settings.setValue('dt',self.ui.dt_SpinBox.value())
        self.settings.setValue('win',self.ui.win_SpinBox.value())
        self.tlPM.close()
       # try:
         #   timer
        #except NameError:
         #   pass
        #else:
       #     self.timer.stop()
        sys.exit(app.exec_())

if __name__ == '__main__':
    app = qtw.QApplication(sys.argv)
    w = PowerMonitor()
    sys.exit(app.exec_())