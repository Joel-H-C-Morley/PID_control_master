import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
import pyqtgraph as pg
import numpy as np
from time import perf_counter

Ui_PID_control, baseClass = uic.loadUiType('mainwindow.ui') #load the GUI layout made in QtCreator

class MainWindow(baseClass):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Connect and Initialise input
        #-
        #-
        #-

        # Connect and Initialise output
        #-
        #-
        #-
        
        # Setup GUI
        self.ui = Ui_PID_control()
        self.ui.setupUi(self)
        self.show()
        self.settings = qtc.QSettings('Qt_apps','PID_App')
        #print(self.settings.fileName()) #show location of registry folder containing stored values in the GUI
        self.ui.int_SpinBox.setProperty("value", self.settings.value('int')) #Set GUI values taken from the registry 
        self.ui.win_SpinBox.setProperty("value", self.settings.value('win'))
        self.ui.dt_SpinBox.setProperty("value", self.settings.value('dt'))
        self.ui.k_doubleSpinBox.setProperty("value", self.settings.value('k'))
        self.ui.p_doubleSpinBox.setProperty("value", self.settings.value('p'))
        self.ui.i_doubleSpinBox.setProperty("value", self.settings.value('i'))
        self.ui.d_doubleSpinBox.setProperty("value", self.settings.value('d'))
        self.ui.start_button.clicked.connect(self.start_plot_timer) #Give functionality to GUI components
        self.ui.stop_button.clicked.connect(self.stop_timer)
        self.ui.save_button.clicked.connect(self.save_data)
        self.ui.load_button.clicked.connect(self.load_data)
        self.ui.close_button.clicked.connect(self.close_gui)
        self.ui.sp_doubleSpinBox.valueChanged.connect(self.write_power)
        self.ui.int_SpinBox.valueChanged.connect(self.start_plot_timer) #The 'infinte checkbox' and 'interval spinbox' requires the timer to be restarted
        self.ui.inf_checkBox.stateChanged.connect(self.start_plot_timer)
        self.interval = self.ui.int_SpinBox.value() #Extract GUI values and put into 'self'
        self.win = self.ui.win_SpinBox.value()
        self.dt = self.ui.dt_SpinBox.value()
        self.setpoint = self.ui.sp_doubleSpinBox.value()

        #Create plotting space
        self.ui.graphwidget.setBackground('w')
        styles = {'color':'r', 'font-size':'20px'} #Set plot options
        self.ui.graphwidget.setLabel('left', 'Power (mW)', **styles)
        self.ui.graphwidget.setLabel('bottom', '', **styles)
        pen = pg.mkPen(color=(0, 0, 255), width = 2)
        #pen_v = pg.mkPen(color=(0, 255, 0), width = 2)
        self.ui.graphwidget.setMouseEnabled(x=True, y=False)
        self.ui.graphwidget.setAutoVisible(x=None, y=True)
        #self.buff_pow = 0
        self.x = list(np.zeros(self.win)) #Initialise vectors to accept the input data for plotting
        self.y = list(np.zeros(self.win))
        self.y_v = list(np.zeros(self.win))
        self.data_line = self.ui.graphwidget.plot(self.x, self.y, pen=pen) #Create dataline for plot from the initial vectors
        #self.data_line_v = self.ui.graphwidget.plot(self.x, self.y_v, pen=pen_v)
        self.show()

        #Base timer used for PID and plotting. This runs in background even if PID not activated. Plotting function samples the data according to 'Interval'
        self._bufsize = int(self.win)
        self.timer = qtc.QTimer()
        self.timer2 = qtc.QTimer() #create, but don't activate second timer used for plotting
        self.timer.timeout.connect(self.bkgnd_read)
        self.timer.start(self.dt)

        #Initialse vectors used for passing old and new values around the PID loop
        self.clock = np.zeros(2)
        self.counter = np.zeros(2)
        self.Error = np.zeros(2)
        self.Int = np.zeros(2)
        self.Calib = 1.69 #Value to convert the power output value given by PID loop and the correct corresponding control voltage output
        self.clock[0] = perf_counter()
    
    def read_input(self): #Read data from input device, returns said value
        #-
        #-
        #-
        return (...)

    def bkgnd_read(self): #Function is called every 'dt' ms and provides input for PID and plotting
        pow = self.read_input() #Extract a single value from input signal, used for y values
        self.clock[1] = perf_counter() 
        time_int = self.clock[1]-self.clock[0] #Measure actual time interval between readings
        self.counter[1] = self.counter[0]+time_int
        time = self.counter[1] #Convert time interval into elapsed time for x-values
        self.buff_pow = [time,pow] #Create list of x and y data
        if self.ui.PID_checkBox.isChecked() == True: #If PID box is checked, it will initiate the PID loop
            p_out, self.ERR, self.PID = self.PID_run(time_int, pow)
            self.write_power(p_out)
        self.clock[0] = self.clock[1] #Pass new values into vector to be used as old vaules in the next loop
        self.counter[0] = self.counter[1]

    def start_plot_timer(self): #Start a second timer used for the plotting, usually required to be different from the PID interval 'dt'
        self.int = self.ui.int_SpinBox.value() #Determine timer interval from GUI
        self._bufsize = int(self.win)
        self.timer2.timeout.connect(self.plot_mode)
        self.timer2.start(self.int)

    def stop_timer(self): #Stop timers if they are running
        if self.timer.isActive() == True:
            self.timer.stop()
        if self.timer2.isActive() == True:
            self.timer2.stop()

    def plot_mode(self): #This function is called from the plot timer and in turn, calls function to update plot
        [time,pow] = self.buff_pow #Takes the current value of input and time from the bkgnd_read
        if self.ui.PIDout_checkBox.isChecked() == True: #Plots signal input and if selected, PID output
            self.update_plot_data(time, pow, self.PID)
        else:
            self.update_plot_data(time, pow, 0)
            
    def write_power(self, pow_in): #Command to write voltage from output device, to be used as the feedback signal
        #-
        # - pow_in*self.Calib is used here
        #-
        pass #**remove this line when function is populated**

    def PID_run(self, d_t, pow_in):
        setpoint = self.ui.sp_doubleSpinBox.value() #Extract PID values from GUI
        K = self.ui.k_doubleSpinBox.value()
        KP = self.ui.p_doubleSpinBox.value()
        KI = self.ui.i_doubleSpinBox.value()
        KD = self.ui.d_doubleSpinBox.value()
        self.Error[1] = float(setpoint - pow_in) #error entering the PID controller, P
        self.Int[1] = self.Int[0]+((self.Error[1] + self.Error[0])*d_t) #integration of the total error, I
        self.Der = (self.Error[1] - self.Error[0])/d_t #derivative of the error, D
        correction = K*KP*self.Error[1] + K*KI*self.Int[1]+ K*KD*self.Der
        new_power = correction + pow_in
        p_out = self._clamp(new_power, (0, 1/self.Calib)) #Limit output between 0 and 1 for safety (if output driver does not already do this)
        self.Error[0] = self.Error[1]# Pass new values for next reading
        self.Int[0] = self.Int[1]
        return p_out, self.Error[1], correction, 

    def _clamp(self, value, limits): #If output value goes outside the limits, _clamp will keep the value at the given limit value
        lower, upper = limits
        if value is None:
            return None
        elif (upper is not None) and (value > upper):
            return upper
        elif (lower is not None) and (value < lower):
            return lower
        return value

    def update_plot_data(self, time, pow_in, error): #Updates the plot with new values of time and pow_in. Plot resizes depending on 'window'
        self.win = self.ui.win_SpinBox.value() #Extract value for window size (data to be displayed) from GUI
        if self.ui.inf_checkBox.isChecked() == True: # Add new data ad infinitum
            self.x.append(time)  # Add a new time value
            self.y.append(pow_in)  # Add a new power value.
        else:
            diff = self.win-len(self.x)
            if diff == 0: #Maintain data vector length at given window value
                self.x = self.x[1:] #Remove the first element  
                self.y = self.y[1:]
                self.x.append(time) #Add a new element
                self.y.append(pow_in)
            elif diff > 0: #Begin to increase data vector length
                self.x.append(time) #Add a new element
                self.y.append(pow_in)
            elif diff < 0: #Begin to decrease data vector length
                self.x = self.x[5:]  # Remove the first 5 elements.
                self.y = self.y[5:]  
                self.x.append(time) #Add a new element               
                self.y.append(pow_in)  
        self.data_line.setData(self.x, self.y) #Send vectors appended with new values to the plot
    
    def save_data(self): #Save the data that has been plotted
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ =QFileDialog.getSaveFileName(self,"Save File Window Title","PowerLog.txt","All Files (*)",options=option)
        file = open(filename,'w')
        np.savetxt(file,np.column_stack([self.x,self.y]))
        file.close()

    def load_data(self): #Load previous logs for analysis
        option=QFileDialog.Options()
        option|=QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self,"Load File Window Title","","Text Files (*.txt)",options=option)
        array = np.loadtxt(filename,dtype=float)
        self.x=array[:,0]
        self.y=array[:,1]
        self.data_line.setData(self.x, self.y)

    def close_gui(self): #Close the GUI, must be used instead of closing window with top right x in order to close the connections to hardware safely
        self.settings.setValue('k',self.ui.k_doubleSpinBox.value()) #Save current GUI values back to registry to be loaded during the next use
        self.settings.setValue('p',self.ui.p_doubleSpinBox.value())
        self.settings.setValue('i',self.ui.i_doubleSpinBox.value())
        self.settings.setValue('d',self.ui.d_doubleSpinBox.value())
        self.settings.setValue('dt',self.ui.dt_SpinBox.value())
        self.settings.setValue('int',self.ui.int_SpinBox.value())
        self.settings.setValue('win',self.ui.win_SpinBox.value())
        #- Close connection to input device
        #- Close connection to output device
        sys.exit(app.exec_())

if __name__ == '__main__':
    app = qtw.QApplication(sys.argv)
    w = MainWindow()
    sys.exit(app.exec_())