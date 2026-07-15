"""
UI Module for Video Translator Application (PyQt6)
"""
from .main_window import MainWindow
from .video_player import VideoPlayer
from .sidebar import Sidebar
from .subtitle_panel import SubtitlePanel
from .styles import STYLESHEET

__all__ = ['MainWindow', 'VideoPlayer', 'Sidebar', 'SubtitlePanel', 'STYLESHEET']
