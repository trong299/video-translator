"""
Sidebar widget with controls
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QLineEdit, QProgressBar,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal

from pathlib import Path
from typing import Optional

from utils.logger import get_logger


logger = get_logger(__name__)


class Sidebar(QWidget):
    """
    Left sidebar with controls
    """
    
    # Signals
    video_selected = pyqtSignal(Path)
    output_dir_selected = pyqtSignal(Path)
    ocr_started = pyqtSignal()
    translate_started = pyqtSignal()
    render_started = pyqtSignal()
    stop_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_video: Optional[Path] = None
        self.output_dir: Path = Path.home() / "VideoTranslatorOutput"
        self.is_processing = False
        
        self._setup_ui()
        
        logger.info("Sidebar initialized")
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Video Translator")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Video selection group
        video_group = QGroupBox("Video")
        video_layout = QVBoxLayout(video_group)
        
        self.btn_select_video = QPushButton("📂 Chọn Video")
        self.btn_select_video.setObjectName("primary")
        self.btn_select_video.clicked.connect(self._on_select_video)
        video_layout.addWidget(self.btn_select_video)
        
        self.video_path_label = QLabel("Chưa chọn video")
        self.video_path_label.setWordWrap(True)
        self.video_path_label.setStyleSheet("color: #808080; font-size: 11px;")
        video_layout.addWidget(self.video_path_label)
        
        layout.addWidget(video_group)
        
        # Output directory group
        output_group = QGroupBox("Thư mục Output")
        output_layout = QVBoxLayout(output_group)
        
        self.btn_select_output = QPushButton("📁 Chọn Thư mục")
        self.btn_select_output.clicked.connect(self._on_select_output)
        output_layout.addWidget(self.btn_select_output)
        
        self.output_path_label = QLabel(str(self.output_dir))
        self.output_path_label.setWordWrap(True)
        self.output_path_label.setStyleSheet("color: #808080; font-size: 11px;")
        output_layout.addWidget(self.output_path_label)
        
        layout.addWidget(output_group)
        
        # ROI Info
        self.roi_info_label = QLabel("Chưa chọn vùng phụ đề")
        self.roi_info_label.setWordWrap(True)
        self.roi_info_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                color: #f39c12;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.roi_info_label)
        
        layout.addStretch()
        
        # Action buttons
        btn_layout = QVBoxLayout()
        
        self.btn_start_ocr = QPushButton("🔍 Bắt đầu OCR")
        self.btn_start_ocr.setEnabled(False)
        self.btn_start_ocr.clicked.connect(self._on_start_ocr)
        btn_layout.addWidget(self.btn_start_ocr)
        
        self.btn_translate = QPushButton("🌐 Dịch Phụ Đề")
        self.btn_translate.setEnabled(False)
        self.btn_translate.clicked.connect(self._on_start_translate)
        btn_layout.addWidget(self.btn_translate)
        
        self.btn_render = QPushButton("🎬 Render Video")
        self.btn_render.setEnabled(False)
        self.btn_render.clicked.connect(self._on_start_render)
        btn_layout.addWidget(self.btn_render)
        
        self.btn_stop = QPushButton("⏹ Dừng")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.btn_stop)
        
        layout.addLayout(btn_layout)
        
        # Progress section
        progress_group = QGroupBox("Tiến Trình")
        progress_layout = QVBoxLayout(progress_group)
        
        self.ocr_progress = QProgressBar()
        self.ocr_progress.setFormat("OCR: %p%")
        progress_layout.addWidget(QLabel("OCR:"))
        progress_layout.addWidget(self.ocr_progress)
        
        self.translate_progress = QProgressBar()
        self.translate_progress.setFormat("Dịch: %p%")
        progress_layout.addWidget(QLabel("Dịch:"))
        progress_layout.addWidget(self.translate_progress)
        
        self.render_progress = QProgressBar()
        self.render_progress.setFormat("Render: %p%")
        progress_layout.addWidget(QLabel("Render:"))
        progress_layout.addWidget(self.render_progress)
        
        layout.addWidget(progress_group)
        
        # Status
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                color: #27ae60;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def _on_select_video(self):
        """Handle video selection"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Video",
            str(Path.home()),
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v)"
        )
        
        if file_path:
            self.current_video = Path(file_path)
            self.video_path_label.setText(self.current_video.name)
            self.video_selected.emit(self.current_video)
            self.btn_start_ocr.setEnabled(True)
            logger.info(f"Selected video: {self.current_video.name}")
    
    def _on_select_output(self):
        """Handle output directory selection"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Chọn Thư mục Output",
            str(self.output_dir)
        )
        
        if dir_path:
            self.output_dir = Path(dir_path)
            self.output_path_label.setText(str(self.output_dir))
            self.output_dir_selected.emit(self.output_dir)
            logger.info(f"Selected output directory: {self.output_dir}")
    
    def _on_start_ocr(self):
        """Handle OCR start"""
        if not self.current_video:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn video trước")
            return
        
        self.ocr_started.emit()
    
    def _on_start_translate(self):
        """Handle translate start"""
        self.translate_started.emit()
    
    def _on_start_render(self):
        """Handle render start"""
        self.render_started.emit()
    
    def _on_stop(self):
        """Handle stop"""
        self.stop_requested.emit()
    
    def set_roi(self, roi: tuple):
        """Update ROI info display"""
        x, y, w, h = roi
        self.roi_info_label.setText(f"Vùng phụ đề: ({x}, {y}) {w}x{h}")
    
    def clear_roi(self):
        """Clear ROI info"""
        self.roi_info_label.setText("Chưa chọn vùng phụ đề")
    
    def set_processing(self, is_processing: bool):
        """Set processing state"""
        self.is_processing = is_processing
        
        # Update button states
        self.btn_select_video.setEnabled(not is_processing)
        self.btn_select_output.setEnabled(not is_processing)
        self.btn_start_ocr.setEnabled(not is_processing and self.current_video is not None)
        self.btn_translate.setEnabled(not is_processing)
        self.btn_render.setEnabled(not is_processing)
        self.btn_stop.setEnabled(is_processing)
    
    def update_ocr_progress(self, current: int, total: int):
        """Update OCR progress"""
        if total > 0:
            percent = int(current / total * 100)
            self.ocr_progress.setValue(percent)
    
    def update_translate_progress(self, current: int, total: int):
        """Update translate progress"""
        if total > 0:
            percent = int(current / total * 100)
            self.translate_progress.setValue(percent)
    
    def update_render_progress(self, current: int, total: int):
        """Update render progress"""
        if total > 0:
            percent = int(current / total * 100)
            self.render_progress.setValue(percent)
    
    def set_status(self, message: str, color: str = "#27ae60"):
        """Set status message"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                color: {color};
                font-weight: bold;
            }}
        """)
    
    def enable_translate(self, enabled: bool):
        """Enable/disable translate button"""
        self.btn_translate.setEnabled(enabled)
    
    def enable_render(self, enabled: bool):
        """Enable/disable render button"""
        self.btn_render.setEnabled(enabled)
    
    def reset_progress(self):
        """Reset all progress bars"""
        self.ocr_progress.setValue(0)
        self.translate_progress.setValue(0)
        self.render_progress.setValue(0)
