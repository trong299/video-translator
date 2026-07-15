"""
Subtitle Exporter - exports subtitles to various formats
"""
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from utils.logger import get_logger
from utils.helpers import format_timestamp, ensure_dir
from .subtitle import SubtitleSet


logger = get_logger(__name__)


@dataclass
class ASSStyle:
    """ASS subtitle style"""
    name: str = "Default"
    fontname: str = "Arial"
    fontsize: float = 48
    primary_color: str = "&H00FFFFFF"  # White
    outline_color: str = "&H00000000"  # Black
    back_color: str = "&H00000000"    # Transparent
    bold: int = 0
    italic: int = 0
    underline: int = 0
    strikeout: int = 0
    scale_x: float = 100
    scale_y: float = 100
    spacing: float = 0
    angle: float = 0
    border_style: int = 1  # 1=Outline, 3=Opaque box
    outline: float = 2
    shadow: float = 0
    alignment: int = 2  # Bottom center
    margin_l: int = 50
    margin_r: int = 50
    margin_v: int = 20
    encoding: int = 1
    
    def to_ass_string(self) -> str:
        """Convert style to ASS format string"""
        return (
            f"Style: {self.name},{self.fontname},{self.fontsize},"
            f"{self.primary_color},{self.outline_color},{self.back_color},"
            f"{self.bold},{self.italic},{self.underline},{self.strikeout},"
            f"{self.scale_x},{self.scale_y},{self.spacing},{self.angle},"
            f"{self.border_style},{self.outline},{self.shadow},"
            f"{self.alignment},{self.margin_l},{self.margin_r},{self.margin_v},"
            f"{self.encoding}"
        )


