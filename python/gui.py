import sys
import json
from pathlib import Path
import subprocess
import os
from typing import Dict, Optional
from datetime import datetime

from PyQt6.QtCore import Qt, QPointF, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QComboBox, QListWidget, QListWidgetItem, QTabWidget, 
    QScrollArea, QLineEdit, QStatusBar, QSpinBox, QCheckBox, QFrame,
    QSpacerItem, QSizePolicy, QGraphicsDropShadowEffect, QStackedWidget
)
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QPalette, QColor, QFont, QIcon, QPainter, QLinearGradient, QPen, QBrush, QPixmap
import pyqtgraph as pg

from .hardware import find_sensors, find_fans


# Modern Color Palette
class Colors:
    """Modern color palette for the application."""
    # Primary colors
    PRIMARY = "#00d4ff"
    PRIMARY_DARK = "#00b8e6"
    PRIMARY_LIGHT = "#33e0ff"
    
    # Secondary colors
    SECONDARY = "#ff6b35"
    SECONDARY_DARK = "#e65a2b"
    
    # Background colors
    BG_DARKEST = "#1a1a2e"
    BG_DARK = "#1f1f35"
    BG_MEDIUM = "#252542"
    BG_LIGHT = "#2b2b4a"
    BG_CARD = "#2a2a40"
    
    # Text colors
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#b8b8d0"
    TEXT_MUTED = "#6b6b80"
    
    # Status colors
    SUCCESS = "#00ff88"
    WARNING = "#ffaa00"
    ERROR = "#ff4466"
    INFO = "#00d4ff"
    
    # Gradient stops
    GRADIENT_START = "#00d4ff"
    GRADIENT_END = "#0099cc"


MODERN_STYLESHEET = f"""
/* Global Styles */
QWidget {{
    font-family: 'Segoe UI', 'Inter', 'Roboto', Arial, sans-serif;
    font-size: 10pt;
    color: {Colors.TEXT_PRIMARY};
    background-color: {Colors.BG_DARKEST};
}}

/* Scrollbar Styling */
QScrollBar:vertical {{
    background-color: {Colors.BG_DARK};
    width: 10px;
    border-radius: 5px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {Colors.BG_LIGHT};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {Colors.PRIMARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {Colors.BG_DARK};
    height: 10px;
    border-radius: 5px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {Colors.BG_LIGHT};
    border-radius: 5px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {Colors.PRIMARY};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Buttons */
QPushButton {{
    background-color: {Colors.PRIMARY};
    color: {Colors.BG_DARKEST};
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 10pt;
    min-width: 100px;
}}
QPushButton:hover {{
    background-color: {Colors.PRIMARY_LIGHT};
}}
QPushButton:pressed {{
    background-color: {Colors.PRIMARY_DARK};
}}
QPushButton:disabled {{
    background-color: {Colors.BG_LIGHT};
    color: {Colors.TEXT_MUTED};
}}

/* Secondary Button Style */
QPushButton#secondaryButton {{
    background-color: transparent;
    border: 2px solid {Colors.PRIMARY};
    color: {Colors.PRIMARY};
}}
QPushButton#secondaryButton:hover {{
    background-color: {Colors.PRIMARY};
    color: {Colors.BG_DARKEST};
}}

/* Danger Button Style */
QPushButton#dangerButton {{
    background-color: {Colors.ERROR};
    color: white;
}}
QPushButton#dangerButton:hover {{
    background-color: #ff6685;
}}

/* Input Fields */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {Colors.BG_MEDIUM};
    border: 2px solid {Colors.BG_LIGHT};
    border-radius: 6px;
    padding: 8px 12px;
    color: {Colors.TEXT_PRIMARY};
    selection-background-color: {Colors.PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {Colors.PRIMARY};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border: 2px solid {Colors.PRIMARY_DARK};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {Colors.PRIMARY};
    margin-right: 10px;
}}

/* SpinBox arrows */
QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    width: 20px;
    background-color: {Colors.BG_LIGHT};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {Colors.PRIMARY};
}}

/* Tab Widget */
QTabWidget::pane {{
    border: none;
    background-color: transparent;
    border-radius: 12px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {Colors.TEXT_SECONDARY};
    padding: 12px 24px;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 500;
    margin-right: 4px;
}}
QTabBar::tab:hover {{
    color: {Colors.TEXT_PRIMARY};
    background-color: {Colors.BG_CARD};
}}
QTabBar::tab:selected {{
    color: {Colors.PRIMARY};
    border-bottom: 3px solid {Colors.PRIMARY};
    background-color: transparent;
}}
QTabBar::tab:first {{
    margin-left: 8px;
}}
QTabBar::tab:last {{
    margin-right: 8px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT_SECONDARY};
    border-top: 1px solid {Colors.BG_LIGHT};
    padding: 8px;
    font-size: 9pt;
}}

/* List Widget */
QListWidget {{
    background-color: {Colors.BG_MEDIUM};
    border: 2px solid {Colors.BG_LIGHT};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px;
    border-radius: 6px;
    margin: 2px 4px;
    background-color: transparent;
}}
QListWidget::item:hover {{
    background-color: {Colors.BG_LIGHT};
}}
QListWidget::item:selected {{
    background-color: {Colors.PRIMARY};
    color: {Colors.BG_DARKEST};
    font-weight: 600;
}}

/* CheckBox */
QCheckBox {{
    color: {Colors.TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 2px solid {Colors.BG_LIGHT};
    background-color: {Colors.BG_MEDIUM};
}}
QCheckBox::indicator:hover {{
    border: 2px solid {Colors.PRIMARY};
}}
QCheckBox::indicator:checked {{
    background-color: {Colors.PRIMARY};
    border: 2px solid {Colors.PRIMARY};
}}

/* Labels */
QLabel {{
    color: {Colors.TEXT_PRIMARY};
    background-color: transparent;
}}
QLabel#titleLabel {{
    font-size: 18pt;
    font-weight: 700;
    color: {Colors.TEXT_PRIMARY};
}}
QLabel#sectionTitle {{
    font-size: 12pt;
    font-weight: 600;
    color: {Colors.PRIMARY};
}}
QLabel#valueLabel {{
    font-size: 14pt;
    font-weight: 600;
    color: {Colors.SUCCESS};
}}
QLabel#mutedLabel {{
    color: {Colors.TEXT_MUTED};
    font-size: 9pt;
}}

/* Card/Frame */
QFrame#card {{
    background-color: {Colors.BG_CARD};
    border-radius: 12px;
    border: 1px solid {Colors.BG_LIGHT};
}}
QFrame#headerCard {{
    background-color: {Colors.BG_CARD};
    border-radius: 16px;
    border: none;
}}

/* GroupBox */
QGroupBox {{
    font-weight: 600;
    color: {Colors.TEXT_SECONDARY};
    border: 2px solid {Colors.BG_LIGHT};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {Colors.PRIMARY};
}}

/* Tool Tip */
QToolTip {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BG_LIGHT};
    border-radius: 4px;
    padding: 6px 10px;
}}

/* Progress Bar (if needed later) */
QProgressBar {{
    background-color: {Colors.BG_MEDIUM};
    border-radius: 6px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {Colors.PRIMARY};
    border-radius: 6px;
}}
"""


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "fan_controller"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    new_config_path = config_dir / "config.json"
    
    # If a config already exists in the new location, we're done.
    if new_config_path.exists():
        return config_dir
        
    # For backward compatibility, check the CWD
    old_config_path = Path.cwd() / "config.json"
    if old_config_path.exists():
        import shutil
        shutil.copy(old_config_path, new_config_path)
        return config_dir
        
    # If no config is found, the load_config function will create a default one.
    return config_dir


