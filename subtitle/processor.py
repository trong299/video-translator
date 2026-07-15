"""
Subtitle Processor - processes and cleans up subtitles
"""
import re
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass
from rapidfuzz import fuzz, process

from utils.logger import get_logger
from utils.helpers import sanitize_text
from .subtitle import Subtitle, SubtitleSet


logger = get_logger(__name__)


@dataclass
class ProcessingConfig:
    """Configuration for subtitle processing"""
    min_duration: float = 0.5      # Minimum subtitle duration
    max_duration: float = 10.0     # Maximum subtitle duration
    merge_gap: float = 2.0         # Gap threshold for merging
    duplicate_threshold: float = 0.8  # Similarity threshold for duplicates
    max_text_length: int = 200     # Maximum text length
    min_text_length: int = 1      # Minimum text length


class SubtitleProcessor:
    """
    Process and clean up subtitles
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        
        # OCR error patterns and corrections
        self._ocr_corrections = self._build_ocr_corrections()
        
        # Common Chinese patterns
        self._patterns_to_remove = self._build_patterns()
        
        logger.info("SubtitleProcessor initialized")
    
    def _build_ocr_corrections(self) -> Dict[str, str]:
        """Build OCR error corrections dictionary"""
        # Common OCR misrecognitions for Chinese
        return {
            # Character substitutions
            "丿": "、",
            "丨": "1",
            "乚": "1",
            "乛": "了",
            "亅": "1",
            "丶": "、",
            "一": "-",
            "一一": "--",
            # Common OCR errors
            "|": "1",
            "Il": "11",
            "lI": "11",
            "O0": "00",
            "0O": "00",
            # Punctuation
            "。": "。",
            "，": "，",
            "！": "！",
            "？": "？",
        }
    
    def _build_patterns(self) -> List[re.Pattern]:
        """Build regex patterns for cleanup"""
        return [
            # Remove timestamps in text
            re.compile(r'\d{1,2}:\d{2}:\d{2}'),
            re.compile(r'\d{1,2}:\d{2}'),
            # Remove special characters
            re.compile(r'[^\w\s\u4e00-\u9fff\u00c0-\u024f\u00e7\u4e00-\u9fff\u3000-\u303f\u2018-\u201f\u2026]'),
            # Remove excessive whitespace
            re.compile(r'\s+'),
        ]
    
    def process(
        self, 
        subtitle_set: SubtitleSet,
        remove_duplicates: bool = True,
        fix_ocr_errors: bool = True,
        merge_consecutive: bool = True,
        filter_invalid: bool = True
    ) -> SubtitleSet:
        """
        Process subtitle set
        
        Args:
            subtitle_set: Input subtitle set
            remove_duplicates: Remove duplicate subtitles
            fix_ocr_errors: Fix OCR errors
            merge_consecutive: Merge consecutive similar subtitles
            filter_invalid: Remove invalid subtitles
        
        Returns:
            Processed subtitle set
        """
        logger.info("Starting subtitle processing")
        
        # Make a copy
        result = subtitle_set.copy()
        
        # Sort by time
        result.sort_by_time()
        
        # Process each subtitle
        for sub in result.subtitles:
            if fix_ocr_errors:
                sub.text = self._fix_ocr_errors(sub.text)
            
            if filter_invalid:
                if not self._is_valid_subtitle(sub):
                    sub.text = ""
                    sub.translation = ""
        
        # Remove empty subtitles
        if filter_invalid:
            result.subtitles = [s for s in result.subtitles if s.text.strip()]
            result._renumber()
        
        # Remove duplicates
        if remove_duplicates:
            result.filter_duplicates(threshold=self.config.duplicate_threshold)
        
        # Merge consecutive
        if merge_consecutive:
            result.merge_consecutive(gap_threshold=self.config.merge_gap)
        
        # Update stats
        result._update_stats()
        
        logger.info(f"Processing complete: {len(result)} subtitles")
        
        return result
    
    def _is_valid_subtitle(self, subtitle: Subtitle) -> bool:
        """Check if subtitle is valid"""
        # Check duration
        if subtitle.duration < self.config.min_duration:
            return False
        if subtitle.duration > self.config.max_duration:
            # Split long subtitles
            return False
        
        # Check text length
        if len(subtitle.text) < self.config.min_text_length:
            return False
        if len(subtitle.text) > self.config.max_text_length:
            return False
        
        # Check for mostly numbers
        if self._is_mostly_numbers(subtitle.text):
            return False
        
        return True
    
    @staticmethod
    def _is_mostly_numbers(text: str) -> bool:
        """Check if text is mostly numbers"""
        digits = sum(c.isdigit() for c in text)
        letters = sum(c.isalpha() for c in text)
        
        if letters == 0:
            return True
        
        return digits / (digits + letters) > 0.8
    
    def _fix_ocr_errors(self, text: str) -> str:
        """Fix common OCR errors"""
        if not text:
            return text
        
        # Apply character corrections
        for wrong, correct in self._ocr_corrections.items():
            text = text.replace(wrong, correct)
        
        # Clean up patterns
        for pattern in self._patterns_to_remove:
            text = pattern.sub(' ', text)
        
        # Sanitize
        text = sanitize_text(text)
        
        # Remove leading/trailing punctuation
        text = text.strip('。,，、.!?！？')
        
        return text
    
    def fix_ocr_errors_batch(self, texts: List[str]) -> List[str]:
        """Fix OCR errors in batch"""
        return [self._fix_ocr_errors(text) for text in texts]
    
    def merge_subtitles(
        self, 
        subtitles: List[Subtitle],
        gap_threshold: float = 2.0
    ) -> List[Subtitle]:
        """
        Merge consecutive subtitles
        
        Args:
            subtitles: List of subtitles
            gap_threshold: Maximum gap to merge
        
        Returns:
            List of merged subtitles
        """
        if not subtitles:
            return []
        
        # Sort by time
        sorted_subs = sorted(subtitles, key=lambda x: x.start_time)
        
        merged = [sorted_subs[0].copy()]
        
        for sub in sorted_subs[1:]:
            last = merged[-1]
            
            # Check if can merge
            gap = sub.start_time - last.end_time
            
            if gap <= gap_threshold and sub.text == last.text:
                # Extend last subtitle
                last.end_time = max(last.end_time, sub.end_time)
            else:
                merged.append(sub.copy())
        
        # Renumber
        for i, sub in enumerate(merged):
            sub.index = i + 1
        
        return merged
    
    def split_long_subtitles(
        self, 
        subtitle: Subtitle,
        max_duration: float = 5.0
    ) -> List[Subtitle]:
        """
        Split long subtitle into multiple parts
        
        Args:
            subtitle: Long subtitle
            max_duration: Maximum duration per part
        
        Returns:
            List of shorter subtitles
        """
        if subtitle.duration <= max_duration:
            return [subtitle]
        
        # Split by sentences (Chinese punctuation)
        sentences = re.split(r'[。！？]', subtitle.text)
        translations = re.split(r'[.!?]', subtitle.translation)
        
        if len(sentences) <= 1:
            return [subtitle]
        
        # Calculate time per character
        total_chars = sum(len(s) for s in sentences if s.strip())
        if total_chars == 0:
            return [subtitle]
        
        time_per_char = subtitle.duration / total_chars
        
        parts = []
        current_text = ""
        current_trans = ""
        current_start = subtitle.start_time
        current_chars = 0
        idx = 1
        
        for i, (sentence, trans) in enumerate(zip(sentences, translations)):
            if not sentence.strip():
                continue
            
            current_text += sentence
            if trans:
                current_trans += trans
            
            current_chars += len(sentence)
            estimated_end = current_start + current_chars * time_per_char
            
            # Check if we should split here
            duration = estimated_end - current_start
            
            if duration >= max_duration or i == len(sentences) - 1:
                parts.append(Subtitle(
                    index=idx,
                    start_time=current_start,
                    end_time=subtitle.end_time if i == len(sentences) - 1 else estimated_end,
                    text=current_text.strip(),
                    translation=current_trans.strip(),
                    confidence=subtitle.confidence
                ))
                idx += 1
                current_start = estimated_end
                current_text = ""
                current_trans = ""
                current_chars = 0
        
        return parts if parts else [subtitle]
    
    def remove_overlapping(self, subtitles: List[Subtitle]) -> List[Subtitle]:
        """
        Remove overlapping subtitles (keep longer ones)
        
        Args:
            subtitles: List of subtitles
        
        Returns:
            List without overlaps
        """
        if not subtitles:
            return []
        
        sorted_subs = sorted(subtitles, key=lambda x: (x.start_time, -x.duration))
        result = []
        
        last_end = -1
        
        for sub in sorted_subs:
            if sub.start_time >= last_end:
                result.append(sub)
                last_end = sub.end_time
            elif sub.duration > result[-1].duration:
                # Replace with longer one
                result[-1] = sub
                last_end = sub.end_time
        
        return result
    
    def clean_text(self, text: str) -> str:
        """Clean subtitle text"""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove leading/trailing punctuation
        text = text.strip('。,，、.!?！？…')
        
        return text


class ChineseTextProcessor:
    """
    Specialized processor for Chinese text
    """
    
    # Common Chinese number patterns
    NUMBER_MAP = {
        '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
        '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
        '十': '10', '百': '100', '千': '1000', '万': '10000'
    }
    
    @staticmethod
    def normalize_punctuation(text: str) -> str:
        """Normalize Chinese punctuation"""
        replacements = {
            '，': ',',
            '。': '.',
            '！': '!',
            '？': '?',
            '；': ';',
            '：': ':',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '（': '(',
            '）': ')',
            '【': '[',
            '】': ']',
        }
        
        for cn, en in replacements.items():
            text = text.replace(cn, en)
        
        return text
    
    @staticmethod
    def extract_numbers(text: str) -> List[Tuple[str, int]]:
        """Extract Chinese numbers from text"""
        results = []
        current_num = ""
        
        for char in text:
            if char in ChineseTextProcessor.NUMBER_MAP:
                current_num += char
            else:
                if current_num:
                    results.append((current_num, len(current_num)))
                    current_num = ""
        
        if current_num:
            results.append((current_num, len(current_num)))
        
        return results
