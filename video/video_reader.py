"""
Video Reader using OpenCV
Provides efficient frame reading and batch processing
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Iterator, List, Tuple, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class VideoInfo:
    """Video metadata"""
    path: Path
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float
    fourcc: str
    
    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 16/9


class VideoReader:
    """
    Efficient video reader with frame caching and batch processing
    """
    
    def __init__(
        self, 
        video_path: Path,
        batch_size: int = 10,
        cache_size: int = 100
    ):
        """
        Initialize video reader
        
        Args:
            video_path: Path to video file
            batch_size: Number of frames to read per batch
            cache_size: Maximum number of frames to cache
        """
        self.video_path = Path(video_path)
        self.batch_size = batch_size
        
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        
        self._info = self._extract_info()
        self._current_frame = 0
        self._lock = threading.Lock()
        
        logger.info(f"VideoReader initialized: {self.video_path.name} "
                   f"({self._info.width}x{self._info.height}, {self._info.fps:.2f}fps)")
    
    def _extract_info(self) -> VideoInfo:
        """Extract video information"""
        return VideoInfo(
            path=self.video_path,
            width=int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=self.cap.get(cv2.CAP_PROP_FPS),
            frame_count=int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            duration=self.cap.get(cv2.CAP_PROP_FRAME_COUNT) / self.cap.get(cv2.CAP_PROP_FPS),
            fourcc=self._fourcc_to_str(int(self.cap.get(cv2.CAP_PROP_FOURCC)))
        )
    
    @staticmethod
    def _fourcc_to_str(fourcc: int) -> str:
        """Convert fourcc int to string"""
        return "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    
    @property
    def info(self) -> VideoInfo:
        """Get video information"""
        return self._info
    
    @property
    def position(self) -> int:
        """Get current frame position"""
        return int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
    
    @position.setter
    def position(self, frame_number: int):
        """Set current frame position"""
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self._current_frame = frame_number
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read single frame
        
        Returns:
            (success, frame)
        """
        with self._lock:
            ret, frame = self.cap.read()
            if ret:
                self._current_frame += 1
            return ret, frame
    
    def read_batch(self, count: Optional[int] = None) -> List[np.ndarray]:
        """
        Read multiple frames
        
        Args:
            count: Number of frames to read (default: batch_size)
        
        Returns:
            List of frames
        """
        if count is None:
            count = self.batch_size
        
        frames = []
        for _ in range(count):
            ret, frame = self.read()
            if not ret:
                break
            frames.append(frame)
        
        return frames
    
    def read_at(self, frame_number: int) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame at specific position
        
        Args:
            frame_number: Target frame number
        
        Returns:
            (success, frame)
        """
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.cap.read()
            if ret:
                self._current_frame = frame_number + 1
            return ret, frame
    
    def read_at_time(self, timestamp: float) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame at specific timestamp
        
        Args:
            timestamp: Time in seconds
        
        Returns:
            (success, frame)
        """
        frame_number = int(timestamp * self._info.fps)
        return self.read_at(frame_number)
    
    def iter_frames(
        self, 
        start: int = 0, 
        end: Optional[int] = None,
        step: int = 1
    ) -> Iterator[Tuple[int, np.ndarray]]:
        """
        Iterate over frames
        
        Args:
            start: Starting frame number
            end: Ending frame number (exclusive)
            step: Frame step
        
        Yields:
            (frame_number, frame)
        """
        if end is None:
            end = self._info.frame_count
        
        self.position = start
        
        for frame_num in range(start, end, step):
            ret, frame = self.read()
            if not ret:
                break
            yield frame_num, frame
    
    def get_frame_at_timestamp(self, timestamp: float) -> Optional[np.ndarray]:
        """Get frame at timestamp"""
        ret, frame = self.read_at_time(timestamp)
        return frame if ret else None
    
    def get_frames_batch_at_timestamps(
        self, 
        timestamps: List[float],
        workers: int = 4
    ) -> List[Tuple[float, Optional[np.ndarray]]]:
        """
        Get frames at multiple timestamps using parallel reading
        
        Args:
            timestamps: List of timestamps in seconds
            workers: Number of worker threads
        
        Returns:
            List of (timestamp, frame) tuples
        """
        results = []
        
        def read_frame(ts):
            ret, frame = self.read_at_time(ts)
            return ts, frame if ret else None
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(read_frame, ts) for ts in timestamps]
            for future in futures:
                results.append(future.result())
        
        return sorted(results, key=lambda x: x[0])
    
    def seek(self, timestamp: float):
        """Seek to timestamp"""
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            self._current_frame = int(timestamp * self._info.fps)
    
    def seek_to_start(self):
        """Seek to start of video"""
        self.seek(0)
    
    def seek_to_end(self):
        """Seek to end of video"""
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._info.frame_count - 1)
            self._current_frame = self._info.frame_count
    
    def get_timestamp_at_frame(self, frame_number: int) -> float:
        """Get timestamp for a frame number"""
        return frame_number / self._info.fps
    
    def get_frame_at_timestamp_ms(self, timestamp_ms: int) -> Optional[np.ndarray]:
        """Get frame at specific millisecond"""
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
            ret, frame = self.cap.read()
            if ret:
                self._current_frame += 1
            return frame if ret else None
    
    def get_thumbnail(self, timestamp: float = 0, size: Tuple[int, int] = (320, 180)) -> Optional[np.ndarray]:
        """
        Get video thumbnail
        
        Args:
            timestamp: Timestamp for thumbnail
            size: Output size (width, height)
        
        Returns:
            Thumbnail image
        """
        ret, frame = self.read_at_time(timestamp)
        if ret and frame is not None:
            return cv2.resize(frame, size)
        return None
    
    def release(self):
        """Release video capture"""
        if self.cap is not None:
            self.cap.release()
            logger.info(f"VideoReader released: {self.video_path.name}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.release()
    
    def __del__(self):
        self.release()
