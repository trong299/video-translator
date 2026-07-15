"""
Video Player Widget with ROI selection
"""
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QKeyEvent

from pathlib import Path
from typing import Optional, Tuple, Callable

from utils.logger import get_logger
from video.video_reader import VideoReader


logger = get_logger(__name__)


class ROISelectionOverlay(QWidget):
    """Overlay for ROI selection on video frame"""
    
    selection_changed = pyqtSignal(tuple)  # (x, y, w, h)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        
        self.is_selecting = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.current_roi = None  # (x, y, w, h)
    
    def set_roi(self, roi: Optional[Tuple[int, int, int, int]]):
        """Set current ROI"""
        if roi:
            x, y, w, h = roi
            self.current_roi = roi
            self.start_point = QPoint(x, y)
            self.end_point = QPoint(x + w, y + h)
        else:
            self.current_roi = None
            self.start_point = QPoint()
            self.end_point = QPoint()
        self.update()
    
    def clear_roi(self):
        """Clear ROI selection"""
        self.current_roi = None
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = True
            self.start_point = event.pos()
            self.end_point = event.pos()
    
    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_point = event.pos()
            
            # Calculate ROI
            x = min(self.start_point.x(), self.end_point.x())
            y = min(self.start_point.y(), self.end_point.y())
            w = abs(self.end_point.x() - self.start_point.x())
            h = abs(self.end_point.y() - self.start_point.y())
            
            if w > 20 and h > 10:  # Minimum size
                self.current_roi = (x, y, w, h)
                self.selection_changed.emit(self.current_roi)
            
            self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if not self.current_roi and not self.is_selecting:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Selection rectangle
        if self.is_selecting:
            pen = QPen(QColor(46, 204, 113), 2)
            painter.setPen(pen)
            rect = self._get_rect(self.start_point, self.end_point)
            painter.drawRect(rect)
            
            # Fill with semi-transparent
            fill_color = QColor(46, 204, 113, 50)
            painter.fillRect(rect, fill_color)
        
        # Current ROI
        if self.current_roi:
            pen = QPen(QColor(52, 152, 219), 3)
            painter.setPen(pen)
            x, y, w, h = self.current_roi
            painter.drawRect(QRect(x, y, w, h))
            
            # Draw corner handles
            handle_color = QColor(231, 76, 60)
            painter.setPen(handle_color)
            painter.setBrush(handle_color)
            
            corners = [(x, y), (x+w, y), (x, y+h), (x+w, y+h)]
            for cx, cy in corners:
                painter.drawEllipse(cx-4, cy-4, 8, 8)
    
    def _get_rect(self, p1: QPoint, p2: QPoint) -> QRect:
        """Get rectangle from two points"""
        return QRect(
            min(p1.x(), p2.x()),
            min(p1.y(), p2.y()),
            abs(p2.x() - p1.x()),
            abs(p2.y() - p1.y())
        )


