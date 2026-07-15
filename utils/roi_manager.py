"""
ROI (Region of Interest) Manager
Handles saving, loading, and validating ROI selections
"""
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass, asdict

from .logger import get_logger


logger = get_logger(__name__)


@dataclass
class ROI:
    """Region of Interest data"""
    x: int
    y: int
    width: int
    height: int
    video_path: str
    
    def is_valid(self, video_width: int, video_height: int) -> bool:
        """Check if ROI is valid for video dimensions"""
        if self.x < 0 or self.y < 0:
            return False
        if self.x + self.width > video_width:
            return False
        if self.y + self.height > video_height:
            return False
        if self.width <= 0 or self.height <= 0:
            return False
        return True
    
    def normalize(self, video_width: int, video_height: int) -> 'ROI':
        """Ensure ROI is within video bounds"""
        x = max(0, min(self.x, video_width - 1))
        y = max(0, min(self.y, video_height - 1))
        width = min(self.width, video_width - x)
        height = min(self.height, video_height - y)
        return ROI(x, y, width, height, self.video_path)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ROI':
        return cls(**data)


class ROIManager:
    """Manager for ROI persistence and retrieval"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".video_translator_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "roi_cache.json"
        self._cache: Dict[str, ROI] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load ROI cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for video_path, roi_data in data.items():
                        self._cache[video_path] = ROI.from_dict(roi_data)
                logger.info(f"Loaded {len(self._cache)} ROI entries from cache")
            except Exception as e:
                logger.warning(f"Failed to load ROI cache: {e}")
    
    def _save_cache(self):
        """Save ROI cache to disk"""
        try:
            data = {path: roi.to_dict() for path, roi in self._cache.items()}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save ROI cache: {e}")
    
    def save_roi(self, video_path: str, x: int, y: int, width: int, height: int):
        """
        Save ROI for a video
        
        Args:
            video_path: Path to the video file
            x, y: Top-left corner coordinates
            width, height: ROI dimensions
        """
        roi = ROI(x, y, width, height, video_path)
        self._cache[video_path] = roi
        self._save_cache()
        logger.info(f"Saved ROI for {Path(video_path).name}: ({x}, {y}, {width}, {height})")
    
    def get_roi(self, video_path: str) -> Optional[ROI]:
        """
        Get saved ROI for a video
        
        Args:
            video_path: Path to the video file
            
        Returns:
            ROI if found, None otherwise
        """
        return self._cache.get(video_path)
    
    def delete_roi(self, video_path: str):
        """Delete saved ROI for a video"""
        if video_path in self._cache:
            del self._cache[video_path]
            self._save_cache()
            logger.info(f"Deleted ROI for {Path(video_path).name}")
    
    def clear_cache(self):
        """Clear all cached ROIs"""
        self._cache.clear()
        self._save_cache()
        logger.info("Cleared ROI cache")
    
    @staticmethod
    def validate_roi(x: int, y: int, width: int, height: int) -> Tuple[bool, str]:
        """
        Validate ROI parameters
        
        Returns:
            (is_valid, error_message)
        """
        if width < 20:
            return False, "ROI width must be at least 20 pixels"
        if height < 10:
            return False, "ROI height must be at least 10 pixels"
        if x < 0 or y < 0:
            return False, "ROI coordinates must be non-negative"
        return True, ""
