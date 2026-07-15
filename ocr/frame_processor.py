"""
Frame Processor with SSIM-based deduplication
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional, Iterator, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib

from utils.logger import get_logger
from .paddle_ocr import OCRResult, PaddleOCRProcessor


logger = get_logger(__name__)


@dataclass
class FrameDifference:
    """Result of frame comparison"""
    frame1: int
    frame2: int
    ssim_score: float
    is_different: bool


class SSIMCalculator:
    """
    Structural Similarity Index calculation for frame comparison
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        # Pre-compute Gaussian kernel for SSIM
        self._kernel = self._create_gaussian_kernel(11, 1.5)
    
    @staticmethod
    def _create_gaussian_kernel(width: int, sigma: float) -> np.ndarray:
        """Create Gaussian kernel"""
        ax = np.arange(-width // 2 + 1., width // 2 + 1.)
        xx, yy = np.meshgrid(ax, ax)
        kernel = np.exp(-(xx**2 + yy**2) / (2. * sigma**2))
        return kernel / np.sum(kernel)
    
    @staticmethod
    def _compute_mssim_internal(
        img1: np.ndarray, 
        img2: np.ndarray,
        kernel: np.ndarray,
        k1: float = 0.01,
        k2: float = 0.03,
        L: float = 255.0
    ) -> float:
        """Compute SSIM between two images"""
        # Convert to grayscale if needed
        if len(img1.shape) == 3:
            img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        if len(img2.shape) == 3:
            img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # Ensure same size
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
        # Constants
        C1 = (k1 * L) ** 2
        C2 = (k2 * L) ** 2
        
        # Compute means
        mu1 = cv2.filter2D(img1.astype(np.float64), -1, kernel)
        mu2 = cv2.filter2D(img2.astype(np.float64), -1, kernel)
        
        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2
        
        # Compute variances and covariance
        sigma1_sq = cv2.filter2D(img1.astype(np.float64) ** 2, -1, kernel) - mu1_sq
        sigma2_sq = cv2.filter2D(img2.astype(np.float64) ** 2, -1, kernel) - mu2_sq
        sigma12 = cv2.filter2D(img1.astype(np.float64) * img2.astype(np.float64), -1, kernel) - mu1_mu2
        
        # SSIM formula
        numerator = (2 * mu1_mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)
        
        ssim_map = numerator / denominator
        
        # Return mean SSIM
        return float(np.mean(ssim_map))
    
    def compute_ssim(
        self, 
        img1: np.ndarray, 
        img2: np.ndarray
    ) -> float:
        """Compute SSIM between two images"""
        return self._compute_mssim_internal(img1, img2, self._kernel)
    
    def compute_ssim_fast(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        scale: int = 2
    ) -> float:
        """
        Fast SSIM computation by downscaling images first
        
        Args:
            img1: First image
            img2: Second image
            scale: Downscale factor
        
        Returns:
            SSIM score
        """
        # Downscale for faster comparison
        h, w = img1.shape[:2]
        new_size = (w // scale, h // scale)
        
        small1 = cv2.resize(img1, new_size)
        small2 = cv2.resize(img2, new_size)
        
        return self.compute_ssim(small1, small2)


class FrameProcessor:
    """
    Frame processor with SSIM-based deduplication
    Only OCRs frames that are significantly different
    """
    
    def __init__(
        self,
        ocr_processor: PaddleOCRProcessor,
        ssim_threshold: float = 0.90,
        batch_size: int = 10,
        workers: int = 4
    ):
        """
        Initialize frame processor
        
        Args:
            ocr_processor: PaddleOCR processor instance
            ssim_threshold: Threshold for considering frames different (0-1)
            batch_size: Batch size for OCR processing
            workers: Number of worker threads
        """
        self.ocr = ocr_processor
        self.ssim_threshold = ssim_threshold
        self.batch_size = batch_size
        self.workers = workers
        self.ssim_calc = SSIMCalculator()
        
        # Caching
        self._ocr_cache: dict = {}
        self._frame_cache: dict = {}
        
        # Statistics
        self._stats = {
            'total_frames': 0,
            'unique_frames': 0,
            'skipped_frames': 0,
            'ocr_calls': 0
        }
        self._stats_lock = threading.Lock()
        
        logger.info(f"FrameProcessor initialized (SSIM threshold: {ssim_threshold})")
    
    def _compute_frame_hash(self, frame: np.ndarray) -> str:
        """Compute perceptual hash for frame"""
        # Resize to small size
        small = cv2.resize(frame, (64, 64))
        
        # Convert to grayscale if needed
        if len(small.shape) == 3:
            small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        # Compute average hash
        avg = np.mean(small)
        bits = (small > avg).astype(np.uint8)
        
        # Convert to hex string
        bits_flat = bits.flatten()
        bit_string = ''.join(bits_flat.astype(str))
        return hex(int(bit_string, 2))[2:]
    
    def _is_frame_unique(
        self, 
        frame: np.ndarray, 
        previous_frames: List[np.ndarray]
    ) -> bool:
        """
        Check if frame is unique compared to previous frames
        
        Args:
            frame: Current frame
            previous_frames: List of previous frames to compare
        
        Returns:
            True if frame is unique (different enough)
        """
        if not previous_frames:
            return True
        
        # Quick hash check first
        current_hash = self._compute_frame_hash(frame)
        
        for prev_frame in previous_frames[-5:]:  # Only check last 5 frames
            prev_hash = self._compute_frame_hash(prev_frame)
            
            # Quick bit difference
            diff = sum(c1 != c2 for c1, c2 in zip(current_hash, prev_hash))
            
            if diff <= 2:  # Very similar hashes
                # Do full SSIM check
                ssim = self.ssim_calc.compute_ssim_fast(frame, prev_frame, scale=4)
                if ssim >= self.ssim_threshold:
                    return False
        
        return True
    
    def process_frames(
        self,
        frames: Iterator[Tuple[int, np.ndarray]],
        total_frames: int,
        roi: Optional[Tuple[int, int, int, int]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[OCRResult]:
        """
        Process frames with deduplication
        
        Args:
            frames: Iterator of (frame_number, frame) tuples
            total_frames: Total number of frames
            roi: Region of interest for OCR
            progress_callback: Progress callback function
        
        Returns:
            List of OCR results for unique frames
        """
        results = []
        previous_frames = []
        processed = 0
        batch = []
        batch_frames_for_comparison = []
        
        with self._stats_lock:
            self._stats['total_frames'] = total_frames
        
        for frame_num, frame in frames:
            # Extract ROI if specified
            if roi is not None:
                x, y, w, h = roi
                proc_frame = frame[y:y+h, x:x+w]
            else:
                proc_frame = frame
            
            # Check if frame is unique
            is_unique = self._is_frame_unique(proc_frame, previous_frames)
            
            if is_unique:
                batch.append((frame_num, proc_frame))
                batch_frames_for_comparison.append(proc_frame.copy())
                
                # Update previous frames
                if len(previous_frames) >= 10:
                    previous_frames.pop(0)
                previous_frames.append(proc_frame.copy())
            
            processed += 1
            
            if len(batch) >= self.batch_size:
                # Process batch
                batch_results = self._process_batch(batch, roi)
                results.extend(batch_results)
                
                with self._stats_lock:
                    self._stats['unique_frames'] += len(batch)
                
                batch = []
                
                if progress_callback:
                    progress_callback(processed, total_frames)
        
        # Process remaining batch
        if batch:
            batch_results = self._process_batch(batch, roi)
            results.extend(batch_results)
            
            with self._stats_lock:
                self._stats['unique_frames'] += len(batch)
        
        # Calculate skipped frames
        with self._stats_lock:
            self._stats['skipped_frames'] = self._stats['total_frames'] - self._stats['unique_frames']
        
        if progress_callback:
            progress_callback(total_frames, total_frames)
        
        logger.info(f"Frame processing complete: {self._stats['unique_frames']} unique, "
                   f"{self._stats['skipped_frames']} skipped")
        
        return results
    
    def _process_batch(
        self, 
        batch: List[Tuple[int, np.ndarray]], 
        roi: Optional[Tuple[int, int, int, int]]
    ) -> List[OCRResult]:
        """Process a batch of frames with OCR"""
        images = [item[1] for item in batch]
        
        # Check cache
        uncached = []
        cached_results = []
        
        for i, (frame_num, _) in enumerate(batch):
            cache_key = self._compute_frame_hash(images[i])
            if cache_key in self._ocr_cache:
                cached_result = self._ocr_cache[cache_key]
                cached_result.frame_number = frame_num
                cached_results.append(cached_result)
            else:
                uncached.append((i, frame_num, images[i]))
        
        # Process uncached frames
        if uncached:
            uncached_images = [item[2] for item in uncached]
            ocr_results = self.ocr.process_batch(
                uncached_images, 
                rois=[roi] * len(uncached_images) if roi else None,
                workers=self.workers
            )
            
            for i, (_, frame_num, img) in enumerate(uncached):
                if i < len(ocr_results):
                    result = ocr_results[i]
                    result.frame_number = frame_num
                    
                    # Cache result
                    cache_key = self._compute_frame_hash(img)
                    self._ocr_cache[cache_key] = result
                    cached_results.append(result)
        
        # Sort by frame number
        cached_results.sort(key=lambda x: x.frame_number)
        
        with self._stats_lock:
            self._stats['ocr_calls'] += len(uncached) if uncached else 0
        
        return cached_results
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        with self._stats_lock:
            stats = self._stats.copy()
            stats['cache_size'] = len(self._ocr_cache)
            stats['cache_hit_rate'] = (
                (stats['unique_frames'] - stats['ocr_calls']) / stats['unique_frames']
                if stats['unique_frames'] > 0 else 0
            )
            return stats
    
    def clear_cache(self):
        """Clear OCR cache"""
        self._ocr_cache.clear()
        self._frame_cache.clear()
        logger.info("Frame processor cache cleared")


class FrameDifferenceAnalyzer:
    """
    Analyzes differences between consecutive frames
    """
    
    def __init__(self, ssim_threshold: float = 0.90):
        self.ssim_threshold = ssim_threshold
        self.ssim_calc = SSIMCalculator()
    
    def analyze_difference(
        self, 
        frame1: np.ndarray, 
        frame2: np.ndarray
    ) -> FrameDifference:
        """Analyze difference between two frames"""
        ssim = self.ssim_calc.compute_ssim_fast(frame1, frame2, scale=2)
        return FrameDifference(
            frame1=0,
            frame2=0,
            ssim_score=ssim,
            is_different=ssim < self.ssim_threshold
        )
    
    def find_scene_changes(
        self,
        frames: List[np.ndarray],
        threshold: float = 0.80
    ) -> List[int]:
        """
        Find scene change points in a list of frames
        
        Args:
            frames: List of frames
            threshold: SSIM threshold for scene change detection
        
        Returns:
            List of frame indices where scene changes occur
        """
        scene_changes = []
        
        for i in range(1, len(frames)):
            ssim = self.ssim_calc.compute_ssim_fast(frames[i-1], frames[i], scale=2)
            if ssim < threshold:
                scene_changes.append(i)
        
        return scene_changes