class SubtitleExporter:
    """
    Export subtitles to various formats (SRT, ASS, VTT, TXT)
    """
    
    def __init__(self):
        self.ass_styles = {
            'default': ASSStyle()
        }
        logger.info("SubtitleExporter initialized")
    
    def export_srt(
        self, 
        subtitle_set: SubtitleSet, 
        output_path: Path,
        include_original: bool = False
    ) -> bool:
        """
        Export subtitles to SRT format
        
        Args:
            subtitle_set: Subtitle set to export
            output_path: Output file path
            include_original: Include original Chinese text
        
        Returns:
            True if successful
        """
        try:
            ensure_dir(output_path.parent)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for sub in subtitle_set.subtitles:
                    # Determine text to write
                    if sub.translation:
                        display_text = sub.translation
                    else:
                        display_text = sub.text
                    
                    # Include original if requested
                    if include_original and sub.text:
                        display_text = f"{sub.text}\n{display_text}"
                    
                    # Format SRT entry
                    start = format_timestamp(sub.start_time, 'srt')
                    end = format_timestamp(sub.end_time, 'srt')
                    
                    f.write(f"{sub.index}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{display_text}\n")
                    f.write("\n")
            
            logger.info(f"Exported SRT: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export SRT: {e}")
            return False
    
    def export_ass(
        self, 
        subtitle_set: SubtitleSet, 
        output_path: Path,
        style: Optional[ASSStyle] = None,
        include_original: bool = False
    ) -> bool:
        """
        Export subtitles to ASS format
        
        Args:
            subtitle_set: Subtitle set to export
            output_path: Output file path
            style: Custom style (uses default if None)
            include_original: Include original Chinese text
        
        Returns:
            True if successful
        """
        try:
            ensure_dir(output_path.parent)
            
            if style is None:
                style = self.ass_styles['default']
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write ASS header
                f.write("[Script Info]\n")
                f.write("Title: Subtitle Export\n")
                f.write("ScriptType: v4.00+\n")
                f.write("Collisions: Normal\n")
                f.write("PlayDepth: 0\n")
                f.write("\n")
                
                # Write styles
                f.write("[V4+ Styles]\n")
                f.write(f"Format: {','.join(self._get_ass_format_fields())}\n")
                f.write(style.to_ass_string() + "\n")
                f.write("\n")
                
                # Write events
                f.write("[Events]\n")
                f.write("Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
                
                for sub in subtitle_set.subtitles:
                    # Determine text
                    if sub.translation:
                        display_text = sub.translation
                    else:
                        display_text = sub.text
                    
                    if include_original and sub.text:
                        display_text = f"{sub.text}\\N{display_text}"
                    
                    # Escape and format
                    text = self._escape_ass_text(display_text)
                    
                    start = format_timestamp(sub.start_time, 'ass')
                    end = format_timestamp(sub.end_time, 'ass')
                    
                    f.write(f"Dialogue: 0,{start},{end},{style.name},"
                           f"{style.margin_l},{style.margin_r},{style.margin_v},,{text}\n")
            
            logger.info(f"Exported ASS: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export ASS: {e}")
            return False
    
    def _get_ass_format_fields(self) -> list:
        """Get ASS format field names"""
        return [
            "Name", "Fontname", "Fontsize", "PrimaryColour", "OutlineColour",
            "BackColour", "Bold", "Italic", "Underline", "Strikeout",
            "ScaleX", "ScaleY", "Spacing", "Angle", "BorderStyle",
            "Outline", "Shadow", "Alignment", "MarginL", "MarginR",
            "MarginV", "Encoding"
        ]
    
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
    
    def export_vtt(
        self, 
        subtitle_set: SubtitleSet, 
        output_path: Path,
        include_original: bool = False
    ) -> bool:
        """
        Export subtitles to WebVTT format
        
        Args:
            subtitle_set: Subtitle set to export
            output_path: Output file path
            include_original: Include original Chinese text
        
        Returns:
            True if successful
        """
        try:
            ensure_dir(output_path.parent)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write VTT header
                f.write("WEBVTT\n\n")
                
                for sub in subtitle_set.subtitles:
                    # Format time
                    start = format_timestamp(sub.start_time, 'vtt')
                    end = format_timestamp(sub.end_time, 'vtt')
                    
                    # Determine text
                    if sub.translation:
                        display_text = sub.translation
                    else:
                        display_text = sub.text
                    
                    if include_original and sub.text:
                        display_text = f"{sub.text}\n{display_text}"
                    
                    f.write(f"{sub.index}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{display_text}\n\n")
            
            logger.info(f"Exported VTT: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export VTT: {e}")
            return False
    
    def export_txt(
        self, 
        subtitle_set: SubtitleSet, 
        output_path: Path,
        translation_only: bool = True,
        numbered: bool = False
    ) -> bool:
        """
        Export subtitles to plain text
        
        Args:
            subtitle_set: Subtitle set to export
            output_path: Output file path
            translation_only: Export only translations (not original)
            numbered: Include line numbers
        
        Returns:
            True if successful
        """
        try:
            ensure_dir(output_path.parent)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for sub in subtitle_set.subtitles:
                    if translation_only:
                        text = sub.translation if sub.translation else sub.text
                    else:
                        text = f"{sub.text} | {sub.translation}" if sub.translation else sub.text
                    
                    if numbered:
                        f.write(f"{sub.index}. {text}\n")
                    else:
                        f.write(f"{text}\n")
            
            logger.info(f"Exported TXT: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export TXT: {e}")
            return False
    
    def export_all_formats(
        self, 
        subtitle_set: SubtitleSet, 
        output_dir: Path,
        base_name: str = "subtitles",
        include_original: bool = False,
        ass_style: Optional[ASSStyle] = None
    ) -> Dict[str, Path]:
        """
        Export subtitles in all formats
        
        Args:
            subtitle_set: Subtitle set to export
            output_dir: Output directory
            base_name: Base filename (without extension)
            include_original: Include original text
            ass_style: Custom ASS style
        
        Returns:
            Dictionary mapping format to output path
        """
        ensure_dir(output_dir)
        
        results = {}
        
        # SRT
        srt_path = output_dir / f"{base_name}.srt"
        if self.export_srt(subtitle_set, srt_path, include_original):
            results['srt'] = srt_path
        
        # ASS
        ass_path = output_dir / f"{base_name}.ass"
        if self.export_ass(subtitle_set, ass_path, ass_style, include_original):
            results['ass'] = ass_path
        
        # VTT
        vtt_path = output_dir / f"{base_name}.vtt"
        if self.export_vtt(subtitle_set, vtt_path, include_original):
            results['vtt'] = vtt_path
        
        # TXT (translation only)
        txt_path = output_dir / f"{base_name}.txt"
        if self.export_txt(subtitle_set, txt_path, translation_only=True):
            results['txt'] = txt_path
        
        logger.info(f"Exported {len(results)} subtitle formats")
        
        return results
    
    def create_ass_style(
        self,
        name: str = "Custom",
        fontname: str = "Arial",
        fontsize: float = 48,
        primary_color: str = "&H00FFFFFF",
        outline_color: str = "&H00000000",
        **kwargs
    ) -> ASSStyle:
        """Create a custom ASS style"""
        return ASSStyle(
            name=name,
            fontname=fontname,
            fontsize=fontsize,
            primary_color=primary_color,
            outline_color=outline_color,
            **kwargs
        )
