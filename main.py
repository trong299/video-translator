#!/usr/bin/env python3
"""
Video Translator - Chinese to Vietnamese
Main entry point

A desktop application for translating video subtitles from Chinese to Vietnamese.
Features:
- Video playback with ROI selection
- OCR using PaddleOCR
- Offline translation using MarianMT
- Subtitle export (SRT, ASS)
- Video rendering with burned subtitles
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# CRITICAL: Set up library paths BEFORE importing PyQt6
home_lib = Path.home() / ".local" / "lib"
if home_lib.exists():
    os.environ['LD_LIBRARY_PATH'] = str(home_lib) + ':' + os.environ.get('LD_LIBRARY_PATH', '')
    # Preload EGL library
    egl_lib = home_lib / "libEGL.so.1"
    if egl_lib.exists():
        try:
            import ctypes
            ctypes.CDLL(str(egl_lib))
        except:
            pass

# Check for EGL and set platform if needed
if not Path('/usr/lib/x86_64-linux-gnu/libEGL.so.1').exists():
    if not (home_lib / "libEGL.so.1").exists():
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
elif os.environ.get('DISPLAY', '') == '':
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from config import config
from utils.logger import setup_logger, get_logger
from utils.helpers import check_ffmpeg_available
from ui.main_window import MainWindow


def check_dependencies():
    """Check if required dependencies are available"""
    missing = []
    
    # Check FFmpeg
    ffmpeg_available, ffmpeg_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        missing.append("FFmpeg")
    
    # Check Python packages
    required_packages = [
        'cv2',
        'paddleocr',
        'paddle',
        'numpy',
        'transformers',
        'torch'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing


def main():
    """Main entry point"""
    # Setup logging
    setup_logger(log_level="INFO")
    logger = get_logger(__name__)
    
    logger.info("=" * 50)
    logger.info("Video Translator - Chinese to Vietnamese")
    logger.info("=" * 50)
    
    # Check dependencies
    logger.info("Checking dependencies...")
    missing = check_dependencies()
    
    if missing:
        error_msg = "Thiếu các thư viện sau:\n\n" + "\n".join(f"  - {p}" for p in missing)
        error_msg += "\n\nVui lòng cài đặt: pip install -r requirements.txt"
        
        print(error_msg)
        
        # Try to show GUI error if possible
        try:
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Thiếu Dependencies", error_msg)
        except:
            pass
        
        sys.exit(1)
    
    # Check FFmpeg specifically
    ffmpeg_available, ffmpeg_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        logger.warning("FFmpeg not found. Video rendering will not be available.")
        logger.warning("Please install FFmpeg from: https://ffmpeg.org/download.html")
    
    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {config.output_dir}")
    
    # Create application
    # Use offscreen platform if EGL is not available
    import os
    from pathlib import Path
    
    # Add local lib directory to library path
    local_lib = project_root / "lib"
    if local_lib.exists():
        os.environ['LD_LIBRARY_PATH'] = str(local_lib) + ':' + os.environ.get('LD_LIBRARY_PATH', '')
    
    # Check for EGL library
    egl_path = '/usr/lib/x86_64-linux-gnu/libEGL.so.1'
    if not Path(egl_path).exists():
        # Try local symlink
        local_egl = local_lib / "libEGL.so.1"
        if local_egl.exists():
            egl_path = str(local_egl)
    
    if not Path(egl_path).exists():
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        logger.info("Using offscreen Qt platform (no display)")
    
    app = QApplication(sys.argv)
    app.setApplicationName("Video Translator")
    app.setOrganizationName("VideoTranslator")
    
    # Enable high DPI (PyQt6 handles this automatically, no need to set attributes)
    
    # Create main window
    window = MainWindow()
    window.show()
    
    logger.info("Application started successfully")
    
    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
