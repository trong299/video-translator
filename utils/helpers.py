"""
Helper utilities
"""
import cv2
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import timedelta

from .logger import get_logger


logger = get_logger(__name__)


def format_timestamp(seconds: float, format_type: str = 'srt') -> str:
    """
    Format timestamp for subtitle formats
    
    Args:
        seconds: Time in seconds
        format_type: 'srt' (00:00:00,000) or 'ass' (0:00:00.00) or 'seconds'
    
    Returns:
        Formatted timestamp string
    """
    if format_type == 'srt':
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    elif format_type == 'ass':
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    elif format_type == 'timestamp':
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{seconds:.3f}"


def parse_timestamp(timestamp: str) -> float:
    """
    Parse timestamp string to seconds
    
    Args:
        timestamp: Timestamp string (supports various formats)
    
    Returns:
        Time in seconds
    """
    # Try SRT format: 00:00:00,000
    if ',' in timestamp:
        timestamp = timestamp.replace(',', '.')
    
    parts = timestamp.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    else:
        return float(timestamp)


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_video_file(path: Path) -> bool:
    """Check if file is a supported video format"""
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    return path.suffix.lower() in video_extensions


def sanitize_text(text: str) -> str:
    """
    Sanitize text for subtitle display
    
    Args:
        text: Input text
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    return text.strip()


def get_video_info(video_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get video file information using OpenCV
    
    Args:
        video_path: Path to video file
    
    Returns:
        Dictionary with video info or None on error
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return None
        
        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS),
            'fourcc': int(cap.get(cv2.CAP_PROP_FOURCC))
        }
        cap.release()
        
        logger.info(f"Video info for {video_path.name}: {info['width']}x{info['height']}, "
                   f"{info['fps']:.2f} fps, {info['frame_count']} frames")
        return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None


def get_video_info_ffmpeg(video_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get detailed video info using FFmpeg
    
    Args:
        video_path: Path to video file
    
    Returns:
        Dictionary with detailed video info or None on error
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        data = json.loads(result.stdout)
        
        video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        audio_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
        
        if not video_stream:
            return None
        
        info = {
            'width': video_stream.get('width', 0),
            'height': video_stream.get('height', 0),
            'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream.get('r_frame_rate') else 0,
            'duration': float(data.get('format', {}).get('duration', 0)),
            'bitrate': int(data.get('format', {}).get('bit_rate', 0)),
            'codec': video_stream.get('codec_name', ''),
            'has_audio': audio_stream is not None,
            'audio_codec': audio_stream.get('codec_name') if audio_stream else None
        }
        
        return info
    except Exception as e:
        logger.warning(f"FFprobe failed: {e}, falling back to OpenCV")
        return get_video_info(video_path)


def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg executable path"""
    import shutil
    
    # Try common locations
    paths_to_check = [
        'ffmpeg',
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        'C:\\ffmpeg\\bin\\ffmpeg.exe'
    ]
    
    for path in paths_to_check:
        if shutil.which(path):
            return path
    
    # Try with shutil
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    
    return None


def check_ffmpeg_available() -> Tuple[bool, str]:
    """Check if FFmpeg is available"""
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        return True, ffmpeg_path
    return False, "FFmpeg not found in PATH"


def estimate_processing_time(frame_count: int, fps: float) -> Dict[str, float]:
    """
    Estimate processing time based on video properties
    
    Args:
        frame_count: Total number of frames
        fps: Video FPS
    
    Returns:
        Dictionary with estimated times (in seconds)
    """
    # Rough estimates (adjust based on hardware)
    ocr_time_per_frame = 0.05  # seconds (CPU)
    translation_time_per_subtitle = 0.1  # seconds
    
    total_duration = frame_count / fps
    
    return {
        'ocr_estimated': total_duration * ocr_time_per_frame * 2,  # With some overhead
        'translation_estimated': frame_count / 30 * translation_time_per_subtitle,
        'render_estimated': total_duration * 0.5,  # Real-time rendering
    }


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
