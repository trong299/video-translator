"""
Main Window - Orchestrates all UI components and processing
"""
import sys
import time
import threading
from pathlib import Path
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QKeyEvent

from config import config
from utils.logger import get_logger
from utils.helpers import format_timestamp, ensure_dir
from utils.roi_manager import ROIManager

from .video_player import VideoPlayer
from .sidebar import Sidebar
from .subtitle_panel import SubtitlePanel
from .styles import STYLESHEET

from video import VideoReader
from ocr import PaddleOCRProcessor, FrameProcessor
from translator import OfflineTranslator
from subtitle import Subtitle, SubtitleSet, SubtitleProcessor, SubtitleExporter
from renderer import FFmpegRenderer


logger = get_logger(__name__)


class ProcessingWorker(QThread):
    """
    Background worker for processing tasks
    """
    
    progress_updated = pyqtSignal(str, int, int)  # (stage, current, total)
    log_message = pyqtSignal(str, str)  # (message, level)
    processing_complete = pyqtSignal(str, bool)  # (stage, success)
    result_ready = pyqtSignal(object)  # Processing result
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._stage = ""
    
    def run_ocr(self, video_path: Path, roi: Tuple[int, int, int, int]):
        """Run OCR processing"""
        self._is_running = True
        self._stage = "ocr"
        
        try:
            self.log_message.emit("Đang khởi tạo OCR...", "info")
            
            # Initialize OCR
            ocr_processor = PaddleOCRProcessor(use_gpu=True)
            frame_processor = FrameProcessor(ocr_processor, ssim_threshold=config.ssim_threshold)
            
            # Open video
            video_reader = VideoReader(video_path)
            total_frames = video_reader.info.frame_count
            
            self.log_message.emit(f"Tổng số frame: {total_frames}", "info")
            self.log_message.emit(f"FPS video: {video_reader.info.fps:.2f}", "info")
            
            # Process frames
            ocr_results = []
            start_time = time.time()
            
            frame_count = 0
            for frame_num, frame in video_reader.iter_frames():
                if not self._is_running:
                    break
                
                # Apply ROI
                x, y, w, h = roi
                roi_frame = frame[y:y+h, x:x+w]
                
                # OCR
                result = ocr_processor.process_image(roi_frame)
                
                if result.is_valid():
                    timestamp = video_reader.get_timestamp_at_frame(frame_num)
                    ocr_results.append({
                        'frame': frame_num,
                        'timestamp': timestamp,
                        'text': result.text,
                        'confidence': result.confidence
                    })
                    
                    self.log_message.emit(
                        f"[{format_timestamp(timestamp, 'timestamp')}] {result.text}",
                        "success"
                    )
                
                frame_count += 1
                
                if frame_count % 100 == 0:
                    self.progress_updated.emit("ocr", frame_count, total_frames)
            
            video_reader.release()
            
            ocr_time = time.time() - start_time
            self.log_message.emit(f"OCR hoàn tất trong {ocr_time:.1f}s", "success")
            
            self.result_ready.emit({'ocr_results': ocr_results, 'ocr_time': ocr_time})
            self.processing_complete.emit("ocr", True)
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            self.log_message.emit(f"Lỗi OCR: {e}", "error")
            self.processing_complete.emit("ocr", False)
        
        self._is_running = False
    
    def run_translate(self, ocr_results: List[dict]):
        """Run translation"""
        self._is_running = True
        self._stage = "translate"
        
        try:
            self.log_message.emit("Đang khởi tạo translator...", "info")
            
            # Initialize translator
            translator = OfflineTranslator()
            
            # Group similar texts
            subtitles = self._group_ocr_results(ocr_results)
            
            total = len(subtitles)
            self.log_message.emit(f"Số phụ đề cần dịch: {total}", "info")
            
            start_time = time.time()
            translated = 0
            
            for sub in subtitles:
                if not self._is_running:
                    break
                
                result = translator.translate(sub['text'])
                sub['translation'] = result.translated
                
                self.log_message.emit(
                    f"'{sub['text']}' → '{result.translated}'",
                    "info"
                )
                
                translated += 1
                if translated % 10 == 0:
                    self.progress_updated.emit("translate", translated, total)
            
            translate_time = time.time() - start_time
            self.log_message.emit(f"Dịch hoàn tất trong {translate_time:.1f}s", "success")
            
            self.result_ready.emit({'subtitles': subtitles, 'translate_time': translate_time})
            self.processing_complete.emit("translate", True)
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            self.log_message.emit(f"Lỗi dịch: {e}", "error")
            self.processing_complete.emit("translate", False)
        
        self._is_running = False
    
    def _group_ocr_results(self, ocr_results: List[dict]) -> List[dict]:
        """Group OCR results by similar text"""
        from rapidfuzz import fuzz
        
        if not ocr_results:
            return []
        
        groups = []
        current_group = None
        
        for result in ocr_results:
            if not current_group:
                current_group = {
                    'text': result['text'],
                    'start_time': result['timestamp'],
                    'end_time': result['timestamp'] + 2.0,  # Default duration
                    'confidence': result['confidence']
                }
            else:
                # Check similarity
                similarity = fuzz.ratio(current_group['text'], result['text']) / 100.0
                
                if similarity > 0.8 and (result['timestamp'] - current_group['end_time']) < 3.0:
                    # Merge
                    current_group['end_time'] = result['timestamp'] + 2.0
                    current_group['confidence'] = (current_group['confidence'] + result['confidence']) / 2
                else:
                    # New group
                    groups.append(current_group)
                    current_group = {
                        'text': result['text'],
                        'start_time': result['timestamp'],
                        'end_time': result['timestamp'] + 2.0,
                        'confidence': result['confidence']
                    }
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def stop(self):
        """Stop processing"""
        self._is_running = False


