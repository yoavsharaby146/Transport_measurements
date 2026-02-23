import sys
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QListWidget,
    QListWidgetItem, QAbstractItemView, QCheckBox, QColorDialog, QSpinBox, QFontComboBox
)
import pyqtgraph as pg
from pyqtgraph import PlotWidget


class CSVPlotter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV X-Y Plotter (pyqtgraph)")
        self.df = None

        # Widgets
        self.load_button = QPushButton("Load CSV")
        self.export_button = QPushButton("Export Plot to PNG")
        self.plot_button = QPushButton("Plot")
        self.autoscale_button = QPushButton("Autoscale")

        self.x_axis_dropdown = QComboBox()
        self.y_axis_list = QListWidget()
        self.y_axis_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        self.log_x_checkbox = QCheckBox("Log X")
        self.log_y_checkbox = QCheckBox("Log Y")
        self.dual_y_checkbox = QCheckBox("Dual Y Axis")
        self.legend_checkbox = QCheckBox("Show Legend")

        self.color_button = QPushButton("Choose Line Color")
        self.bgcolor_button = QPushButton("Choose Background Color")

        self.font_combo = QFontComboBox()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 32)
        self.font_size_spin.setValue(10)

        self.plot_widget = PlotWidget()
        self.plot_widget.showGrid(x=True, y=True)

        self.line_color = pg.mkColor('b')
        self.bg_color = pg.mkColor('w')

        # Layouts
        layout = QVBoxLayout()
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("X Axis:"))
        control_layout.addWidget(self.x_axis_dropdown)
        control_layout.addWidget(QLabel("Y Axes:"))
        control_layout.addWidget(self.y_axis_list)
        control_layout.addWidget(self.plot_button)
        control_layout.addWidget(self.export_button)
        control_layout.addWidget(self.autoscale_button)

        options_layout = QHBoxLayout()
        options_layout.addWidget(self.log_x_checkbox)
        options_layout.addWidget(self.log_y_checkbox)
        options_layout.addWidget(self.dual_y_checkbox)
        options_layout.addWidget(self.legend_checkbox)
        options_layout.addWidget(self.color_button)
        options_layout.addWidget(self.bgcolor_button)
        options_layout.addWidget(QLabel("Font:"))
        options_layout.addWidget(self.font_combo)
        options_layout.addWidget(QLabel("Size:"))
        options_layout.addWidget(self.font_size_spin)

        layout.addWidget(self.load_button)
        layout.addLayout(control_layout)
        layout.addLayout(options_layout)
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

        # Connections
        self.load_button.clicked.connect(self.load_csv)
        self.plot_button.clicked.connect(self.plot_data)
        self.export_button.clicked.connect(self.export_plot)
        self.color_button.clicked.connect(self.choose_line_color)
        self.bgcolor_button.clicked.connect(self.choose_bg_color)
        self.autoscale_button.clicked.connect(self.autoscale_plot)

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

        self.plot_widget.clear()
        self.plot_widget.setBackground(self.bg_color)

        font = self.font_combo.currentFont()
        font_size = self.font_size_spin.value()

        if self.dual_y_checkbox.isChecked() and len(y_cols) >= 2:
            left_axis = self.plot_widget.getPlotItem()
            right_axis = pg.ViewBox()
            left_axis.showAxis('right')
            left_axis.scene().addItem(right_axis)
            left_axis.getAxis('right').linkToView(right_axis)
            right_axis.setXLink(left_axis)

            def update_views():
                right_axis.setGeometry(left_axis.vb.sceneBoundingRect())
                right_axis.linkedViewChanged(left_axis.vb, right_axis.XAxis)
            update_views()
            left_axis.vb.sigResized.connect(update_views)

            y1, y2 = y_cols[0], y_cols[1]
            x = self.df[x_col].copy()
            y1_data = self.df[y1].copy()
            y2_data = self.df[y2].copy()
            if self.log_x_checkbox.isChecked(): x = x.apply(lambda v: v if v > 0 else None).apply(np.log10)
            if self.log_y_checkbox.isChecked():
                y1_data = y1_data.apply(lambda v: v if v > 0 else None).apply(np.log10)
                y2_data = y2_data.apply(lambda v: v if v > 0 else None).apply(np.log10)

            left_axis.plot(x, y1_data, pen=pg.mkPen(color=pg.intColor(0)), name=y1)
            right_axis.addItem(pg.PlotDataItem(x, y2_data, pen=pg.mkPen(color=pg.intColor(1)), name=y2))
            left_axis.setLabel('left', y1, **{'font-family': font.family(), 'font-size': str(font_size)})
            left_axis.setLabel('bottom', x_col, **{'font-family': font.family(), 'font-size': str(font_size)})
            left_axis.setLabel('right', y2, **{'font-family': font.family(), 'font-size': str(font_size)})
        else:
            x = self.df[x_col].copy()
            if self.log_x_checkbox.isChecked():
                x = x.apply(lambda v: v if v > 0 else None).apply(np.log10)

            for i, y_col in enumerate(y_cols):
                y = self.df[y_col].copy()
                if self.log_y_checkbox.isChecked():
                    y = y.apply(lambda v: v if v > 0 else None).apply(np.log10)
                pen = pg.mkPen(color=pg.intColor(i))
                self.plot_widget.plot(x, y, pen=pen, name=y_col)

            plot_item = self.plot_widget.getPlotItem()
            plot_item.setLabel('bottom', x_col, **{'font-family': font.family(), 'font-size': str(font_size)})
            plot_item.setLabel('left', ', '.join(y_cols), **{'font-family': font.family(), 'font-size': str(font_size)})

            if self.legend_checkbox.isChecked():
                plot_item.addLegend()

    def autoscale_plot(self):
        self.plot_widget.enableAutoRange()

    def choose_line_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.line_color = pg.mkColor(color.name())

    def choose_bg_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.bg_color = pg.mkColor(color.name())

    def export_plot(self):
        exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
        file_path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "plot.png", "PNG Files (*.png)")
        if file_path:
            exporter.export(file_path)


if __name__ == "__main__":
    import numpy as np
    import pyqtgraph.exporters

    app = QApplication(sys.argv)
    window = CSVPlotter()
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec())
