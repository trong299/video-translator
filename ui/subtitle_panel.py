"""
Subtitle Panel - displays subtitles and log
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QGroupBox, QSplitter, QTabWidget, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor

from typing import List, Optional, TYPE_CHECKING

from utils.logger import get_logger
from utils.helpers import format_timestamp

if TYPE_CHECKING:
    from subtitle import Subtitle, SubtitleSet


logger = get_logger(__name__)


class LogWidget(QTextBrowser):
    """
    Real-time log display widget
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumBlockCount(1000)  # Keep last 1000 lines
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup syntax highlighting"""
        pass
    
    def append_log(self, message: str, level: str = "info"):
        """Append log message with color coding"""
        # Create text format
        fmt = QTextCharFormat()
        
        colors = {
            'info': '#3498db',    # Blue
            'success': '#27ae60', # Green
            'warning': '#f39c12', # Yellow/Orange
            'error': '#e74c3c',   # Red
            'debug': '#9b59b6'    # Purple
        }
        
        color = colors.get(level, '#e0e0e0')
        fmt.setForeground(QColor(color))
        
        # Insert with format
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message, fmt)
        cursor.insertText('\n')
        
        # Scroll to bottom
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def clear_logs(self):
        """Clear all logs"""
        self.clear()
    
    def get_logs(self) -> List[str]:
        """Get all log messages"""
        return self.toPlainText().split('\n')


class SubtitleTable(QTableWidget):
    """
    Table view for subtitles
    """
    
    subtitle_selected = pyqtSignal(int)  # Subtitle index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup table UI"""
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "Thời gian", "Tiếng Trung", "Tiếng Việt"])
        
        # Stretch columns
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Connect signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            index_item = self.item(row, 0)
            if index_item:
                self.subtitle_selected.emit(int(index_item.text()))
    
    def load_subtitles(self, subtitle_set: 'SubtitleSet'):
        """Load subtitles into table"""
        self.setRowCount(0)
        
        for sub in subtitle_set.subtitles:
            self.insertRow(sub.index - 1)
            
            # Index
            self.setItem(sub.index - 1, 0, QTableWidgetItem(str(sub.index)))
            
            # Time
            start = format_timestamp(sub.start_time, 'timestamp')
            end = format_timestamp(sub.end_time, 'timestamp')
            self.setItem(sub.index - 1, 1, QTableWidgetItem(f"{start} → {end}"))
            
            # Original text
            self.setItem(sub.index - 1, 2, QTableWidgetItem(sub.text))
            
            # Translation
            self.setItem(sub.index - 1, 3, QTableWidgetItem(sub.translation))
    
    def clear_subtitles(self):
        """Clear table"""
        self.setRowCount(0)


class SubtitlePreview(QWidget):
    """
    Preview widget for subtitle display
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 2px solid #404040;
                border-radius: 8px;
                color: #ffffff;
                font-size: 24px;
                padding: 20px;
            }
        """)
        
        layout.addWidget(self.preview_label)
        
        # Time label
        self.time_label = QLabel("00:00:00 → 00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: #808080; font-size: 12px;")
        
        layout.addWidget(self.time_label)
        layout.addStretch()
    
    def show_subtitle(self, subtitle: 'Subtitle'):
        """Show subtitle preview"""
        # Show translation or original
        text = subtitle.translation if subtitle.translation else subtitle.text
        self.preview_label.setText(text)
        
        # Update time
        start = format_timestamp(subtitle.start_time, 'timestamp')
        end = format_timestamp(subtitle.end_time, 'timestamp')
        self.time_label.setText(f"{start} → {end}")
    
    def clear(self):
        """Clear preview"""
        self.preview_label.setText("Không có phụ đề")
        self.time_label.setText("")