class MainWindow(QMainWindow):
    """
    Main application window
    """
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Video Translator - Chinese to Vietnamese")
        self.setMinimumSize(1200, 800)
        
        # State
        self.current_video: Optional[Path] = None
        self.current_roi: Optional[Tuple[int, int, int, int]] = None
        self.subtitle_set: Optional[SubtitleSet] = None
        self.processing_worker: Optional[ProcessingWorker] = None
        
        self._ocr_results = []
        self._processing_stats = {}
        
        # ROI manager
        self.roi_manager = ROIManager()
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        
        logger.info("MainWindow initialized")
    
    def _setup_ui(self):
        """Setup UI components"""
        self.setStyleSheet(STYLESHEET)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Splitters
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left - Sidebar
        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(280)
        splitter.addWidget(self.sidebar)
        
        # Center - Video Player
        self.video_player = VideoPlayer()
        splitter.addWidget(self.video_player)
        
        # Right - Subtitle Panel
        self.subtitle_panel = SubtitlePanel()
        self.subtitle_panel.setFixedWidth(350)
        splitter.addWidget(self.subtitle_panel)
        
        # Set splitter proportions
        splitter.setSizes([280, 800, 350])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Sẵn sàng")
    
    def _connect_signals(self):
        """Connect signals"""
        # Video player signals
        self.video_player.roi_changed.connect(self._on_roi_changed)
        self.video_player.state_changed.connect(self._on_playback_state_changed)
        
        # Sidebar signals
        self.sidebar.video_selected.connect(self._on_video_selected)
        self.sidebar.ocr_started.connect(self._on_start_ocr)
        self.sidebar.translate_started.connect(self._on_start_translate)
        self.sidebar.render_started.connect(self._on_start_render)
        self.sidebar.stop_requested.connect(self._on_stop)
        
        # Processing worker signals
        self.processing_worker = ProcessingWorker(self)
        self.processing_worker.progress_updated.connect(self._on_progress_updated)
        self.processing_worker.log_message.connect(self._on_log_message)
        self.processing_worker.processing_complete.connect(self._on_processing_complete)
        self.processing_worker.result_ready.connect(self._on_result_ready)
    
    def _on_video_selected(self, video_path: Path):
        """Handle video selection"""
        self.current_video = video_path
        
        # Load video
        if self.video_player.load_video(video_path):
            self.statusBar().showMessage(f"Đã mở: {video_path.name}")
            self.subtitle_panel.append_log(f"Video loaded: {video_path.name}", "success")
            
            # Check for saved ROI
            saved_roi = self.roi_manager.get_roi(str(video_path))
            if saved_roi:
                self.current_roi = (saved_roi.x, saved_roi.y, saved_roi.width, saved_roi.height)
                self.video_player.set_roi(self.current_roi)
                self.sidebar.set_roi(self.current_roi)
                self.subtitle_panel.append_log(f"ROI đã lưu: {self.current_roi}", "info")
    
    def _on_roi_changed(self, roi: Tuple[int, int, int, int]):
        """Handle ROI change"""
        self.current_roi = roi
        self.sidebar.set_roi(roi)
        
        # Save ROI
        if self.current_video:
            self.roi_manager.save_roi(str(self.current_video), *roi)
            self.subtitle_panel.append_log(f"ROI set: {roi}", "success")
    
    def _on_playback_state_changed(self, state: str):
        """Handle playback state change"""
        self.statusBar().showMessage(f"Trạng thái: {state}")
    
    def _on_start_ocr(self):
        """Start OCR processing"""
        if not self.current_video or not self.current_roi:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn video và vùng phụ đề trước")
            return
        
        # Reset
        self._ocr_results = []
        self.subtitle_panel.clear_subtitles()
        self.sidebar.reset_progress()
        
        # Start processing
        self.sidebar.set_processing(True)
        self.sidebar.set_status("Đang OCR...", "#f39c12")
        
        # Start worker
        self.processing_worker = ProcessingWorker(self)
        self.processing_worker.progress_updated.connect(self._on_progress_updated)
        self.processing_worker.log_message.connect(self._on_log_message)
        self.processing_worker.processing_complete.connect(self._on_processing_complete)
        self.processing_worker.result_ready.connect(self._on_result_ready)
        
        self.processing_worker.run_ocr(self.current_video, self.current_roi)
    
    def _on_start_translate(self):
        """Start translation"""
        if not self._ocr_results:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chạy OCR trước")
            return
        
        # Start translation
        self.sidebar.set_processing(True)
        self.sidebar.set_status("Đang dịch...", "#f39c12")
        
        # Start worker
        self.processing_worker = ProcessingWorker(self)
        self.processing_worker.progress_updated.connect(self._on_progress_updated)
        self.processing_worker.log_message.connect(self._on_log_message)
        self.processing_worker.processing_complete.connect(self._on_processing_complete)
        self.processing_worker.result_ready.connect(self._on_result_ready)
        
        self.processing_worker.run_translate(self._ocr_results)
    
    def _on_start_render(self):
        """Start video rendering"""
        if not self.subtitle_set or not self.current_video:
            QMessageBox.warning(self, "Cảnh báo", "Không có phụ đề để render")
            return
        
        # Confirm
        reply = QMessageBox.question(
            self, "Xác nhận",
            "Bắt đầu render video với phụ đề?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Start rendering in background
        self._render_video()
    
    def _render_video(self):
        """Render video with subtitles"""
        self.sidebar.set_processing(True)
        self.sidebar.set_status("Đang render...", "#f39c12")
        
        try:
            # Initialize renderer
            renderer = FFmpegRenderer()
            
            # Output paths
            output_dir = self.sidebar.output_dir
            ensure_dir(output_dir)
            
            output_video = output_dir / f"{self.current_video.stem}_subtitled.mp4"
            srt_file = output_dir / "subtitles.srt"
            ass_file = output_dir / "subtitles.ass"
            
            # Export subtitles
            exporter = SubtitleExporter()
            exporter.export_srt(self.subtitle_set, srt_file)
            exporter.export_ass(self.subtitle_set, ass_file)
            
            self.subtitle_panel.append_log("Đã xuất file phụ đề", "success")
            
            # Render video
            self.subtitle_panel.append_log("Bắt đầu render video...", "info")
            
            def progress_callback(progress):
                self.sidebar.update_render_progress(
                    int(progress.progress_percent), 100
                )
            
            success = renderer.render_with_ass(
                self.current_video,
                output_video,
                self.subtitle_set,
                progress_callback=progress_callback
            )
            
            if success:
                self.subtitle_panel.append_log(f"Render hoàn tất: {output_video}", "success")
                self.sidebar.set_status("Render thành công!", "#27ae60")
                
                QMessageBox.information(
                    self, "Thành công",
                    f"Video đã được render!\n\n{output_video}"
                )
            else:
                self.sidebar.set_status("Render thất bại", "#e74c3c")
                QMessageBox.critical(self, "Lỗi", "Render thất bại")
            
        except Exception as e:
            logger.error(f"Render error: {e}")
            self.sidebar.set_status(f"Lỗi: {e}", "#e74c3c")
            QMessageBox.critical(self, "Lỗi", f"Render lỗi: {e}")
        
        finally:
            self.sidebar.set_processing(False)
    
    def _on_stop(self):
        """Stop processing"""
        if self.processing_worker:
            self.processing_worker.stop()
        
        self.sidebar.set_processing(False)
        self.sidebar.set_status("Đã dừng", "#e74c3c")
        self.subtitle_panel.append_log("Đã dừng xử lý", "warning")
    
    def _on_progress_updated(self, stage: str, current: int, total: int):
        """Handle progress update"""
        if stage == "ocr":
            self.sidebar.update_ocr_progress(current, total)
        elif stage == "translate":
            self.sidebar.update_translate_progress(current, total)
    
    def _on_log_message(self, message: str, level: str):
        """Handle log message"""
        self.subtitle_panel.append_log(message, level)
    
    def _on_processing_complete(self, stage: str, success: bool):
        """Handle processing complete"""
        self.sidebar.set_processing(False)
        
        if success:
            self.sidebar.set_status(f"{stage.upper()} hoàn tất", "#27ae60")
        else:
            self.sidebar.set_status(f"{stage.upper()} thất bại", "#e74c3c")
    
    def _on_result_ready(self, result: dict):
        """Handle processing result"""
        if 'ocr_results' in result:
            self._ocr_results = result['ocr_results']
            self._processing_stats['ocr_time'] = result['ocr_time']
            
            self.subtitle_panel.append_log(
                f"OCR: {len(self._ocr_results)} kết quả",
                "success"
            )
            
            # Enable translate
            self.sidebar.enable_translate(True)
            
        elif 'subtitles' in result:
            # Create subtitle set
            self.subtitle_set = SubtitleSet()
            
            for i, sub_data in enumerate(result['subtitles']):
                sub = Subtitle(
                    index=i + 1,
                    start_time=sub_data['start_time'],
                    end_time=sub_data['end_time'],
                    text=sub_data['text'],
                    translation=sub_data.get('translation', ''),
                    confidence=sub_data.get('confidence', 1.0)
                )
                self.subtitle_set.add(sub)
            
            self._processing_stats['translate_time'] = result['translate_time']
            
            # Process subtitles
            processor = SubtitleProcessor()
            self.subtitle_set = processor.process(self.subtitle_set)
            
            # Load into panel
            self.subtitle_panel.load_subtitles(self.subtitle_set)
            
            # Export subtitles
            exporter = SubtitleExporter()
            output_dir = self.sidebar.output_dir
            ensure_dir(output_dir)
            
            exporter.export_all_formats(
                self.subtitle_set,
                output_dir,
                base_name="subtitles"
            )
            
            self.subtitle_panel.append_log(
                f"Dịch hoàn tất: {len(self.subtitle_set)} phụ đề",
                "success"
            )
            
            # Update stats
            self.subtitle_panel.set_stats(self._processing_stats)
            
            # Enable render
            self.sidebar.enable_render(True)
    
    def closeEvent(self, event):
        """Handle window close"""
        # Stop processing
        if self.processing_worker and self.processing_worker.isRunning():
            self.processing_worker.stop()
            self.processing_worker.wait()
        
        # Close video
        self.video_player.close_video()
        
        logger.info("Application closed")
        event.accept()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press"""
        if event.key() == Qt.Key.Key_Space:
            self.video_player.toggle_play_pause()
        elif event.key() == Qt.Key.Key_Escape:
            self.video_player.stop()
        elif event.key() == Qt.Key.Key_Left:
            # Seek backward 5 seconds
            current = self.video_player.get_current_timestamp()
            self.video_player.seek(max(0, current - 5))
        elif event.key() == Qt.Key.Key_Right:
            # Seek forward 5 seconds
            current = self.video_player.get_current_timestamp()
            info = self.video_player.get_video_info()
            if info:
                self.video_player.seek(min(info['duration'], current + 5))
