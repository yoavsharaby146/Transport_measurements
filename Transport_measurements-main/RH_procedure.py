import os
import sys
import time
import math
import numpy as np
from datetime import datetime

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from pymeasure.log import console_log

import pyqtgraph as pg



from pymeasure.experiment import Results, Worker
from pymeasure.display.plotter import Plotter

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QHBoxLayout, QLabel
from PyQt5.QtCore import QTimer
from pymeasure.experiment import Procedure, IntegerParameter, FloatParameter, Parameter, Metadata

from Instruments.SR830_with_add_ons import SR830
from Instruments.SR860_with_add_ons import SR860
from Instruments.keithley2450_with_add_ons import Keithley2450
from Instruments.keithley2604B import Keithley2604B
from Instruments.dilution_connection import DilutionInstrument


class Resistance_Magnet_field_measurement(Procedure):
    
    Title = Parameter('RH measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    acq_delay = FloatParameter('Acquisition  Delay (s)', default = 1)
    target_field = FloatParameter('Target Field(B)', default = 0 )
    step_size = IntegerParameter('Step size (mB)', default = 1)
    ramp_rate = FloatParameter('Ramp rate(T/ min)', default=0.001)
    axis = Parameter('Axis of magnet sweep (Bx, By, Bz)', default = 'bz')
    
# ----- B_x, B_y, B_z MUST be LAST -----
    DATA_COLUMNS =  [
        'time(s)',
        'Mixing_chanber(K)','Magnet Temperature(K)',
##        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)',
##        'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_1_X(V)', 'Lockin_Voltage_SRS860_1_Y(V)',
##        'Lockin_Voltage_SRS860_2_X(V)', 'Lockin_Voltage_SRS860_2_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        #'Lockin_Voltage_SRS830_3_X(V)', 'Lockin_Voltage_SRS830_3_Y(V)',
##        'Lockin_Voltage_SRS830_4_X(V)', 'Lockin_Voltage_SRS830_4_Y(V)',
        'B_x (T)', 'B_y (T)', 'B_z (T)', 
        ]

    def startup(self):
        print("Connecting to instruments")
        
        self.SRS860_1 = SR860("USB0::0xB506::0x2000::007030::INSTR")
        print('SRS860_1 using: USB0::0xB506::0x2000::007030::INSTR')
        
        self.SRS830_1 = SR830("GPIB::17")
        print('SRS830_1 using: GPIB::17')
         
        self.SRS830_2 = SR830("GPIB::18")
        print('SRS830_2 using: GPIB::18')
        
        #self.SRS830_3 = SR830("GPIB::9")
        self.Gate_1 = Keithley2450("USB0::0x05E6::0x2450::04416746::INSTR")
        
        print("Connecting to Dilution computer ip - 132.66.132.173, port - 33576")
        self.Dilution = DilutionInstrument(ip = '132.66.132.173', port = 33576)
        
        self.Dilution.connect()
        
        print("Connected to devices")

            

    def getmeas(self, t0):
        
        temperature = self.Dilution.get_temperature(thermometer_num = 8)
        
        vals = [time.time() - t0]
        vals += [temperature]
        
        magnet_temperature = self.Dilution.get_temperature(thermometer_num = 13)
        vals += [magnet_temperature]
        
        vals += [self.Gate_1.measure__voltage(), self.Gate_1.measure__current()]
        
        for attempt in range(10):
            try:
                x,y = self.SRS860_1.snap("X", "Y")
                if not math.isnan(x) and not math.isnan(y):
                    vals += [x,y]
                    break
            except :
                pass
            time.sleep(0.01)
        else:
            sys.exit("Attempted Snap 10 times in SRS860_1 and failed, Aborting measuremnt")
            
        
        
        for attempt in range(10):
            try:
                x,y = self.SRS830_1.snap("X", "Y")
                if not math.isnan(x) and not math.isnan(y):
                    vals += [x,y]
                    break
            except :
                pass
            time.sleep(0.01)
        else:
            sys.exit("Attempted Snap 10 times in SRS830_1 and failed, Aborting measuremnt ")
            
        
        for attempt in range(10):
            try:
                x,y = self.SRS830_2.snap("X", "Y")
                if not math.isnan(x) and not math.isnan(y):
                    vals += [x,y]
                    break
            except :
                pass
            time.sleep(0.1)
        else:
            sys.exit("Attempted Snap 10 times in SRS830_2 and failed, Aborting measuremnt")
            
                
##      vals += list(self.SRS830_3.snap("X", "Y"))
        
        ## Read magnetic fields 
        bx , by, bz = self.Dilution.read_magnet()
        vals += [bx, by, bz]
        
        
        return vals
    
    def execute(self):
        
        """
        Ramps a single magnetic axis with strict safety limits for a 3D vector magnet.
        """
        axis = self.axis.strip().lower()
        
        # --- 1. Validate individual axis boundaries ---
        if axis in ['bx', 'by'] and not (-1.0 <= self.target_field <= 1.0):
            raise ValueError(f"Safety Violation: {axis} must be between -1T and 1T. Requested: {self.target_field}T")
          
        if axis == 'bz' and not (-8.0 <= self.target_field <= 8.0):
            raise ValueError(f"Safety Violation: bz must be between -8T and 8T. Requested: {self.target_field}T")
        
        
        step_b = self.step_size / 1000
        if self.step_size == 0:
            step_b = 0.001
        
        # --- 2. Calculate the proposed new vector and array---
        current_bx, current_by, current_bz = self.Dilution.read_magnet()
        if axis == 'bx':
            
            new_bx, new_by, new_bz = self.target_field, current_by, current_bz
            num_points = int(abs(new_bx - current_bx)/step_b)+1
            field_range = np.linspace(current_bx, new_bx, num_points)
            
        elif axis == 'by':
            
            new_bx, new_by, new_bz = current_bx, self.target_field, current_bz
            num_points = int(abs(new_by - current_by)/step_b)+1
            field_range = np.linspace(current_by, new_by, num_points)
            
        elif axis == 'bz':
            
            new_bx, new_by, new_bz = current_bx, current_by, self.target_field
            num_points = int(abs(new_bz - current_bz)/step_b)+1
            field_range = np.linspace(current_bz, new_bz, num_points)
            
        else:
            raise ValueError(f"Invalid axis '{axis}'. Choose 'bx', 'by', or 'bz'.")

        # --- 3. Validate the combined vector limit ---
        # Rule: If using BX or BY (or both), the total vector cannot exceed 1.0 T.
        if new_bx != 0.0 or new_by != 0.0:
            total_magnitude = math.sqrt(new_bx**2 + new_by**2 + new_bz**2)
            if total_magnitude > 1.0:
                raise ValueError(
                    f"Safety Violation: In-plane axes are active, but total vector magnitude ({total_magnitude:.3f}T) "
                    f"exceeds the 1T limit! [Bx={new_bx}, By={new_by}, Bz={new_bz}]"
                )
        
        # --- 4. Safely fire the command ---
        print(f"Safety checks passed. starting Magnetic field {axis} sweep to {self.target_field}T with step size {self.step_size}mT")
        
        time_0 = time.time()
        
        for field in field_range:
            if axis == 'bx':
                self.Dilution.ramp_magnet_to(self.ramp_rate, field, new_by, new_bz)
            elif axis == 'by':
                self.Dilution.ramp_magnet_to(self.ramp_rate, new_bx, field, new_bz)
            elif axis == 'bz':
                self.Dilution.ramp_magnet_to(self.ramp_rate, new_bx, new_by, field)
            time.sleep(self.acq_delay)
            
            data = self.getmeas(time_0)
            
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            new_bx, new_by, new_bz = data[-3:]
            if self.should_stop():
                print("Measurement stopped")
                return

    def shutdown(self):
        self.Dilution.close()
        print("Finished measuring")




# --- Custom Stable Plotter Window ---
class LivePlotterWindow(QMainWindow):
    def __init__(self, results, worker):
        super().__init__()
        self.results = results
        self.worker = worker
        self.close_delay_counter = 0 
    
        
        self.setWindowTitle("Stable Live Plotter")
        self.resize(800, 600)
        
        # Main layout setup
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
        # --- Axis Controls ---
        control_layout = QHBoxLayout()
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        
        # Populate dropdowns with your DATA_COLUMNS
        columns = self.results.procedure.DATA_COLUMNS
        self.x_combo.addItems(columns)
        self.y_combo.addItems(columns)
        
        # Set default axes
        self.x_combo.setCurrentText('time(s)')
        self.y_combo.setCurrentText( 'B_z (T)')
        
        control_layout.addWidget(QLabel("X Axis:"))
        control_layout.addWidget(self.x_combo)
        control_layout.addWidget(QLabel("Y Axis:"))
        control_layout.addWidget(self.y_combo)
        layout.addLayout(control_layout)
        
        # --- Plotting Area ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w') # White background
        layout.addWidget(self.plot_widget)
        self.curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2)) # Blue line
        
        # --- The Safety Timer ---
        # This safely polls the data every 500ms so threads don't crash
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)
        
        # --- Add the Stop Button ---
        from PyQt5.QtWidgets import QPushButton
        self.stop_btn = QPushButton("STOP MEASUREMENT")
        self.stop_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self.interrupt_measurement)
        control_layout.addWidget(self.stop_btn) # Add it to your existing QHBoxLayout
        
    def interrupt_measurement(self):
        """Tells the worker to stop and changes button text."""
        if self.worker.is_alive():
            self.worker.stop()
            self.stop_btn.setText("STOPPING...")
            self.stop_btn.setEnabled(False)
            
    def update_plot(self):
        # 1. Check if the worker is done
        if not self.worker.is_alive():
            #print("Measurement finished. Closing plotter...")
            
            self.close_delay_counter += 1
            # Visual feedback on the button
            seconds_left = 3 - (self.close_delay_counter // 5)
            if seconds_left > 0:
                self.stop_btn.setText(f"SAVED - Closing in {seconds_left}s")
            
            if self.close_delay_counter >= 15: # 3 seconds @ 200ms intervals    
                self.timer.stop()
                self.close() # This exits app.exec_() in your main.run()
            return
        try:
            # Reload data from the Results object safely
            self.results.reload()
            data = self.results.data
            
            if data is not None and not data.empty:
                x_col = self.x_combo.currentText()
                y_col = self.y_combo.currentText()
                
                # CRITICAL: Drop NaNs to prevent pyqtgraph from crashing
                clean_data = data[[x_col, y_col]].dropna()
                
                if not clean_data.empty:
                    self.curve.setData(clean_data[x_col].values, clean_data[y_col].values)
                    self.plot_widget.setLabel('bottom', x_col)
                    self.plot_widget.setLabel('left', y_col)
        except Exception as e:
            # If a read collision happens, quietly ignore it and try again in 500ms
            pass 



class main:
    def __init__(self,
                 title='RH',
                 target_field = 0.5, step_size = 5,ramp_rate = 0.001 ,axis = 'bz',
                 acq_delay = 10,
                 Resistor='N/A', Contacts='N/A',
                 save_dir = r'C:\Users\USER\Desktop\Data\YoavSharaby'
                 ):
        
        print("Constructing an RH_procedure") 
        # 0. Handle QApplication (ensures only one exists)
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)

        # 1. Setup Procedure
        self.procedure = Resistance_Magnet_field_measurement()
        self.procedure.Title = title
        self.procedure.target_field = target_field
        self.procedure.step_size = step_size
        self.procedure.ramp_rate = ramp_rate
        
        self.procedure.acq_delay = acq_delay
        self.procedure.axis = axis
        
        self.procedure.Resistor = Resistor
        self.procedure.Contacts = Contacts

        # 2. Setup Results with a specific folder
 
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        # Combine folder and filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        filename = f'RH_Procedure_sweeping {axis}_to_{target_field}T_{timestamp}.csv'
        print("Constructing the Results with a data file: %s" % filename)
        print("Measurement saved in: %s" %save_dir)
        
        self.filename = os.path.join(save_dir, filename)
        self.results = Results(self.procedure, self.filename)
        
        # 3. Initialize Worker and Window
        self.worker = Worker(self.results)
        self.window = LivePlotterWindow(self.results,self.worker)

    def run(self):
        """Starts the measurement and opens the plot window."""
        self.worker.start()
        self.window.show()
        
        status = self.app.exec_()
        
        # Cleanup
        if self.worker.is_alive():
            self.worker.stop()
        return status

# This keeps the script runnable on its own, but safe to import
if __name__ == '__main__':
    manager = main()
    sys.exit(manager.run())
