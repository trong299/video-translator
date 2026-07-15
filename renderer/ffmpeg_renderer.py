"""
FFmpeg-based video renderer with subtitle burning
"""
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass
import os

from utils.logger import get_logger
from utils.helpers import format_timestamp, ensure_dir, find_ffmpeg
from subtitle import SubtitleSet


logger = get_logger(__name__)


@dataclass
class RenderProgress:
    """Render progress information"""
    current_frame: int
    total_frames: int
    current_time: float
    total_time: float
    fps: float
    eta_seconds: float
    progress_percent: float
    
    @property
    def eta_formatted(self) -> str:
        """Format ETA as string"""
        if self.eta_seconds < 60:
            return f"{self.eta_seconds:.1f}s"
        elif self.eta_seconds < 3600:
            return f"{self.eta_seconds/60:.1f}m"
        else:
            return f"{self.eta_seconds/3600:.1f}h"


class FFmpegRenderer:
    """
    Video renderer using FFmpeg for subtitle burning
    """
    
    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        temp_dir: Optional[Path] = None
    ):
        """
        Initialize FFmpeg renderer
        
        Args:
            ffmpeg_path: Path to FFmpeg (auto-detect if None)
            temp_dir: Temporary directory for intermediate files
        """
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "video_translator"
        ensure_dir(self.temp_dir)
        
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
        
        logger.info(f"FFmpegRenderer initialized: {self.ffmpeg_path}")
    
    def check_ffmpeg(self) -> Tuple[bool, str]:
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                return True, version
        except Exception as e:
            return False, str(e)
        return False, "FFmpeg check failed"
    
    def render_with_ass(
        self,
        input_video: Path,
        output_video: Path,
        subtitle_set: SubtitleSet,
        ass_style_config: Optional[Dict[str, Any]] = None,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        crf: int = 23,
        preset: str = "medium",
        progress_callback: Optional[Callable[[RenderProgress], None]] = None
    ) -> bool:
        """
        Render video with ASS subtitles (recommended)
        
        Args:
            input_video: Input video path
            output_video: Output video path
            subtitle_set: Subtitle set to burn
            ass_style_config: Custom ASS style configuration
            video_codec: Video codec
            audio_codec: Audio codec
            crf: Constant Rate Factor (quality)
            preset: Encoding preset (ultrafast to veryslow)
            progress_callback: Progress callback
        
        Returns:
            True if successful
        """
        try:
            # Create ASS file
            ass_file = self.temp_dir / f"subtitles_{os.getpid()}.ass"
            self._create_ass_file(subtitle_set, ass_file, ass_style_config)
            
            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-y',  # Overwrite output
                '-hide_banner',
                '-loglevel', 'error',
                '-progress', 'pipe:1',  # Progress to stdout
                '-i', str(input_video),
                '-vf', f"ass={ass_file}",
                '-c:v', video_codec,
                '-c:a', audio_codec,
                '-crf', str(crf),
                '-preset', preset,
                '-movflags', '+faststart',
                str(output_video)
            ]
            
            logger.info(f"Starting render: {input_video.name} -> {output_video.name}")
            
            # Run FFmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress
            total_frames = self._get_frame_count(input_video)
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if 'frame=' in line:
                    frame = int(line.split('frame=')[1].split()[0])
                    
                    if progress_callback and total_frames > 0:
                        progress = RenderProgress(
                            current_frame=frame,
                            total_frames=total_frames,
                            current_time=frame / 30,  # Approximate
                            total_time=total_frames / 30,
                            fps=30,
                            eta_seconds=(total_frames - frame) / 30,
                            progress_percent=frame / total_frames * 100
                        )
                        progress_callback(progress)
            
            # Check result
            if process.returncode != 0:
                stderr = process.stderr.read()
                logger.error(f"FFmpeg error: {stderr}")
                return False
            
            # Cleanup
            if ass_file.exists():
                ass_file.unlink()
            
            logger.info(f"Render complete: {output_video}")
            return True
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
            return False
    
    def render_with_srt(
        self,
        input_video: Path,
        output_video: Path,
        subtitle_set: SubtitleSet,
        font_name: str = "Arial",
        font_size: int = 48,
        font_color: str = "white",
        progress_callback: Optional[Callable[[RenderProgress], None]] = None
    ) -> bool:
        """
        Render video with SRT subtitles (burned)
        
        Args:
            input_video: Input video path
            output_video: Output video path
            subtitle_set: Subtitle set to burn
            font_name: Font name
            font_size: Font size
            font_color: Font color
            progress_callback: Progress callback
        
        Returns:
            True if successful
        """
        try:
            # Create SRT file
            srt_file = self.temp_dir / f"subtitles_{os.getpid()}.srt"
            self._create_srt_file(subtitle_set, srt_file)
            
            # Map color name to ASS color
            color_map = {
                'white': 'FFFFFF',
                'yellow': 'FFFF00',
                'red': 'FF0000',
                'green': '00FF00',
                'blue': '0000FF'
            }
            color_hex = color_map.get(font_color.lower(), 'FFFFFF')
            
            # Build filter
            filter_str = (
                f"subtitles='{srt_file}':"
                f"force_style='FontName={font_name},FontSize={font_size},"
                f"PrimaryColour=&H00{color_hex}'"
            )
            
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-hide_banner',
                '-loglevel', 'error',
                '-i', str(input_video),
                '-vf', filter_str,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-movflags', '+faststart',
                str(output_video)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for completion
            process.wait()
            
            if process.returncode != 0:
                stderr = process.stderr.read()
                logger.error(f"FFmpeg SRT error: {stderr}")
                return False
            
            # Cleanup
            if srt_file.exists():
                srt_file.unlink()
            
            logger.info(f"SRT render complete: {output_video}")
            return True
            
        except Exception as e:
            logger.error(f"SRT render failed: {e}")
            return False
    
    def extract_audio(
        self,
        input_video: Path,
        output_audio: Path,
        codec: str = "aac"
    ) -> bool:
        """Extract audio from video"""
        try:
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-i', str(input_video),
                '-vn',  # No video
                '-c:a', codec,
                str(output_audio)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return False
    
    def get_video_info(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """Get video information using FFprobe"""
        try:
            cmd = [
                'ffprobe' if self.ffmpeg_path else self.ffmpeg_path.replace('ffmpeg', 'ffprobe'),
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            import json
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            
        except Exception as e:
            logger.error(f"FFprobe error: {e}")
        
        return None
    
    def _get_frame_count(self, video_path: Path) -> int:
        """Get frame count from video"""
        info = self.get_video_info(video_path)
        if info:
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return int(stream.get('nb_frames', 0))
        return 0
    
    def _create_ass_file(
        self,
        subtitle_set: SubtitleSet,
        output_path: Path,
        config: Optional[Dict[str, Any]] = None
    ):
        """Create ASS subtitle file"""
        config = config or {}
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Header
            f.write("[Script Info]\n")
            f.write("Title: Subtitle Export\n")
            f.write("ScriptType: v4.00+\n")
            f.write("Collisions: Normal\n")
            f.write("\n")
            
            # Styles
            f.write("[V4+ Styles]\n")
            f.write("Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,"
                   "BackColour,Bold,Italic,Underline,Strikeout,ScaleX,ScaleY,"
                   "Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
                   "MarginL,MarginR,MarginV,Encoding\n")
            
            fontname = config.get('font_name', 'Arial')
            fontsize = config.get('font_size', 48)
            primary_color = config.get('primary_color', '&H00FFFFFF')
            outline_color = config.get('outline_color', '&H00000000')
            
            style_line = (
                f"Style: Default,{fontname},{fontsize},{primary_color},"
                f"{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,"
                f"50,50,20,1\n"
            )
            f.write(style_line)
            f.write("\n")
            
            # Events
            f.write("[Events]\n")
            f.write("Format: Layer,Start,End,Style,Name,MarginL,MarginR,"
                   "MarginV,Effect,Text\n")
            
            for sub in subtitle_set.subtitles:
                # Use translation or original
                text = sub.translation if sub.translation else sub.text
                text = self._escape_ass_text(text)
                
                start = format_timestamp(sub.start_time, 'ass')
                end = format_timestamp(sub.end_time, 'ass')
                
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
    
    def _create_srt_file(self, subtitle_set: SubtitleSet, output_path: Path):
        """Create SRT subtitle file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subtitle_set.subtitles:
                text = sub.translation if sub.translation else sub.text
                
                start = format_timestamp(sub.start_time, 'srt')
                end = format_timestamp(sub.end_time, 'srt')
                
                f.write(f"{sub.index}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
    
    @staticmethod
    def _escape_ass_text(text: str) -> str:
        """Escape text for ASS format"""
        replacements = {
            '\\': '\\\\',
            '\n': '\\N',
            '{': '\\{',
            '}': '\\}'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def estimate_output_size(
        self,
        input_video: Path,
        duration: float,
        crf: int = 23
    ) -> int:
        """
        Estimate output file size
        
        Args:
            input_video: Input video path
            duration: Duration in seconds
            crf: CRF value
        
        Returns:
            Estimated size in bytes
        """
        # Rough estimation based on CRF
        # Lower CRF = larger file
        bitrate_map = {
            18: 8000,  # High quality
            23: 4000,  # Medium quality
            28: 2000,  # Low quality
        }
        
        bitrate = bitrate_map.get(crf, 3000)  # kbps
        
        return int(duration * bitrate * 1000 / 8)  # bytes


class RenderQueue:
    """
    Queue for batch rendering
    """
    
    def __init__(self, renderer: FFmpegRenderer):
        self.renderer = renderer
        self._queue = []
        self._is_processing = False
        self._current_item = None
    
    def add(
        self,
        input_video: Path,
        output_video: Path,
        subtitle_set: SubtitleSet,
        priority: int = 0
    ):
        """Add item to render queue"""
        self._queue.append({
            'input': input_video,
            'output': output_video,
            'subtitles': subtitle_set,
            'priority': priority
        })
        self._queue.sort(key=lambda x: x['priority'])
    
    def process_next(self, callback: Optional[Callable] = None) -> bool:
        """Process next item in queue"""
        if not self._queue or self._is_processing:
            return False
        
        self._is_processing = True
        item = self._queue.pop(0)
        self._current_item = item
        
        try:
            result = self.renderer.render_with_ass(
                item['input'],
                item['output'],
                item['subtitles'],
                progress_callback=callback
            )
            
            self._current_item = None
            self._is_processing = False
            
            return result
            
        except Exception as e:
            logger.error(f"Queue processing error: {e}")
            self._is_processing = False
            return False
    
    def clear(self):
        """Clear queue"""
        self._queue.clear()
    
    @property
    def queue_size(self) -> int:
        return len(self._queue)
    
    @property
    def is_processing(self) -> bool:
        return self._is_processing
