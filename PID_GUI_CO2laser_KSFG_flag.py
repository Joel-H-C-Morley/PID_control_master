import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
#from PyQt5 import QtGui as qtg
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
#from qtc import QThread

import pyqtgraph as pg
#from pyqtgraph import PlotWidget
import numpy as np
#from random import randint
import nidaqmx

from time import perf_counter
import pyvisa
from TLPM import TLPM
from ctypes import cdll, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_double, sizeof, c_voidp

Ui_Power_control, baseClass = uic.loadUiType('mainwindow_FG.ui')

class MainWindow(baseClass):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Connect to power meter
        resourceName = create_string_buffer(1024)
        self.tlPM = TLPM()
        deviceCount = c_uint32()
        self.tlPM.findRsrc(byref(deviceCount))
        self.tlPM.getRsrcName(c_int(0), resourceName)
        PM_label = "PowerMeter - "
        PM_label2 = str(c_char_p(resourceName.raw).value)
        PM_l = PM_label+PM_label2
        print(PM_l)
        self.tlPM.open(resourceName, c_bool(True), c_bool(True))
        
        # Connect to DAQ board
        self.task = nidaqmx.Task()
        self.task.ai_channels.add_ai_voltage_chan("Dev1/ai2")
        self.task.start()
        print('-NI DAQ connected--')

        # Connect to Keysight Function Generator
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource('TCPIP0::A-33521B-00505::inst0::INSTR')
        if self.inst.resource_name.startswith('ASRL') or self.inst.resource_name.endswith('SOCKET'):  
            self.inst.read_termination = '\n'# For Serial and TCP/IP socket connections enable the read Termination Character, or read's will timeout
        self.inst.write('FUNction SQU')
        self.inst.write('FUNc:SQU:DCYC +1')
        self.inst.write('FREQ +5E+3')
        self.inst.write('VOLT:HIGH +5')
        self.inst.write('VOLT:LOW +0')
        self.inst.write('OUTP 1')

        self.timer = qtc.QTimer()
        self.timer2 = qtc.QTimer()
        self.clock = np.zeros(2)
        self.counter = np.zeros(2)
        self.Error = np.zeros(2)
        self.Int = np.zeros(2)

        # Setup GUI
        self.ui = Ui_Power_control()
        self.ui.setupUi(self)
        self.show()
        self.settings = qtc.QSettings('Qt_apps','PID_App')
        #print(self.settings.fileName())
        self.ui.int_SpinBox.setProperty("value", self.settings.value('int'))
        self.ui.win_SpinBox.setProperty("value", self.settings.value('win'))
        self.ui.dt_SpinBox.setProperty("value", self.settings.value('dt'))
        self.ui.k_doubleSpinBox.setProperty("value", self.settings.value('k'))
        self.ui.p_doubleSpinBox.setProperty("value", self.settings.value('p'))
        self.ui.i_doubleSpinBox.setProperty("value", self.settings.value('i'))
        self.ui.d_doubleSpinBox.setProperty("value", self.settings.value('d'))  
        self.ui.start_button.clicked.connect(self.start_plot_timer)
        self.ui.start_button.clicked.connect(self.start_PID_timer)
        self.ui.clear_button.clicked.connect(self.clear_data)
        self.ui.stop_button.clicked.connect(self.stop_timer)
        self.ui.save_button.clicked.connect(self.save_data)
        self.ui.load_button.clicked.connect(self.load_data)
        self.ui.close_button.clicked.connect(self.close_gui)
        self.ui.laser_low_button.clicked.connect(self.laser_low)
        self.ui.sp_doubleSpinBox.valueChanged.connect(self.write_power)
        self.ui.int_SpinBox.valueChanged.connect(self.start_plot_timer)
        self.ui.inf_checkBox.stateChanged.connect(self.start_plot_timer)
        self.ui.dt_SpinBox.valueChanged.connect(self.start_PID_timer)        
        self.interval = self.ui.int_SpinBox.value()
        self.win = self.ui.win_SpinBox.value()
        self.dt = self.ui.dt_SpinBox.value()
        self.setpoint = self.ui.sp_doubleSpinBox.value()

        self.ui.graphwidget.setBackground('w')
        styles = {'color':'r', 'font-size':'20px'}
        self.ui.graphwidget.setLabel('left', 'Power (W)', **styles)
        self.ui.graphwidget.setLabel('bottom', 'Time (s)', **styles)
        pen = pg.mkPen(color=(0, 0, 255), width = 2)
        pen_v = pg.mkPen(color=(0, 255, 0), width = 2)
        self.ui.graphwidget.setMouseEnabled(x=True, y=False)
        self.ui.graphwidget.setAutoVisible(x=None, y=True)
        self.x = list(np.zeros(1))
        self.y = list(np.zeros(1))
        self.y_v = list(np.zeros(1))
        self.data_line_v = self.ui.graphwidget.plot(self.x, self.y_v, pen=pen_v)
        self.data_line = self.ui.graphwidget.plot(self.x, self.y, pen=pen)
        #self.write_power(self.setpoint)
        self.show()  
        self.start_PID_timer()

    def readTLPM(self): #Read data from input device, returns said value
        power_c =  c_double()
        self.tlPM.measPower(byref(power_c))
        Power = power_c.value
        return (float(Power))

    def read_pow(self): #Function is called every 'dt' ms and provides input for PID and plotting
        flag = self.task.read()
        self.clock[1] = perf_counter()
        time_int = self.clock[1]-self.clock[0]
        self.counter[1] = self.counter[0]+time_int
        time = self.counter[1]
        if flag < 1 & self.ui.shootBox.isChecked() == True:
            self.buff_pow = [time,self.pow]
        else:
            self.pow = self.readTLPM()
            self.buff_pow = [time,self.pow]
            if self.ui.PID_checkBox.isChecked() == True:
                p_out, self.ERR, self.PID = self.PID_run(time_int, self.pow)
                self.write_power(p_out)
        self.clock[0] = self.clock[1]
        self.counter[0] = self.counter[1]

    def start_PID_timer(self):#Start a second timer used for the plotting, usually required to be different from the PID interval 'dt'
        self.clock[0] = perf_counter()
        self.timer.timeout.connect(self.read_pow)
        self.timer.start(self.dt)        

    def start_plot_timer(self):#Start a second timer used for the plotting, usually required to be different from the PID interval 'dt'
        self.int = self.ui.int_SpinBox.value()
        self.timer2.timeout.connect(self.plot_mode)
        self.timer2.start(self.int)

    def stop_timer(self): #Stop timers if they are running
        if self.timer.isActive() == True:
            self.timer.stop()
        if self.timer2.isActive() == True:
            self.timer2.stop()
         
    def write_power(self, pow_in):#Command to write voltage from output device, to be used as the feedback signal
        self.PWM = (pow_in+0.42889)/0.33463
        str1 = 'FUNc:SQU:DCYC +'
        str2 = str(self.PWM)
        str_out = str1+str2
        self.inst.write(str_out)

    def laser_low(self):
        self.write_power(0.1)
        self.ui.sp_doubleSpinBox.setProperty("value", 0.1)
        self.ui.PID_checkBox.setChecked(False)

    def PID_run(self, d_t, pow_in):
        setpoint = self.ui.sp_doubleSpinBox.value()
        K = self.ui.k_doubleSpinBox.value()
        KP = self.ui.p_doubleSpinBox.value()
        KI = self.ui.i_doubleSpinBox.value()
        KD = self.ui.d_doubleSpinBox.value()
        self.Error[1] = float(setpoint - pow_in) #error entering the PID controller, P
        self.Int[1] = self.Int[0]+((self.Error[1] + self.Error[0])*d_t) #integration of the total error, I        
        self.Der = (self.Error[1] - self.Error[0])/d_t #derivative of the error, D
        correction = K*KP*self.Error[1] + K*KI*self.Int[1]+ K*KD*self.Der
        new_power = correction + pow_in
        p_out = self._clamp(new_power, (0, (14*0.33463)-0.42889))
        #p_out = self._clamp(new_power, (0, 2.5))
        self.Error[0] = self.Error[1]# Pass new values for next reading
        self.Int[0] = self.Int[1]
        return p_out, self.Error[1], correction

    def _clamp(self, value, limits): #If output value goes outside the limits, _clamp will keep the value at the given limit value
        lower, upper = limits
        if value is None:
            return None
        elif (upper is not None) and (value > upper):
            return upper
        elif (lower is not None) and (value < lower):
            return lower
        return value
    
    def plot_mode(self): #This function is called from the plot timer and in turn, calls function to update plot
        [time,pow] = self.buff_pow
        if self.ui.PID_checkBox.isChecked() == True:
            self.update_plot_data(time, pow, self.PID)
        else:
           self.update_plot_data(time, pow, 0)
        self.ui.v_out_disp.display(self.PWM)

    def update_plot_data(self, time, pow_in, error): #Updates the plot with new values of time and pow_in. Plot resizes depending on 'window'
        self.win = round(self.ui.win_SpinBox.value()/(0.001*self.ui.int_SpinBox.value()))
        diff = self.win-len(self.x)
        self.x.append(time)  # Add a new value 1 higher than the last.
        self.y.append(pow_in)  # Add a new power value.
        self.y_v.append(error)  # Add a new power value.
        if self.ui.inf_checkBox.isChecked() == False:
            if diff == 0:
                #print(self.win)
                #print(len(self.x))
                self.x = self.x[1:]  # Remove the first x element.
                self.y = self.y[1:]  # Remove the first y element.
                self.y_v = self.y_v[1:]  # Remove the first
            elif diff < 0:
                #print(self.win)
                #print(len(self.x))
                self.x = self.x[5:]  # Remove the first 5 x elements.
                self.y = self.y[5:]  # Remove the first 5 y elements.
                self.y_v = self.y_v[5:]  # Remove the first
        if self.ui.PIDout_checkBox.isChecked() == True:
            self.data_line_v.setData(self.x, self.y_v)  # Update the data.self.data_line_v.setData(self.x,self.y)  # Update the data.
        else:
            self.data_line_v.setData(self.x, self.y)  # Update the data.self.data_line_v.setData(self.x,self.y)  # Update the data.
        self.data_line.setData(self.x, self.y)  # Update the data     

    def save_data(self): #Save the data that has been plotted
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ =QFileDialog.getSaveFileName(self,"Save File Window Title","PowerLog.txt","All Files (*)",options=option)
        file = open(filename,'w')
        np.savetxt(file,np.column_stack([self.x,self.y]))
        file.close()

    def load_data(self):#Load previous logs for analysis
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self,"Load File Window Title","","Text Files (*.txt)",options=option)
        array = np.loadtxt(filename,dtype=float)
        self.x=array[:,0]
        self.y=array[:,1]
        self.y_v = list(np.zeros(self.win))
        self.data_line.setData(self.x, self.y)  # Update the data.
        self.data_line_v.setData(self.y_v, self.y_v)  # Update the data.

    def clear_data(self): #Clear Data
        self.x = list(np.zeros(self.win))
        self.y = list(np.zeros(self.win))
        self.y_v = list(np.zeros(self.win))
        self.data_line.setData(self.x, self.y)
        self.data_line_v.setData(self.x, self.y_v)
   
    def close_gui(self):#Close the GUI, must be used instead of closing window with top right x in order to close the connections to hardware safely
        self.settings.setValue('k',self.ui.k_doubleSpinBox.value())
        self.settings.setValue('p',self.ui.p_doubleSpinBox.value())
        self.settings.setValue('i',self.ui.i_doubleSpinBox.value())
        self.settings.setValue('d',self.ui.d_doubleSpinBox.value())
        self.settings.setValue('dt',self.ui.dt_SpinBox.value())
        self.settings.setValue('int',self.ui.int_SpinBox.value())
        self.settings.setValue('win',self.ui.win_SpinBox.value())
        if self.timer.isActive() == True:
            self.timer.stop()
        if self.timer2.isActive() == True:
            self.timer2.stop()
        self.tlPM.close()
        self.inst.close() # close connection to function generator
        self.rm.close()
        self.task.stop() # Terminate DAQ Device
        self.task.close()
        sys.exit(app.exec_())

if __name__ == '__main__':
    app = qtw.QApplication(sys.argv)
    w = MainWindow()
    sys.exit(app.exec_())