import sys
import os
import csv
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QComboBox, QFileDialog, QLabel, QLineEdit
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from pymeasure.instruments.srs import SR830
import visa

# Placeholder for Keithley 2604B class
class Keithley2604B:
    def __init__(self, resource):
        self.rm = visa.ResourceManager()
        self.inst = self.rm.open_resource(resource)

    def read_voltage(self):
        return float(self.inst.query("print(vsource1.measurev())"))

    def read_current(self):
        return float(self.inst.query("print(vsource1.measurei())"))

    def close(self):
        self.inst.close()

# Worker thread for measurements
class MeasurementThread(QThread):
    data_ready = pyqtSignal(dict)

    def __init__(self, sr830, keithley):
        super().__init__()
        self.running = False
        self.sr830 = sr830
        self.keithley = keithley

    def run(self):
        self.running = True
        while self.running:
            try:
                data = {
                    'time': time.time(),
                    'lockin_x': self.sr830.x,
                    'lockin_y': self.sr830.y,
                    'lockin_r': self.sr830.r,
                    'lockin_theta': self.sr830.theta,
                    'keithley_voltage': self.keithley.read_voltage(),
                    'keithley_current': self.keithley.read_current()
                }
                self.data_ready.emit(data)
                time.sleep(0.5)
            except Exception as e:
                print("Measurement error:", e)
                self.running = False

    def stop(self):
        self.running = False
        self.wait()

class MeasurementGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Measurement GUI")
        self.setGeometry(100, 100, 1000, 600)

        self.sr830 = SR830("GPIB::8")
        self.keithley = Keithley2604B("GPIB::26")

        self.data = []
        self.x_axis = 'time'
        self.y_axis = 'lockin_x'

        self.init_ui()
        self.thread = MeasurementThread(self.sr830, self.keithley)
        self.thread.data_ready.connect(self.update_plot)

    def init_ui(self):
        layout = QVBoxLayout()

        # Dropdowns
        controls_layout = QHBoxLayout()
        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        options = ['time', 'lockin_x', 'lockin_y', 'lockin_r', 'lockin_theta', 'keithley_voltage', 'keithley_current']
        self.x_combo.addItems(options)
        self.y_combo.addItems(options)
        self.x_combo.currentTextChanged.connect(lambda val: setattr(self, 'x_axis', val))
        self.y_combo.currentTextChanged.connect(lambda val: setattr(self, 'y_axis', val))
        controls_layout.addWidget(QLabel("X Axis:"))
        controls_layout.addWidget(self.x_combo)
        controls_layout.addWidget(QLabel("Y Axis:"))
        controls_layout.addWidget(self.y_combo)

        layout.addLayout(controls_layout)

        # Matplotlib plot
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Live Measurement")
        self.canvas.mpl_connect('scroll_event', self.zoom)
        layout.addWidget(self.canvas)

        # Buttons and file control
        file_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Select output directory")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_directory)
        file_layout.addWidget(self.dir_input)
        file_layout.addWidget(browse_btn)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Measurement")
        self.stop_btn = QPushButton("Stop")
        self.save_btn = QPushButton("Save to CSV")
        self.start_btn.clicked.connect(self.start_measurement)
        self.stop_btn.clicked.connect(self.stop_measurement)
        self.save_btn.clicked.connect(self.save_to_csv)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(file_layout)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def zoom(self, event):
        base_scale = 1.1
        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            return

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata

        new_xlim = [xdata - (xdata - xlim[0]) * scale_factor,
                    xdata + (xlim[1] - xdata) * scale_factor]
        new_ylim = [ydata - (ydata - ylim[0]) * scale_factor,
                    ydata + (ylim[1] - ydata) * scale_factor]

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.canvas.draw()

    def start_measurement(self):
        self.data.clear()
        self.thread.start()

    def stop_measurement(self):
        self.thread.stop()

    def update_plot(self, new_data):
        self.data.append(new_data)
        x = [d[self.x_axis] for d in self.data]
        y = [d[self.y_axis] for d in self.data]
        self.ax.clear()
        self.ax.plot(x, y, 'bo-')
        self.ax.set_xlabel(self.x_axis)
        self.ax.set_ylabel(self.y_axis)
        self.ax.grid(True)
        self.canvas.draw()

    def save_to_csv(self):
        if not self.dir_input.text():
            return
        filename = os.path.join(self.dir_input.text(), f"measurement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
            writer.writeheader()
            writer.writerows(self.data)

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            self.dir_input.setText(dir_path)

    def closeEvent(self, event):
        self.stop_measurement()
        self.sr830.shutdown()
        self.keithley.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = MeasurementGUI()
    gui.show()
    sys.exit(app.exec_())