class SubtitlePanel(QWidget):
    """
    Right panel with subtitle display and logs
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
        logger.info("SubtitlePanel initialized")
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        
        # Subtitle tab
        subtitle_tab = QWidget()
        subtitle_layout = QVBoxLayout(subtitle_tab)
        
        # Stats row
        stats_layout = QHBoxLayout()
        
        self.total_label = QLabel("Tổng: 0")
        self.total_label.setStyleSheet("color: #3498db; font-weight: bold;")
        stats_layout.addWidget(self.total_label)
        
        stats_layout.addStretch()
        
        self.removed_label = QLabel("Đã bỏ: 0")
        self.removed_label.setStyleSheet("color: #e74c3c;")
        stats_layout.addWidget(self.removed_label)
        
        subtitle_layout.addLayout(stats_layout)
        
        # Subtitle table
        self.subtitle_table = SubtitleTable()
        self.subtitle_table.subtitle_selected.connect(self._on_subtitle_selected)
        subtitle_layout.addWidget(self.subtitle_table)
        
        # Preview
        self.preview = SubtitlePreview()
        subtitle_layout.addWidget(self.preview)
        
        self.tabs.addTab(subtitle_tab, "📝 Phụ Đề")
        
        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        # Log controls
        log_controls = QHBoxLayout()
        
        self.btn_clear_log = QPushButton("🗑 Xóa Log")
        self.btn_clear_log.clicked.connect(self.clear_logs)
        log_controls.addWidget(self.btn_clear_log)
        
        log_controls.addStretch()
        
        log_layout.addLayout(log_controls)
        
        # Log widget
        self.log_widget = LogWidget()
        self.log_widget.setMinimumHeight(300)
        log_layout.addWidget(self.log_widget)
        
        self.tabs.addTab(log_tab, "📋 Log")
        
        layout.addWidget(self.tabs)
        
        # Statistics panel
        stats_group = QGroupBox("Thống Kê")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Chưa có dữ liệu")
        self.stats_label.setStyleSheet("font-size: 11px; color: #808080;")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
    
    def _on_subtitle_selected(self, index: int):
        """Handle subtitle selection"""
        # Find subtitle by index
        for i in range(self.subtitle_table.rowCount()):
            item = self.subtitle_table.item(i, 0)
            if item and int(item.text()) == index:
                # Get text from columns
                original = self.subtitle_table.item(i, 2).text()
                translation = self.subtitle_table.item(i, 3).text()
                
                # Emit signal with subtitle info
                break
    
    def append_log(self, message: str, level: str = "info"):
        """Append log message"""
        self.log_widget.append_log(message, level)
    
    def clear_logs(self):
        """Clear all logs"""
        self.log_widget.clear_logs()
    
    def load_subtitles(self, subtitle_set: 'SubtitleSet'):
        """Load subtitles into panel"""
        self.subtitle_table.load_subtitles(subtitle_set)
        self.total_label.setText(f"Tổng: {len(subtitle_set)}")
        
        # Update stats
        stats = subtitle_set.get_stats()
        if stats:
            avg_duration = stats.get('avg_duration', 0)
            self.stats_label.setText(
                f"Thời lượng TB: {avg_duration:.1f}s | "
                f"Độ chính xác TB: {stats.get('avg_confidence', 0)*100:.0f}%"
            )
    
    def clear_subtitles(self):
        """Clear subtitles"""
        self.subtitle_table.clear_subtitles()
        self.preview.clear()
        self.total_label.setText("Tổng: 0")
        self.removed_label.setText("Đã bỏ: 0")
        self.stats_label.setText("Chờ xử lý...")
    
    def set_stats(self, stats: dict):
        """Set statistics display"""
        if not stats:
            return
        
        lines = []
        
        if 'total_frames' in stats:
            lines.append(f"Tổng frame: {stats['total_frames']}")
        if 'unique_frames' in stats:
            lines.append(f"Frame duy nhất: {stats['unique_frames']}")
        if 'skipped_frames' in stats:
            lines.append(f"Frame bỏ qua: {stats['skipped_frames']}")
        if 'ocr_time' in stats:
            lines.append(f"Thời gian OCR: {stats['ocr_time']:.1f}s")
        if 'translate_time' in stats:
            lines.append(f"Thời gian dịch: {stats['translate_time']:.1f}s")
        if 'render_time' in stats:
            lines.append(f"Thời gian render: {stats['render_time']:.1f}s")
        if 'fps' in stats:
            lines.append(f"FPS xử lý: {stats['fps']:.1f}")
        
        self.stats_label.setText(" | ".join(lines))
    
    def update_removed_count(self, count: int):
        """Update removed subtitle count"""
        self.removed_label.setText(f"Đã bỏ: {count}")
