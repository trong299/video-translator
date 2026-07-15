"""
PaddleOCR Processor for Chinese text recognition
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from utils.logger import get_logger
from utils.helpers import sanitize_text


logger = get_logger(__name__)


@dataclass
class OCRResult:
    """OCR result for a single frame"""
    frame_number: int
    timestamp: float
    text: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None
    raw_results: Optional[List] = None
    
    def is_valid(self) -> bool:
        """Check if result contains valid text"""
        return len(self.text.strip()) > 0 and self.confidence > 0.3


class PaddleOCRProcessor:
    """
    PaddleOCR wrapper for efficient Chinese text recognition
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for OCR engine"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        use_gpu: bool = True,
        use_angle_cls: bool = True,
        lang: str = 'ch',
        show_log: bool = False
    ):
        """
        Initialize PaddleOCR processor
        
        Args:
            use_gpu: Use GPU if available
            use_angle_cls: Use angle classification
            lang: Language ('ch' for Chinese)
            show_log: Show PaddleOCR logs
        """
        # Skip re-initialization if already initialized
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.show_log = show_log
        
        try:
            from paddleocr import PaddleOCR
            
            self.ocr = PaddleOCR(
                use_angle_cls=use_angle_cls,
                lang=lang,
                use_gpu=use_gpu,
                show_log=show_log,
                rec_batch_num=16,
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                rec_algorithm='CRNN'
            )
            
            self._initialized = True
            logger.info(f"PaddleOCR initialized (GPU: {use_gpu}, lang: {lang})")
            
        except ImportError:
            logger.error("PaddleOCR not installed. Run: pip install paddleocr")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if OCR is available"""
        return hasattr(self, '_initialized') and self._initialized
    
    def process_image(
        self, 
        image: np.ndarray,
        roi: Optional[Tuple[int, int, int, int]] = None
    ) -> OCRResult:
        """
        Process a single image with OCR
        
        Args:
            image: Input image (BGR format)
            roi: Region of interest (x, y, width, height)
        
        Returns:
            OCRResult with recognized text
        """
        if not self.is_available():
            raise RuntimeError("OCR not initialized")
        
        # Apply ROI crop if specified
        if roi is not None:
            x, y, w, h = roi
            # Ensure ROI is within bounds
            h_img, w_img = image.shape[:2]
            x = max(0, min(x, w_img - 1))
            y = max(0, min(y, h_img - 1))
            w = min(w, w_img - x)
            h = min(h, h_img - y)
            
            if w > 0 and h > 0:
                image = image[y:y+h, x:x+w]
            else:
                return OCRResult(0, 0, "", 0.0)
        
        # Convert BGR to RGB for PaddleOCR
        if len(image.shape) == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = image
        
        try:
            result = self.ocr.ocr(rgb_image, cls=self.use_angle_cls)
            
            if not result or not result[0]:
                return OCRResult(0, 0, "", 0.0)
            
            # Extract text and confidence
            texts = []
            confidences = []
            bboxes = []
            
            for line in result[0]:
                if line and len(line) >= 2:
                    bbox = line[0]
                    text_info = line[1]
                    
                    if isinstance(text_info, tuple) and len(text_info) >= 2:
                        text, confidence = text_info[0], text_info[1]
                    else:
                        text, confidence = str(text_info), 1.0
                    
                    texts.append(text)
                    confidences.append(confidence)
                    
                    # Get bounding box
                    if bbox:
                        xs = [p[0] for p in bbox]
                        ys = [p[1] for p in bbox]
                        bboxes.append((min(xs), min(ys), max(xs), max(ys)))
            
            # Combine all texts
            combined_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return OCRResult(
                frame_number=0,
                timestamp=0,
                text=sanitize_text(combined_text),
                confidence=avg_confidence,
                bbox=bboxes[0] if bboxes else None,
                raw_results=result
            )
            
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            return OCRResult(0, 0, "", 0.0)
    
    def process_batch(
        self,
        images: List[np.ndarray],
        rois: Optional[List[Tuple[int, int, int, int]]] = None,
        workers: int = 4
    ) -> List[OCRResult]:
        """
        Process multiple images in parallel
        
        Args:
            images: List of input images
            rois: List of ROIs (one per image)
            workers: Number of worker threads
        
        Returns:
            List of OCR results
        """
        if not self.is_available():
            raise RuntimeError("OCR not initialized")
        
        results = [None] * len(images)
        
        def process_single(args):
            idx, image, roi = args
            result = self.process_image(image, roi)
            return idx, result
        
        args_list = [
            (i, img, rois[i] if rois and i < len(rois) else None)
            for i, img in enumerate(images)
        ]
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_single, args) for args in args_list]
            
            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                except Exception as e:
                    logger.error(f"Batch processing error: {e}")
        
        return results
    
    def process_image_with_details(
        self,
        image: np.ndarray,
        roi: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict[str, Any]:
        """
        Process image with detailed results
        
        Args:
            image: Input image
            roi: Region of interest
        
        Returns:
            Dictionary with detailed OCR results
        """
        result = self.process_image(image, roi)
        
        return {
            'text': result.text,
            'confidence': result.confidence,
            'is_valid': result.is_valid(),
            'has_text': len(result.text.strip()) > 0
        }


class OCRBatchProcessor:
    """
    Batch processor for OCR with progress reporting
    """
    
    def __init__(
        self,
        ocr_processor: PaddleOCRProcessor,
        batch_size: int = 10,
        workers: int = 4
    ):
        self.ocr = ocr_processor
        self.batch_size = batch_size
        self.workers = workers
    
    def process_frames(
        self,
        frame_generator,
        total_frames: int,
        roi: Optional[Tuple[int, int, int, int]] = None,
        progress_callback: Optional[callable] = None
    ) -> List[OCRResult]:
        """
        Process frames with progress reporting
        
        Args:
            frame_generator: Generator yielding (frame_number, frame) tuples
            total_frames: Total number of frames to process
            roi: Region of interest
            progress_callback: Callback for progress updates
        
        Returns:
            List of OCR results
        """
        results = []
        processed = 0
        batch = []
        
        for frame_num, frame in frame_generator:
            batch.append((frame_num, frame))
            
            if len(batch) >= self.batch_size:
                # Process batch
                images = [item[1] for item in batch]
                ocr_results = self.ocr.process_batch(
                    images, 
                    rois=[roi] * len(images) if roi else None,
                    workers=self.workers
                )
                
                # Assign frame numbers
                for i, (frame_num, _) in enumerate(batch):
                    if i < len(ocr_results):
                        ocr_results[i].frame_number = frame_num
                
                results.extend(ocr_results)
                processed += len(batch)
                batch = []
                
                if progress_callback:
                    progress_callback(processed, total_frames)
        
        # Process remaining frames
        if batch:
            images = [item[1] for item in batch]
            ocr_results = self.ocr.process_batch(
                images,
                rois=[roi] * len(images) if roi else None,
                workers=self.workers
            )
            
            for i, (frame_num, _) in enumerate(batch):
                if i < len(ocr_results):
                    ocr_results[i].frame_number = frame_num
            
            results.extend(ocr_results)
            processed += len(batch)
            
            if progress_callback:
                progress_callback(processed, total_frames)
        
        return results