class FanCurvePlot(pg.PlotWidget):
    """Interactive plot widget for editing fan curves with modern styling."""
    
    # Signal emitted when curve points change
    pointsChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up modern plot appearance
        self.setBackground(Colors.BG_MEDIUM)
        self.setLimits(xMin=0, xMax=100, yMin=0, yMax=100)
        self.getPlotItem().vb.setXRange(0, 100, padding=0.05)
        self.getPlotItem().vb.setYRange(0, 100, padding=0.05)
        
        # Style axis labels
        self.setLabel('bottom', 'Temperature (°C)', color=Colors.TEXT_SECONDARY, size='12pt')
        self.setLabel('left', 'Fan Speed (%)', color=Colors.TEXT_SECONDARY, size='12pt')
        
        # Style ticks
        ax_bottom = self.getAxis('bottom')
        ax_left = self.getAxis('left')
        ax_bottom.setTickFont(QFont('Segoe UI', 9))
        ax_left.setTickFont(QFont('Segoe UI', 9))
        ax_bottom.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
        ax_left.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
        
        # Show subtle grid with proper styling
        grid_pen = QPen(QColor(Colors.TEXT_MUTED), 1)
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        self.showGrid(x=True, y=True, alpha=0.2)
        # Set grid through axis properties (pyqtgraph uses setGrid for enabling, not styling)
        ax_bottom.gridAlpha = 0.2
        ax_left.gridAlpha = 0.2
        
        # Create gradient curve
        gradient = QLinearGradient(0, 0, 100, 100)
        gradient.setColorAt(0, QColor(Colors.GRADIENT_START))
        gradient.setColorAt(1, QColor(Colors.GRADIENT_END))
        
        # Create curve with modern styling
        self.curve = self.plot(
            pen=pg.mkPen(color=Colors.PRIMARY, width=3),
            symbol='o',
            symbolBrush=QColor(Colors.SECONDARY),
            symbolPen=QColor(Colors.BG_DARKEST),
            symbolSize=12,
            shadowPen=pg.mkPen(color='#00000080', width=5)
        )
        
        # Add glow effect area under curve
        self.fill_curve = self.plot(
            fillLevel=0,
            brush=pg.mkBrush(color=f'{Colors.PRIMARY}40')
        )
        
        self.points = []
        self.dragged_point = None
        self.getPlotItem().vb.setMouseEnabled(x=False, y=False)
        
        # Remove default border
        self.setStyleSheet("border: none;")

    def set_points(self, points):
        """Set the curve points and update the plot."""
        if not points:
            self.curve.setData([], [])
            self.fill_curve.setData([], [])
            self.points = []
            self.pointsChanged.emit()
            return
            
        self.points = sorted([[float(p[0]), float(p[1])] for p in points])
        x_coords = [p[0] for p in self.points]
        y_coords = [p[1] for p in self.points]
        self.curve.setData(x_coords, y_coords)
        
        # Update filled area under curve
        self.fill_curve.setData(x_coords, y_coords)
        
        # Emit signal to notify of changes
        self.pointsChanged.emit()

    def mousePressEvent(self, ev):
        pos = self.getPlotItem().vb.mapSceneToView(QPointF(ev.pos()))
        x, y = pos.x(), pos.y()

        # Find closest point
        closest_point = None
        min_dist = float('inf')
        for i, p in enumerate(self.points):
            dist = (p[0] - x)**2 + (p[1] - y)**2
            if dist < min_dist:
                min_dist = dist
                closest_point = i

        if ev.button() == Qt.MouseButton.LeftButton:
            if closest_point is not None and min_dist < 25:
                self.dragged_point = closest_point
            else:
                # Add new point
                if 0 <= x <= 100 and 0 <= y <= 100:
                    self.points.append([x, y])
                    self.set_points(self.points)
                    self.dragged_point = len(self.points) - 1

        elif ev.button() == Qt.MouseButton.RightButton:
            # Remove point
            if closest_point is not None and min_dist < 25:
                self.points.pop(closest_point)
                self.set_points(self.points)

    def mouseMoveEvent(self, ev):
        if self.dragged_point is not None:
            pos = self.getPlotItem().vb.mapSceneToView(QPointF(ev.pos()))
            x, y = pos.x(), pos.y()
            x = max(0, min(100, x))
            y = max(0, min(100, y))
            self.points[self.dragged_point] = [x, y]
            self.set_points(self.points)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.dragged_point = None
            self.set_points(self.points)


