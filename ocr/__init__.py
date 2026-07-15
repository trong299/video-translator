"""
OCR module for Chinese text recognition
"""
from .paddle_ocr import PaddleOCRProcessor
from .frame_processor import FrameProcessor

__all__ = ['PaddleOCRProcessor', 'FrameProcessor']