class VideoPlayer(QWidget):
    """
    Video player widget with playback controls and ROI selection
    """
    
    # Signals
    roi_changed = pyqtSignal(tuple)  # (x, y, w, h)
    position_changed = pyqtSignal(float)  # Current timestamp
    duration_changed = pyqtSignal(float)  # Total duration
    state_changed = pyqtSignal(str)  # 'playing', 'paused', 'stopped'
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.video_reader: Optional[VideoReader] = None
        self.video_path: Optional[Path] = None
        self.is_playing = False
        self.is_roi_mode = True  # Enable ROI selection when loading video
        
        self._current_frame = 0
        self._frame_labels = []
        
        # Timers
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self._on_playback_tick)
        
        self._setup_ui()
        self._connect_signals()
        
        logger.info("VideoPlayer initialized")
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Video display area
        self.video_container = QWidget()
        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet("background-color: #000;")
        self.video_label.setText("Chưa có video\n\nNhấn 'Chọn Video' để bắt đầu")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # ROI overlay
        self.roi_overlay = ROISelectionOverlay(self.video_label)
        
        self.video_layout.addWidget(self.video_label)
        
        # Controls container
        controls_container = QWidget()
        controls_container.setFixedHeight(100)
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        
        # Timeline slider
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setEnabled(False)
        controls_layout.addWidget(self.timeline_slider)
        
        # Time labels and controls
        controls_row = QHBoxLayout()
        
        self.time_label = QLabel("00:00:00")
        controls_row.addWidget(self.time_label)
        
        controls_row.addStretch()
        
        # Playback buttons
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setFixedSize(40, 40)
        self.btn_play_pause.setEnabled(False)
        controls_row.addWidget(self.btn_play_pause)
        
        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(40, 40)
        self.btn_stop.setEnabled(False)
        controls_row.addWidget(self.btn_stop)
        
        controls_row.addStretch()
        
        self.duration_label = QLabel("00:00:00")
        controls_row.addWidget(self.duration_label)
        
        controls_layout.addLayout(controls_row)
        
        layout.addWidget(self.video_container)
        layout.addWidget(controls_container)
    
    def _connect_signals(self):
        """Connect signals and slots"""
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop)
        self.timeline_slider.sliderMoved.connect(self._on_sliderMoved)
        self.timeline_slider.sliderPressed.connect(self._on_sliderPressed)
        self.timeline_slider.sliderReleased.connect(self._on_sliderReleased)
        self.roi_overlay.selection_changed.connect(self._on_roi_changed)
    
    def load_video(self, video_path: Path) -> bool:
        """
        Load video file
        
        Args:
            video_path: Path to video file
        
        Returns:
            True if successful
        """
        try:
            # Close previous video
            self.close_video()
            
            # Open new video
            self.video_reader = VideoReader(video_path)
            self.video_path = video_path
            
            # Update UI
            self.timeline_slider.setEnabled(True)
            self.btn_play_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            
            # Show first frame
            self._display_frame(0)
            
            # Reset ROI
            self.roi_overlay.clear_roi()
            
            # Update duration
            duration = self.video_reader.info.duration
            self.duration_changed.emit(duration)
            self.duration_label.setText(self._format_time(duration))
            
            logger.info(f"Loaded video: {video_path.name}")
            
            # Enable ROI mode
            self.is_roi_mode = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể mở video: {e}")
            return False
    
    def close_video(self):
        """Close current video"""
        self.stop()
        
        if self.video_reader:
            self.video_reader.release()
            self.video_reader = None
        
        self.video_path = None
        self._current_frame = 0
        self.roi_overlay.clear_roi()
        
        # Reset UI
        self.video_label.setText("Chưa có video\n\nNhấn 'Chọn Video' để bắt đầu")
        self.timeline_slider.setEnabled(False)
        self.btn_play_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.time_label.setText("00:00:00")
        self.duration_label.setText("00:00:00")
    
    def _display_frame(self, frame_number: int):
        """Display frame at specific position"""
        if not self.video_reader:
            return
        
        ret, frame = self.video_reader.read_at(frame_number)
        
        if ret and frame is not None:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QPixmap
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Scale to fit label
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)
            
            # Update ROI overlay size
            self.roi_overlay.setGeometry(self.video_label.rect())
            
            self._current_frame = frame_number
    
    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if self.is_playing:
            self.pause()
        else:
            self.play()
    
    def play(self):
        """Start playback"""
        if not self.video_reader:
            return
        
        self.is_playing = True
        self.btn_play_pause.setText("⏸")
        self.state_changed.emit('playing')
        
        # Start timer
        fps = self.video_reader.info.fps
        interval = int(1000 / fps) if fps > 0 else 33
        self.playback_timer.start(interval)
    
    def pause(self):
        """Pause playback"""
        self.is_playing = False
        self.btn_play_pause.setText("▶")
        self.playback_timer.stop()
        self.state_changed.emit('paused')
    
    def stop(self):
        """Stop playback"""
        self.pause()
        self._current_frame = 0
        self._display_frame(0)
        self.timeline_slider.setValue(0)
        self.state_changed.emit('stopped')
    
    def seek(self, timestamp: float):
        """Seek to specific timestamp"""
        if not self.video_reader:
            return
        
        frame_number = int(timestamp * self.video_reader.info.fps)
        frame_number = max(0, min(frame_number, self.video_reader.info.frame_count - 1))
        
        self._display_frame(frame_number)
        self._current_frame = frame_number
        
        # Update slider
        progress = frame_number / max(1, self.video_reader.info.frame_count - 1)
        self.timeline_slider.setValue(int(progress * 1000))
        
        self.position_changed.emit(timestamp)
        self.time_label.setText(self._format_time(timestamp))
    
    def get_current_timestamp(self) -> float:
        """Get current playback timestamp"""
        if not self.video_reader:
            return 0
        return self._current_frame / self.video_reader.info.fps
    
    def get_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current ROI"""
        return self.roi_overlay.current_roi
    
    def set_roi(self, roi: Tuple[int, int, int, int]):
        """Set ROI"""
        self.roi_overlay.set_roi(roi)
        self.roi_changed.emit(roi)
    
    def clear_roi(self):
        """Clear ROI"""
        self.roi_overlay.clear_roi()
    
    def enable_roi_mode(self, enabled: bool):
        """Enable/disable ROI selection mode"""
        self.is_roi_mode = enabled
        self.roi_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)
    
    def _on_playback_tick(self):
        """Playback timer tick"""
        if not self.video_reader:
            return
        
        # Advance frame
        next_frame = self._current_frame + 1
        
        if next_frame >= self.video_reader.info.frame_count:
            # Reached end
            self.stop()
            return
        
        self._display_frame(next_frame)
        
        # Update slider
        progress = next_frame / max(1, self.video_reader.info.frame_count - 1)
        self.timeline_slider.setValue(int(progress * 1000))
        
        # Update time
        timestamp = next_frame / self.video_reader.info.fps
        self.time_label.setText(self._format_time(timestamp))
        self.position_changed.emit(timestamp)
    
    def _on_sliderMoved(self, value):
        """Slider moved"""
        if not self.video_reader:
            return
        
        progress = value / 1000
        frame_number = int(progress * (self.video_reader.info.frame_count - 1))
        timestamp = frame_number / self.video_reader.info.fps
        
        self._display_frame(frame_number)
        self.time_label.setText(self._format_time(timestamp))
    
    def _on_sliderPressed(self):
        """Slider pressed - pause playback"""
        if self.is_playing:
            self.was_playing = True
            self.pause()
        else:
            self.was_playing = False
    
    def _on_sliderReleased(self):
        """Slider released - resume if was playing"""
        if getattr(self, 'was_playing', False):
            self.play()
    
    def _on_roi_changed(self, roi: Tuple[int, int, int, int]):
        """ROI selection changed"""
        self.roi_changed.emit(roi)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def resizeEvent(self, event):
        """Handle resize"""
        super().resizeEvent(event)
        
        # Resize ROI overlay
        if self.video_label.pixmap():
            self.roi_overlay.setGeometry(self.video_label.rect())
    
    def get_video_info(self):
        """Get video info"""
        if self.video_reader:
            return {
                'width': self.video_reader.info.width,
                'height': self.video_reader.info.height,
                'fps': self.video_reader.info.fps,
                'frame_count': self.video_reader.info.frame_count,
                'duration': self.video_reader.info.duration,
                'path': self.video_path
            }
        return None
