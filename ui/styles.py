"""
UI Stylesheet and theme configuration
"""

STYLESHEET = """
/* Main Window */
QMainWindow {
    background-color: #1e1e1e;
}

QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}

/* Buttons */
QPushButton {
    background-color: #2d5a8a;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 32px;
}

QPushButton:hover {
    background-color: #3a7abf;
}

QPushButton:pressed {
    background-color: #1e3d5c;
}

QPushButton:disabled {
    background-color: #404040;
    color: #808080;
}

QPushButton#primary {
    background-color: #27ae60;
}

QPushButton#primary:hover {
    background-color: #2ecc71;
}

QPushButton#danger {
    background-color: #c0392b;
}

QPushButton#danger:hover {
    background-color: #e74c3c;
}

/* Input Fields */
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
}

QLineEdit:focus {
    border: 1px solid #3498db;
}

/* Labels */
QLabel {
    color: #e0e0e0;
    background-color: transparent;
}

QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #3498db;
}

QLabel#subtitle {
    font-size: 14px;
    font-weight: bold;
}

/* Group Box */
QGroupBox {
    border: 1px solid #404040;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 15px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #3498db;
}

/* Slider */
QSlider::groove:horizontal {
    border: 1px solid #404040;
    height: 6px;
    background: #2d2d2d;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #3498db;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #5dade2;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #404040;
    border-radius: 4px;
    text-align: center;
    background-color: #2d2d2d;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #3498db;
    border-radius: 3px;
}

/* Scroll Area */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #404040;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #505050;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #2d2d2d;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #404040;
    border-radius: 5px;
    min-width: 30px;
}

/* Text Browser (Log) */
QTextBrowser {
    background-color: #1a1a1a;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 8px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 11px;
}

/* List Widget */
QListWidget {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #3498db;
}

QListWidget::item:hover {
    background-color: #3a5a7a;
}

/* Menu */
QMenuBar {
    background-color: #252525;
    border-bottom: 1px solid #404040;
}

QMenuBar::item {
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #3498db;
}

QMenu {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
}

QMenu::item {
    padding: 6px 24px;
}

QMenu::item:selected {
    background-color: #3498db;
}

/* Tooltip */
QToolTip {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    padding: 4px;
    border-radius: 4px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #404040;
    border-radius: 4px;
    background-color: #252525;
}

QTabBar::tab {
    background-color: #2d2d2d;
    padding: 8px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #3498db;
}

QTabBar::tab:hover {
    background-color: #3a5a7a;
}

/* Status Bar */
QStatusBar {
    background-color: #252525;
    border-top: 1px solid #404040;
}

QStatusBar QLabel {
    padding: 2px 8px;
}

/* Spin Box */
QSpinBox, QDoubleSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3498db;
}

/* Combo Box */
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 6px 10px;
}

QComboBox:hover {
    border: 1px solid #3498db;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    selection-background-color: #3498db;
}
"""

# Color scheme
COLORS = {
    'primary': '#3498db',
    'secondary': '#2ecc71',
    'danger': '#e74c3c',
    'warning': '#f39c12',
    'info': '#9b59b6',
    'dark': '#1e1e1e',
    'darker': '#151515',
    'light': '#e0e0e0',
    'muted': '#808080',
    'border': '#404040',
    'success': '#27ae60'
}

# Font settings
FONTS = {
    'family': 'Segoe UI',
    'mono': 'Consolas',
    'size_small': 10,
    'size_normal': 12,
    'size_large': 14,
    'size_xlarge': 16
}


def get_color(name: str) -> str:
    """Get color by name"""
    return COLORS.get(name, '#e0e0e0')


def get_font(size: str = 'normal') -> tuple:
    """Get font tuple"""
    return (FONTS['family'], FONTS[f'size_{size}'])
