"""
Application Configuration
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class AppConfig:
    """Application configuration"""
    # Project paths
    project_root: Path = field(default_factory=lambda: Path(__file__).parent)
    output_dir: Path = field(default_factory=lambda: Path.home() / "VideoTranslatorOutput")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".video_translator_cache")
    
    # Video settings
    supported_video_formats: List[str] = field(default_factory=lambda: [
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'
    ])
    
    # OCR settings
    ocr_lang: str = 'ch'
    ocr_use_angle_cls: bool = True
    ocr_use_gpu: bool = True  # Auto-detect
    ocr_batch_size: int = 10
    ssim_threshold: float = 0.90  # Frame similarity threshold (0-1)
    min_text_height: int = 10  # Minimum text height in pixels
    
    # Translation settings
    translation_model: str = "opus-mt-zh-vi"  # MarianMT Chinese to Vietnamese
    translation_batch_size: int = 32
    
    # Subtitle settings
    subtitle_encoding: str = 'utf-8'
    max_subtitle_duration: float = 10.0  # Max seconds per subtitle
    min_subtitle_duration: float = 0.5   # Min seconds per subtitle
    merge_gap_threshold: float = 2.0     # Merge subtitles within this gap
    
    # Subtitle style (ASS)
    ass_font: str = "Arial"
    ass_font_size: int = 48
    ass_primary_color: str = "&H00FFFFFF"  # White
    ass_outline_color: str = "&H00000000"  # Black outline
    ass_outline: float = 2.0
    ass_margin_l: int = 50
    ass_margin_r: int = 50
    ass_margin_v: int = 20
    
    # UI settings
    ui_theme: str = 'dark'
    log_max_lines: int = 1000
    preview_fps: int = 30
    
    # Performance settings
    max_workers: int = 4  # Thread pool size
    frame_cache_size: int = 100
    translation_cache_size: int = 10000
    
    # FFmpeg settings
    ffmpeg_path: Optional[str] = None  # Auto-detect
    video_codec: str = 'libx264'
    audio_codec: str = 'aac'
    video_preset: str = 'medium'
    crf: int = 23  # Constant Rate Factor (quality)
    
    def __post_init__(self):
        """Create directories if they don't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_roi_config(self) -> Tuple[int, int, int, int]:
        """Get default ROI configuration (x, y, width, height)"""
        return (0, 0, 0, 0)
    
    def save_roi(self, x: int, y: int, w: int, h: int):
        """Save ROI to config"""
        self._last_roi = (x, y, w, h)
    
    def load_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """Load saved ROI"""
        return getattr(self, '_last_roi', None)


# Global config instance
config = AppConfig()