class FanControlApp(QWidget):
    """Main application window for fan controller GUI with modern UI."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fan Controller")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Set up config paths
        self.config_dir = get_config_dir()
        self.config_path = self.config_dir / "config.json"
        self.status_path = self.config_dir / ".fan_controller_status.json"
        
        # Apply modern theme
        self.apply_modern_theme()
        
        # Create main layout with header
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header section
        header_frame = QFrame()
        header_frame.setObjectName("headerCard")
        header_frame.setMaximumHeight(120)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(30, 20, 30, 20)
        
        # App title and icon area
        title_layout = QVBoxLayout()
        title_layout.setSpacing(5)
        
        app_title = QLabel("FAN CONTROLLER")
        app_title.setObjectName("titleLabel")
        app_title.setStyleSheet(f"""
            font-size: 24pt;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
            letter-spacing: 2px;
        """)
        
        subtitle = QLabel("Advanced Temperature-Based Fan Control")
        subtitle.setObjectName("mutedLabel")
        subtitle.setStyleSheet(f"""
            font-size: 10pt;
            color: {Colors.TEXT_SECONDARY};
        """)
        
        title_layout.addWidget(app_title)
        title_layout.addWidget(subtitle)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Status indicator in header
        status_indicator_layout = QVBoxLayout()
        status_indicator_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"""
            font-size: 24pt;
            color: {Colors.WARNING};
        """)
        
        self.status_label = QLabel("INITIALIZING...")
        self.status_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {Colors.TEXT_SECONDARY};
            font-weight: 500;
        """)
        
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.setSpacing(8)
        
        status_indicator_layout.addLayout(status_row)
        header_layout.addLayout(status_indicator_layout)
        
        main_layout.addWidget(header_frame)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.hardware_tab = QWidget()
        self.curves_tab = QWidget()
        self.aliases_tab = QWidget()

        self.tabs.addTab(self.hardware_tab, "Hardware Monitor")
        self.tabs.addTab(self.curves_tab, "Fan Curves")
        self.tabs.addTab(self.aliases_tab, "Device Settings")
        
        main_layout.addWidget(self.tabs)
        
        # Modern status bar
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        main_layout.addWidget(self.status_bar)
        
        self.setLayout(main_layout)

        # Initialize data
        self.load_config()
        self.controller_process = None
        self.sensors = {}
        self.sensor_items = {}
        self.fan_widgets = {}

        # Initialize UI
        self.init_aliases_tab()
        self.init_hardware_tab()
        self.init_curves_tab()
        self.update_ui_with_aliases()

        # Start status update timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

        # Start controller
        self.restart_controller()

    def apply_modern_theme(self):
        """Apply a modern dark theme to the application."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARKEST))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_MEDIUM))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_LIGHT))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(Colors.BG_CARD))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(Colors.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_CARD))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(Colors.ERROR))
        palette.setColor(QPalette.ColorRole.Link, QColor(Colors.PRIMARY))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.BG_DARKEST))
        self.setPalette(palette)

        # Apply comprehensive modern stylesheet
        self.setStyleSheet(MODERN_STYLESHEET)

    def get_alias(self, path: str) -> str:
        """Get the alias for a hardware path."""
        return self.config.get("aliases", {}).get(path, path)

    def load_config(self):
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "curves": {},
                "fans": {},
                "aliases": {},
                "hidden_fans": [],
                "hidden_sensors": []
            }
        
        # Ensure all required keys exist
        for key in ["aliases", "hidden_sensors", "hidden_fans"]:
            if key not in self.config:
                self.config[key] = [] if "hidden" in key else {}

        # Convert old single sensor format to new multi-sensor format if necessary
        config_changed = False
        for curve_name, curve_data in self.config.get("curves", {}).items():
            if isinstance(curve_data.get("sensor"), str):
                curve_data["sensor"] = {
                    "function": "single", # Use "single" as a pseudo-function for single sensor curves
                    "paths": [curve_data["sensor"]]
                }
                config_changed = True
            elif not isinstance(curve_data.get("sensor"), dict) or "function" not in curve_data["sensor"] or "paths" not in curve_data["sensor"]:
                # Invalid config - fix it
                curve_data["sensor"] = {"function": "single", "paths": []}
                config_changed = True
        
        # Save the converted config back to file if it was changed
        if config_changed:
            self.save_config()

    def save_config(self, restart=True):
        """Save configuration to file.
        
        Args:
            restart: Whether to restart the controller after saving (default: True)
        """
        if "fans" not in self.config:
            self.config["fans"] = {}
        
        for fan_path, widgets in self.fan_widgets.items():
            self.config["fans"][fan_path] = widgets["combo"].currentText()

        if "hardware" not in self.config:
            self.config["hardware"] = {}
            
        for fan_path, widgets in self.fan_widgets.items():
            if "min_speed_spinbox" in widgets:
                self.config["hardware"]["nvidia_min_fan_speed"] = widgets["min_speed_spinbox"].value()

        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)
        
        if restart:
            self.restart_controller()

    def restart_controller(self):
        """Restart the fan controller daemon."""
        if self.controller_process:
            self.controller_process.terminate()
            self.controller_process.wait()
        
        if self.status_path.exists():
            self.status_path.unlink()

        # Use the installed package entry point
        self.controller_process = subprocess.Popen(
            [sys.executable, "-m", "fan_controller.main"],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)}
        )

    def update_status(self):
        """Update the status bar and hardware display with modern indicators."""
        if not self.status_path.exists():
            self.update_status_indicator("stopped")
            self.status_bar.showMessage("Controller: STOPPED")
            return

        try:
            with open(self.status_path, "r") as f:
                status_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self.update_status_indicator("unknown")
            self.status_bar.showMessage("Controller: STATUS UNKNOWN")
            return

        # Check if process is running
        pid = status_data.get("pid")
        try:
            if pid:
                os.kill(pid, 0)
        except OSError:
            self.update_status_indicator("stopped")
            self.status_bar.showMessage("Controller: STOPPED")
            if self.status_path.exists():
                self.status_path.unlink()
            return

        controller_status = status_data.get("status", "UNKNOWN")
        if controller_status == "running":
            self.update_status_indicator("running")
            self.status_bar.showMessage("Controller: RUNNING")
            self.update_sensor_combo(status_data)
        elif controller_status == "error":
            self.update_status_indicator("error")
            error_message = status_data.get('error_message', 'Unknown error')
            self.status_bar.showMessage(f"Controller: ERROR ({error_message})")
        else:
            self.update_status_indicator("unknown")
            self.status_bar.showMessage(f"Controller: {controller_status.upper()}")

        # Update hardware tab with animated labels
        for fan_path, widgets in self.fan_widgets.items():
            fan_status = status_data.get("fans", {}).get(fan_path)
            if not fan_status:
                widgets["temp_label"].setText("--°C")
                widgets["speed_label"].setText("--%")
                continue

            temp = fan_status.get("effective_temp")
            speed = fan_status.get("speed")

            if temp is not None:
                widgets["temp_label"].setText(f"{temp:.1f}°C")
            else:
                widgets["temp_label"].setText("--°C")
                
            if speed is not None:
                widgets["speed_label"].setText(f"{speed:.1f}%")
            else:
                widgets["speed_label"].setText("--%")
    
    def update_status_indicator(self, status: str):
        """Update the header status indicator based on controller status."""
        colors = {
            "running": Colors.SUCCESS,
            "stopped": Colors.ERROR,
            "error": Colors.ERROR,
            "unknown": Colors.WARNING,
            "initializing": Colors.WARNING
        }
        
        color = colors.get(status, Colors.TEXT_MUTED)
        text = status.upper()
        
        self.status_dot.setStyleSheet(f"""
            font-size: 24pt;
            color: {color};
        """)
        
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {color};
            font-weight: 600;
        """)

    def update_sensor_combo(self, status_data):
        """Update sensor combo boxes with current temperatures."""
        if not self.sensor_items:
            return
        for sensor_path, item in self.sensor_items.items():
            temp = status_data.get("sensors", {}).get(sensor_path)
            display_text = self.get_alias(sensor_path)
            if temp is not None:
                display_text += f" ({temp:.1f}°C)"
            item.setText(display_text)

    def update_ui_with_aliases(self):
        """Update UI with current aliases."""
        for path, widgets in self.alias_widgets.items():
            widgets["alias_input"].setText(self.get_alias(path))
            if widgets["type"] == "fan":
                widgets["visible_checkbox"].setChecked(
                    path not in self.config.get("hidden_fans", [])
                )
            elif widgets["type"] == "sensor":
                widgets["visible_checkbox"].setChecked(
                    path not in self.config.get("hidden_sensors", [])
                )

        self.sensors = self.find_sensors()
        self.init_hardware_tab()
        self.init_curves_tab()
        self.update_fan_curve_combos()

    def find_sensors(self) -> Dict[str, str]:
        """Find all visible sensors."""
        all_sensors = find_sensors()
        sensors = {}
        for path in all_sensors.keys():
            if path not in self.config.get("hidden_sensors", []):
                name = self.get_alias(path)
                sensors[name] = path
        return sensors

    def find_fans(self) -> Dict[str, str]:
        """Find all visible fans."""
        all_fans = find_fans()
        fans = {}
        for path in all_fans.keys():
            if path not in self.config.get("hidden_fans", []):
                name = self.get_alias(path)
                fans[name] = path
        return fans

    def init_hardware_tab(self):
        """Initialize the hardware tab with modern card-based layout."""
        # Clear existing widgets
        if self.hardware_tab.layout() is not None:
            while self.hardware_tab.layout().count():
                item = self.hardware_tab.layout().takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            self.hardware_tab.setLayout(QVBoxLayout())

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self.hardware_tab.layout().addWidget(scroll)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Section title
        section_title = QLabel("FAN CONFIGURATION")
        section_title.setObjectName("sectionTitle")
        section_title.setStyleSheet(f"""
            font-size: 14pt;
            font-weight: 600;
            color: {Colors.PRIMARY};
            margin-bottom: 8px;
        """)
        layout.addWidget(section_title)

        self.fan_widgets = {}
        fans = self.find_fans()
        
        for fan_name, fan_path in fans.items():
            # Create card for each fan
            card = QFrame()
            card.setObjectName("card")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(20, 15, 20, 15)
            card_layout.setSpacing(20)
            
            # Fan name
            name_label = QLabel(fan_name)
            name_label.setStyleSheet(f"""
                font-size: 12pt;
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
                min-width: 150px;
            """)
            card_layout.addWidget(name_label)
            
            # Curve selector
            combo_container = QWidget()
            combo_layout = QHBoxLayout(combo_container)
            combo_layout.setContentsMargins(0, 0, 0, 0)
            combo_label = QLabel("Curve:")
            combo_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            combo = QComboBox()
            combo.setMinimumWidth(200)
            combo_layout.addWidget(combo_label)
            combo_layout.addWidget(combo)
            card_layout.addWidget(combo_container)
            
            card_layout.addStretch()
            
            # Temperature display
            temp_container = QWidget()
            temp_layout = QVBoxLayout(temp_container)
            temp_layout.setContentsMargins(0, 0, 0, 0)
            temp_layout.setSpacing(4)
            
            temp_label_title = QLabel("Temperature")
            temp_label_title.setObjectName("mutedLabel")
            temp_label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            temp_label = QLabel("--°C")
            temp_label.setObjectName("valueLabel")
            temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            temp_label.setStyleSheet(f"""
                font-size: 18pt;
                font-weight: 700;
                color: {Colors.SUCCESS};
            """)
            
            temp_layout.addWidget(temp_label_title)
            temp_layout.addWidget(temp_label)
            card_layout.addWidget(temp_container)
            
            # Speed display
            speed_container = QWidget()
            speed_layout = QVBoxLayout(speed_container)
            speed_layout.setContentsMargins(0, 0, 0, 0)
            speed_layout.setSpacing(4)
            
            speed_label_title = QLabel("Speed")
            speed_label_title.setObjectName("mutedLabel")
            speed_label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            speed_label = QLabel("--%")
            speed_label.setObjectName("valueLabel")
            speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            speed_label.setStyleSheet(f"""
                font-size: 18pt;
                font-weight: 700;
                color: {Colors.PRIMARY};
            """)
            
            speed_layout.addWidget(speed_label_title)
            speed_layout.addWidget(speed_label)
            card_layout.addWidget(speed_container)
            
            widgets = {
                "label": name_label,
                "combo": combo,
                "temp_label": temp_label,
                "speed_label": speed_label,
                "card": card
            }

            if fan_path == "nvidia-settings":
                min_speed_container = QWidget()
                min_speed_layout = QHBoxLayout(min_speed_container)
                min_speed_layout.setContentsMargins(0, 0, 0, 0)
                
                min_speed_label = QLabel("Min Speed:")
                min_speed_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
                
                min_speed_spinbox = QSpinBox()
                min_speed_spinbox.setRange(0, 100)
                min_speed_spinbox.setMinimumWidth(80)
                min_speed_spinbox.setValue(
                    self.config.get("hardware", {}).get("nvidia_min_fan_speed", 26)
                )
                
                min_speed_layout.addWidget(min_speed_label)
                min_speed_layout.addWidget(min_speed_spinbox)
                card_layout.addWidget(min_speed_container)
                widgets["min_speed_spinbox"] = min_speed_spinbox

            card_layout.addStretch()
            layout.addWidget(card)
            self.fan_widgets[fan_path] = widgets

        layout.addStretch()
        
        # Save button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 20)
        
        save_button = QPushButton("Save Hardware Configuration")
        save_button.setMinimumHeight(45)
        save_button.clicked.connect(self.save_config)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addStretch()
        
        layout.addWidget(button_container)

    def init_curves_tab(self):
        """Initialize the curves tab."""
        # Clear existing widgets
        if self.curves_tab.layout() is not None:
            while self.curves_tab.layout().count():
                item = self.curves_tab.layout().takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            self.curves_tab.setLayout(QHBoxLayout())
        
        layout = self.curves_tab.layout()

        # Curve list on the left
        self.curve_list = QListWidget()
        self.curve_list.currentItemChanged.connect(self.display_curve)
        layout.addWidget(self.curve_list, 1)

        # Curve editor on the right
        scroll = QScrollArea()
        layout.addWidget(scroll, 3)
        content = QWidget()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        curve_editor_layout = QVBoxLayout(content)

        # Plot
        self.curve_plot = FanCurvePlot()
        self.curve_plot.setMinimumHeight(400)
        self.curve_plot.pointsChanged.connect(self.on_curve_changed)
        curve_editor_layout.addWidget(self.curve_plot)

        # Curve name input
        curve_name_layout = QHBoxLayout()
        curve_editor_layout.addLayout(curve_name_layout)
        curve_name_layout.addWidget(QLabel("Curve Name:"))
        self.curve_name_input = QLineEdit()
        curve_name_layout.addWidget(self.curve_name_input)

        # Sensor Configuration
        sensor_config_layout = QVBoxLayout()
        curve_editor_layout.addLayout(sensor_config_layout)

        # Aggregation Function
        function_layout = QHBoxLayout()
        sensor_config_layout.addLayout(function_layout)
        function_layout.addWidget(QLabel("Aggregation Function:"))
        self.function_combo = QComboBox()
        self.function_combo.addItems(["Single", "Max", "Min", "Average"])
        function_layout.addWidget(self.function_combo)
        
        # Selected Sensors
        sensor_config_layout.addWidget(QLabel("Selected Sensors:"))
        self.selected_sensors_list = QListWidget()
        sensor_config_layout.addWidget(self.selected_sensors_list)

        # Add/Remove Sensors
        add_remove_layout = QHBoxLayout()
        sensor_config_layout.addLayout(add_remove_layout)
        self.available_sensors_combo = QComboBox()
        add_remove_layout.addWidget(self.available_sensors_combo)
        
        self.add_sensor_button = QPushButton("Add Sensor")
        self.remove_sensor_button = QPushButton("Remove Selected")
        add_remove_layout.addWidget(self.add_sensor_button)
        add_remove_layout.addWidget(self.remove_sensor_button)

        self.add_sensor_button.clicked.connect(self.add_selected_sensor)
        self.remove_sensor_button.clicked.connect(self.remove_selected_sensor)

        # Populate available sensors combo
        self.available_sensors_combo.addItem("Select a sensor to add", userData="") # Placeholder
        for sensor_name, sensor_path in self.sensors.items():
            self.available_sensors_combo.addItem(sensor_name, userData=sensor_path)

        # Buttons
        button_layout = QHBoxLayout()
        curve_editor_layout.addLayout(button_layout)
        
        new_curve_button = QPushButton("New Curve")
        new_curve_button.clicked.connect(self.new_curve)
        save_curve_button = QPushButton("Save Curve")
        save_curve_button.clicked.connect(self.save_curve)
        delete_curve_button = QPushButton("Delete Curve")
        delete_curve_button.clicked.connect(self.delete_curve)
        
        button_layout.addWidget(new_curve_button)
        button_layout.addWidget(save_curve_button)
        button_layout.addWidget(delete_curve_button)
        
        # Populate curve list
        self.curve_list.clear()
        for curve_name in self.config.get("curves", {}):
            self.curve_list.addItem(curve_name)

    def init_aliases_tab(self):
        """Initialize the aliases tab."""
        if self.aliases_tab.layout() is not None:
            while self.aliases_tab.layout().count():
                item = self.aliases_tab.layout().takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            self.aliases_tab.setLayout(QVBoxLayout())

        scroll = QScrollArea()
        self.aliases_tab.layout().addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        layout = QGridLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.alias_widgets = {}
        all_fans = find_fans()
        all_sensors = find_sensors()

        # Headers
        layout.addWidget(QLabel("<b>Device Path</b>"), 0, 0)
        layout.addWidget(QLabel("<b>Alias</b>"), 0, 1)
        layout.addWidget(QLabel("<b>Visible</b>"), 0, 2)
        
        i = 1
        for path in all_fans.keys():
            path_label = QLabel(path)
            alias_input = QLineEdit()
            visible_checkbox = QCheckBox()
            visible_checkbox.setChecked(
                path not in self.config.get("hidden_fans", [])
            )

            layout.addWidget(path_label, i, 0)
            layout.addWidget(alias_input, i, 1)
            layout.addWidget(visible_checkbox, i, 2)
            self.alias_widgets[path] = {
                "alias_input": alias_input,
                "visible_checkbox": visible_checkbox,
                "type": "fan"
            }
            i += 1

        for path in all_sensors.keys():
            path_label = QLabel(path)
            alias_input = QLineEdit()
            visible_checkbox = QCheckBox()
            visible_checkbox.setChecked(
                path not in self.config.get("hidden_sensors", [])
            )

            layout.addWidget(path_label, i, 0)
            layout.addWidget(alias_input, i, 1)
            layout.addWidget(visible_checkbox, i, 2)
            self.alias_widgets[path] = {
                "alias_input": alias_input,
                "visible_checkbox": visible_checkbox,
                "type": "sensor"
            }
            i += 1

        save_button = QPushButton("Save Aliases")
        save_button.clicked.connect(self.save_aliases)
        layout.addWidget(save_button, i, 0, 1, 3)

    def save_aliases(self):
        """Save alias configuration."""
        if "aliases" not in self.config:
            self.config["aliases"] = {}
        if "hidden_sensors" not in self.config:
            self.config["hidden_sensors"] = []
        if "hidden_fans" not in self.config:
            self.config["hidden_fans"] = []

        for path, widgets in self.alias_widgets.items():
            self.config["aliases"][path] = widgets["alias_input"].text()
            if widgets["type"] == "sensor":
                if not widgets["visible_checkbox"].isChecked():
                    if path not in self.config["hidden_sensors"]:
                        self.config["hidden_sensors"].append(path)
                else:
                    if path in self.config["hidden_sensors"]:
                        self.config["hidden_sensors"].remove(path)
            elif widgets["type"] == "fan":
                if not widgets["visible_checkbox"].isChecked():
                    if path not in self.config["hidden_fans"]:
                        self.config["hidden_fans"].append(path)
                else:
                    if path in self.config["hidden_fans"]:
                        self.config["hidden_fans"].remove(path)
        
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)
        
        self.update_ui_with_aliases()

    def add_selected_sensor(self):
        """Add the selected sensor from available sensors to the selected sensors list."""
        sensor_path = self.available_sensors_combo.currentData(Qt.ItemDataRole.UserRole)
        sensor_name = self.available_sensors_combo.currentText()
        if sensor_path and sensor_path not in [self.selected_sensors_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.selected_sensors_list.count())]:
            item = QListWidgetItem(sensor_name)
            item.setData(Qt.ItemDataRole.UserRole, sensor_path)
            self.selected_sensors_list.addItem(item)
            # Remove from available combo (optional, for UX)
            # self.available_sensors_combo.removeItem(self.available_sensors_combo.currentIndex())

    def remove_selected_sensor(self):
        """Remove the selected sensor from the selected sensors list."""
        current_item = self.selected_sensors_list.currentItem()
        if current_item:
            sensor_path = current_item.data(Qt.ItemDataRole.UserRole)
            sensor_name = current_item.text()
            self.selected_sensors_list.takeItem(self.selected_sensors_list.row(current_item))
            # Add back to available combo (optional, for UX)
            # self.available_sensors_combo.addItem(sensor_name, userData=sensor_path)


    def new_curve(self):
        """Create a new fan curve."""
        curve_name = self.curve_name_input.text().strip()
        if not curve_name:
            i = 1
            while f"New Curve {i}" in self.config.get("curves", {}):
                i += 1
            curve_name = f"New Curve {i}"
        
        if curve_name in self.config.get("curves", {}):
            return

        item = QListWidgetItem(curve_name)
        self.curve_list.addItem(item)
        self.curve_list.setCurrentItem(item)
        self.curve_plot.set_points([[20, 0], [80, 100]])
        self.curve_name_input.setText(curve_name)

        if "curves" not in self.config:
            self.config["curves"] = {}
        
        
        self.config["curves"][curve_name] = {
            "sensor": {"function": "single", "paths": []}, # Initialize with empty multi-sensor
            "points": [[20, 0], [80, 100]]
        }
        self.save_config()
        self.update_fan_curve_combos()

    def delete_curve(self):
        """Delete the selected curve."""
        current_item = self.curve_list.currentItem()
        if current_item:
            curve_name = current_item.text()
            if curve_name in self.config["curves"]:
                del self.config["curves"][curve_name]
                self.curve_list.takeItem(self.curve_list.row(current_item))
                self.save_config()
                self.update_fan_curve_combos()

    def display_curve(self, item):
        """Display the selected curve in the plot."""
        if not item:
            self.curve_name_input.clear()
            self.curve_plot.set_points([])
            self.selected_sensors_list.clear()
            self.function_combo.setCurrentIndex(0) # Set to "Single"
            return
        
        curve_name = item.text()
        self.curve_name_input.setText(curve_name)
        
        self.selected_sensors_list.clear()
        
        if curve_name in self.config.get("curves", {}):
            curve_data = self.config["curves"][curve_name]
            self.curve_plot.set_points(curve_data["points"])
            
            sensor_config = curve_data["sensor"]
            function_name = sensor_config.get("function", "single")
            sensor_paths = sensor_config.get("paths", [])

            # Set aggregation function
            index = self.function_combo.findText(function_name.capitalize())
            if index != -1:
                self.function_combo.setCurrentIndex(index)
            
            # Populate selected sensors list
            for path in sensor_paths:
                alias = self.get_alias(path)
                item = QListWidgetItem(alias)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.selected_sensors_list.addItem(item)

    def on_curve_changed(self):
        """Handle curve changes - auto-save the current curve."""
        current_item = self.curve_list.currentItem()
        if not current_item:
            return
            
        curve_name = current_item.text().strip()
        if not curve_name or curve_name not in self.config.get("curves", {}):
            return
        
        # Get current curve data from plot
        selected_function = self.function_combo.currentText().lower()
        selected_paths = []
        for i in range(self.selected_sensors_list.count()):
            item = self.selected_sensors_list.item(i)
            selected_paths.append(item.data(Qt.ItemDataRole.UserRole))
        
        sensor_config = {
            "function": selected_function,
            "paths": selected_paths
        }
        points = [[float(p[0]), float(p[1])] for p in self.curve_plot.points]
        
        # Update config immediately
        if "curves" not in self.config:
            self.config["curves"] = {}
        self.config["curves"][curve_name] = {
            "sensor": sensor_config,
            "points": points
        }
        
        # Save to file without restarting (auto-save on drag)
        self.save_config(restart=False)
    
    def save_curve(self):
        """Save the current curve."""
        curve_name = self.curve_name_input.text().strip()
        if not curve_name:
            return

        current_item = self.curve_list.currentItem()
        old_curve_name = current_item.text() if current_item else None

        if old_curve_name and old_curve_name != curve_name:
            if curve_name in self.config.get("curves", {}):
                return
            self.config["curves"][curve_name] = self.config["curves"].pop(old_curve_name)
            current_item.setText(curve_name)

        selected_function = self.function_combo.currentText().lower()
        selected_paths = []
        for i in range(self.selected_sensors_list.count()):
            item = self.selected_sensors_list.item(i)
            selected_paths.append(item.data(Qt.ItemDataRole.UserRole))
        
        sensor_config = {
            "function": selected_function,
            "paths": selected_paths
        }
        points = self.curve_plot.points

        if "curves" not in self.config:
            self.config["curves"] = {}
        self.config["curves"][curve_name] = {
            "sensor": sensor_config,
            "points": points
        }
        self.save_config()
        self.update_fan_curve_combos()

    def update_fan_curve_combos(self):
        """Update fan curve combo boxes with available curves."""
        curve_names = list(self.config.get("curves", {}).keys())
        for fan_path, widgets in self.fan_widgets.items():
            combo = widgets["combo"]
            current_selection = combo.currentText()
            combo.clear()
            combo.addItems(curve_names)
            if fan_path in self.config.get("fans", {}):
                curve_name = self.config["fans"][fan_path]
                combo.setCurrentText(curve_name)
            elif current_selection in curve_names:
                combo.setCurrentText(current_selection)

    def closeEvent(self, event):
        """Handle application close."""
        self.save_config()
        if self.controller_process:
            self.controller_process.terminate()
        if self.status_path.exists():
            self.status_path.unlink()
        event.accept()


def check_permissions() -> bool:
    """Check if we have write permissions for hardware control."""
    import os
    from pathlib import Path
    
    hwmon_path = Path("/sys/class/hwmon")
    if not hwmon_path.exists():
        return True  # No hwmon, assume OK
    
    for path in hwmon_path.glob("hwmon*/pwm*"):
        if path.name.endswith("_enable"):
            continue
        if not os.access(path, os.W_OK):
            print(f"No write permission for {path}.")
            print("Please run 'sudo ./setup_permissions.sh' to set the required permissions.")
            return False
    return True


def main():
    """Main entry point for the GUI."""
    if not check_permissions():
        sys.exit(1)

    app = QApplication(sys.argv)
    window = FanControlApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
