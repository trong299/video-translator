"""
Frame Cache for efficient frame retrieval
"""
import numpy as np
from collections import OrderedDict
from typing import Optional, Dict, Tuple, Any
import threading
import hashlib

from utils.logger import get_logger


logger = get_logger(__name__)


class FrameCache:
    """
    LRU cache for video frames
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize frame cache
        
        Args:
            max_size: Maximum number of frames to cache
        """
        self.max_size = max_size
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        
        logger.debug(f"FrameCache initialized with max_size={max_size}")
    
    def get(self, frame_number: int) -> Optional[np.ndarray]:
        """
        Get frame from cache
        
        Args:
            frame_number: Frame number
        
        Returns:
            Cached frame or None
        """
        with self._lock:
            if frame_number in self._cache:
                self._hits += 1
                # Move to end (most recently used)
                self._cache.move_to_end(frame_number)
                return self._cache[frame_number].copy()
            self._misses += 1
            return None
    
    def put(self, frame_number: int, frame: np.ndarray):
        """
        Put frame in cache
        
        Args:
            frame_number: Frame number
            frame: Frame data
        """
        with self._lock:
            if frame_number in self._cache:
                self._cache.move_to_end(frame_number)
            else:
                if len(self._cache) >= self.max_size:
                    # Remove oldest (first) item
                    self._cache.popitem(last=False)
                self._cache[frame_number] = frame.copy()
    
    def clear(self):
        """Clear all cached frames"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.debug("FrameCache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate
            }
    
    def resize(self, new_size: int):
        """Resize cache"""
        with self._lock:
            self.max_size = new_size
            while len(self._cache) > new_size:
                self._cache.popitem(last=False)
            logger.debug(f"FrameCache resized to {new_size}")


class ProcessedFrameCache:
    """
    Cache for processed/transformed frames (ROI crops, etc.)
    """
    
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self._hash_counts: Dict[str, int] = {}
        
        logger.debug(f"ProcessedFrameCache initialized with max_size={max_size}")
    
    @staticmethod
    def _make_key(frame_number: int, roi: Tuple[int, int, int, int]) -> str:
        """Generate cache key"""
        return f"{frame_number}_{roi[0]}_{roi[1]}_{roi[2]}_{roi[3]}"
    
    @staticmethod
    def _compute_image_hash(image: np.ndarray) -> str:
        """Compute perceptual hash of image"""
        # Resize to small size for hashing
        small = image.copy()
        if len(small.shape) == 3:
            # Convert to grayscale
            small = np.mean(small, axis=2).astype(np.uint8)
        
        # Resize to 8x8
        import cv2
        small = cv2.resize(small, (8, 8))
        
        # Compute hash
        data = small.tobytes()
        return hashlib.md5(data).hexdigest()
    
    def get(self, frame_number: int, roi: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Get processed frame from cache"""
        key = self._make_key(frame_number, roi)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key].copy()
            return None
    
    def put(self, frame_number: int, roi: Tuple[int, int, int, int], frame: np.ndarray):
        """Put processed frame in cache"""
        key = self._make_key(frame_number, roi)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    # Remove oldest
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                
                self._cache[key] = frame.copy()
                self._hash_counts[key] = 0
    
    def get_by_hash(self, img_hash: str) -> Optional[np.ndarray]:
        """Get frame by perceptual hash"""
        with self._lock:
            for key, frame in self._cache.items():
                if self._compute_image_hash(frame) == img_hash:
                    self._cache.move_to_end(key)
                    return frame.copy()
            return None
    
    def put_by_hash(self, img_hash: str, frame: np.ndarray):
        """Put frame with hash as key"""
        with self._lock:
            if img_hash in self._cache:
                self._cache.move_to_end(img_hash)
            else:
                if len(self._cache) >= self.max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                self._cache[img_hash] = frame.copy()
    
    def clear(self):
        """Clear all cached frames"""
        with self._lock:
            self._cache.clear()
            self._hash_counts.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size
            }


class MultiLevelCache:
    """
    Multi-level cache for frames:
    Level 1: Raw frame cache
    Level 2: Processed (ROI crop) frame cache
    """
    
    def __init__(self, raw_max_size: int = 50, processed_max_size: int = 200):
        self.raw_cache = FrameCache(max_size=raw_max_size)
        self.processed_cache = ProcessedFrameCache(max_size=processed_max_size)
        
        logger.info("MultiLevelCache initialized")
    
    def clear_all(self):
        """Clear all cache levels"""
        self.raw_cache.clear()
        self.processed_cache.clear()
        logger.info("All caches cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all cache levels"""
        return {
            'raw': self.raw_cache.get_stats(),
            'processed': self.processed_cache.get_stats()
        }
