import sys
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QListWidget,
    QListWidgetItem, QAbstractItemView
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class CSVPlotter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV Axis Plotter")
        self.df = None

        # Widgets
        self.load_button = QPushButton("Load CSV")
        self.x_axis_dropdown = QComboBox()
        self.y_axis_list = QListWidget()
        self.plot_button = QPushButton("Plot")

        self.y_axis_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        self.canvas = FigureCanvas(Figure(figsize=(6, 4)))
        self.ax = self.canvas.figure.add_subplot(111)

        # Layouts
        layout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("X Axis:"))
        hlayout.addWidget(self.x_axis_dropdown)
        hlayout.addWidget(QLabel("Y Axes:"))
        hlayout.addWidget(self.y_axis_list)
        hlayout.addWidget(self.plot_button)

        layout.addWidget(self.load_button)
        layout.addLayout(hlayout)
        layout.addWidget(self.canvas)

        self.setLayout(layout)

        # Connections
        self.load_button.clicked.connect(self.load_csv)
        self.plot_button.clicked.connect(self.plot_data)

    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if file_path:
            self.df = pd.read_csv(file_path, header=self.detect_header(file_path))
            self.x_axis_dropdown.clear()
            self.y_axis_list.clear()
            for col in self.df.columns:
                self.x_axis_dropdown.addItem(col)
                self.y_axis_list.addItem(QListWidgetItem(col))

    def detect_header(self, file_path, max_lines=20):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:max_lines]):
                if line.strip().lower().startswith("time(s)"):
                    return i
        return 0  # fallback

    def plot_data(self):
        if self.df is None:
            return

        x_col = self.x_axis_dropdown.currentText()
        y_cols = [item.text() for item in self.y_axis_list.selectedItems()]

        self.ax.clear()
        for y_col in y_cols:
            self.ax.plot(self.df[x_col], self.df[y_col], label=y_col)
        self.ax.set_title(f"{' , '.join(y_cols)} vs {x_col}")
        self.ax.set_xlabel(x_col)
        self.ax.set_ylabel("Values")
        self.ax.legend()
        self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CSVPlotter()
    window.show()
    sys.exit(app.exec())
