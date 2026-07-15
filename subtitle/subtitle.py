"""
Subtitle data models
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from datetime import timedelta
import copy

from utils.logger import get_logger
from utils.helpers import format_timestamp, sanitize_text


logger = get_logger(__name__)


@dataclass
class Subtitle:
    """
    Single subtitle entry
    """
    index: int
    start_time: float  # in seconds
    end_time: float    # in seconds
    text: str          # Original text (Chinese)
    translation: str = ""  # Translated text (Vietnamese)
    
    # Metadata
    confidence: float = 1.0
    frame_number: Optional[int] = None
    
    def __post_init__(self):
        """Validate subtitle"""
        if self.start_time < 0:
            self.start_time = 0
        if self.end_time < self.start_time:
            self.end_time = self.start_time + 1.0
        if not isinstance(self.text, str):
            self.text = str(self.text)
        if not isinstance(self.translation, str):
            self.translation = str(self.translation)
    
    @property
    def duration(self) -> float:
        """Get subtitle duration in seconds"""
        return self.end_time - self.start_time
    
    @property
    def is_valid(self) -> bool:
        """Check if subtitle is valid"""
        return (
            len(self.text.strip()) > 0 and
            self.duration > 0 and
            self.start_time >= 0
        )
    
    def format_srt(self) -> str:
        """Format subtitle for SRT format"""
        if self.translation:
            display_text = self.translation
        else:
            display_text = self.text
        
        start = format_timestamp(self.start_time, 'srt')
        end = format_timestamp(self.end_time, 'srt')
        
        return f"{self.index}\n{start} --> {end}\n{display_text}\n"
    
    def format_ass(self, style: Optional[Dict[str, Any]] = None) -> str:
        """Format subtitle for ASS format"""
        if self.translation:
            display_text = self.translation
        else:
            display_text = self.text
        
        # Escape special characters
        display_text = self._escape_ass(display_text)
        
        start = format_timestamp(self.start_time, 'ass')
        end = format_timestamp(self.end_time, 'ass')
        
        return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{display_text}"
    
    @staticmethod
    def _escape_ass(text: str) -> str:
        """Escape text for ASS format"""
        # Order matters - escape backslash first
        replacements = {
            '\\': '\\\\',
            '{': '\\{',
            '}': '\\}',
            '\n': '\\N'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def merge_with(self, other: 'Subtitle', gap_threshold: float = 2.0) -> bool:
        """
        Try to merge with another subtitle
        
        Args:
            other: Another subtitle to merge
            gap_threshold: Maximum gap between subtitles to merge
        
        Returns:
            True if merged, False otherwise
        """
        if not self._can_merge_with(other):
            return False
        
        # Check if gap is within threshold
        gap = other.start_time - self.end_time
        if gap > gap_threshold:
            return False
        
        # Merge
        self.text += " " + other.text
        self.translation += " " + other.translation
        self.end_time = other.end_time
        self.index = min(self.index, other.index)
        
        return True
    
    def _can_merge_with(self, other: 'Subtitle') -> bool:
        """Check if can merge with another subtitle"""
        # Must have overlapping or adjacent times
        if other.start_time > self.end_time + 1.0:
            return False
        
        # Same content or similar
        if self.text == other.text:
            return True
        
        return False
    
    def shift_time(self, offset: float):
        """Shift subtitle time by offset"""
        self.start_time += offset
        self.end_time += offset
        if self.start_time < 0:
            self.start_time = 0
        if self.end_time < 0:
            self.end_time = 0
    
    def copy(self) -> 'Subtitle':
        """Create a deep copy"""
        return copy.deepcopy(self)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'index': self.index,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'text': self.text,
            'translation': self.translation,
            'confidence': self.confidence,
            'frame_number': self.frame_number
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Subtitle':
        """Create from dictionary"""
        return cls(
            index=data['index'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            text=data['text'],
            translation=data.get('translation', ''),
            confidence=data.get('confidence', 1.0),
            frame_number=data.get('frame_number')
        )


@dataclass
class SubtitleSet:
    """
    Collection of subtitles with metadata
    """
    subtitles: List[Subtitle] = field(default_factory=list)
    title: str = ""
    language: str = "vi"
    format_version: str = "1.0"
    
    # Statistics
    _stats: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    def __post_init__(self):
        """Initialize subtitle set"""
        self._update_stats()
    
    def add(self, subtitle: Subtitle):
        """Add subtitle to set"""
        self.subtitles.append(subtitle)
        self._update_stats()
    
    def add_range(self, subtitles: List[Subtitle]):
        """Add multiple subtitles"""
        self.subtitles.extend(subtitles)
        self._update_stats()
    
    def remove(self, index: int) -> bool:
        """Remove subtitle by index"""
        for i, sub in enumerate(self.subtitles):
            if sub.index == index:
                self.subtitles.pop(i)
                self._renumber()
                self._update_stats()
                return True
        return False
    
    def _renumber(self):
        """Renumber all subtitles"""
        for i, sub in enumerate(self.subtitles):
            sub.index = i + 1
    
    def sort_by_time(self):
        """Sort subtitles by start time"""
        self.subtitles.sort(key=lambda x: x.start_time)
        self._renumber()
    
    def sort_by_index(self):
        """Sort subtitles by index"""
        self.subtitles.sort(key=lambda x: x.index)
    
    def filter_duplicates(self, threshold: float = 0.8):
        """
        Filter duplicate subtitles
        
        Args:
            threshold: Similarity threshold (0-1)
        """
        from rapidfuzz import fuzz
        
        self.sort_by_time()
        unique = []
        
        for sub in self.subtitles:
            is_duplicate = False
            
            for unique_sub in unique:
                similarity = fuzz.ratio(sub.text, unique_sub.text) / 100.0
                
                # Check if they overlap in time
                time_gap = abs(sub.start_time - unique_sub.start_time)
                
                if similarity > threshold and time_gap < 5.0:
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if sub.confidence > unique_sub.confidence:
                        unique.remove(unique_sub)
                        unique.append(sub)
                    break
            
            if not is_duplicate:
                unique.append(sub)
        
        self.subtitles = unique
        self._renumber()
        self._update_stats()
    
    def merge_consecutive(self, gap_threshold: float = 2.0):
        """
        Merge consecutive subtitles with gap within threshold
        
        Args:
            gap_threshold: Maximum gap to merge (seconds)
        """
        self.sort_by_time()
        
        if not self.subtitles:
            return
        
        merged = [self.subtitles[0]]
        
        for sub in self.subtitles[1:]:
            last = merged[-1]
            
            gap = sub.start_time - last.end_time
            
            if gap <= gap_threshold and sub.text == last.text:
                # Merge
                last.end_time = max(last.end_time, sub.end_time)
                last.translation += " " + sub.translation
            else:
                merged.append(sub)
        
        self.subtitles = merged
        self._renumber()
        self._update_stats()
    
    def get_at_time(self, timestamp: float) -> List[Subtitle]:
        """Get all subtitles at a specific time"""
        return [
            sub for sub in self.subtitles
            if sub.start_time <= timestamp <= sub.end_time
        ]
    
    def get_duration(self) -> Tuple[float, float]:
        """Get total duration (start to end)"""
        if not self.subtitles:
            return (0.0, 0.0)
        
        return (
            min(s.start_time for s in self.subtitles),
            max(s.end_time for s in self.subtitles)
        )
    
    def get_texts(self) -> List[str]:
        """Get all original texts"""
        return [sub.text for sub in self.subtitles]
    
    def get_translations(self) -> List[str]:
        """Get all translations"""
        return [sub.translation for sub in self.subtitles]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return self._stats.copy()
    
    def _update_stats(self):
        """Update statistics"""
        if not self.subtitles:
            self._stats = {
                'count': 0,
                'total_duration': 0.0,
                'avg_duration': 0.0,
                'avg_confidence': 0.0
            }
            return
        
        durations = [sub.duration for sub in self.subtitles]
        confidences = [sub.confidence for sub in self.subtitles]
        
        self._stats = {
            'count': len(self.subtitles),
            'total_duration': sum(durations),
            'avg_duration': sum(durations) / len(durations) if durations else 0.0,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
            'min_confidence': min(confidences) if confidences else 0.0,
            'max_confidence': max(confidences) if confidences else 0.0
        }
    
    def __len__(self) -> int:
        return len(self.subtitles)
    
    def __iter__(self):
        return iter(self.subtitles)
    
    def __getitem__(self, index):
        return self.subtitles[index]
    
    def copy(self) -> 'SubtitleSet':
        """Create a deep copy"""
        return copy.deepcopy(self)
