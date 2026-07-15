"""
Base Translator Interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import threading

from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class TranslationResult:
    """Translation result"""
    original: str
    translated: str
    confidence: float
    source_lang: str = 'zh'
    target_lang: str = 'vi'
    metadata: Optional[Dict[str, Any]] = None
    
    def is_valid(self) -> bool:
        """Check if translation is valid"""
        return len(self.translated.strip()) > 0


class BaseTranslator(ABC):
    """
    Abstract base class for translators
    """
    
    def __init__(
        self,
        source_lang: str = 'zh',
        target_lang: str = 'vi',
        cache_size: int = 10000
    ):
        """
        Initialize translator
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            cache_size: Size of translation cache
        """
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._cache: Dict[str, str] = {}
        self._cache_lock = threading.Lock()
        self._cache_size = cache_size
        self._initialized = False
        
        logger.info(f"Translator initialized: {source_lang} -> {target_lang}")
    
    @abstractmethod
    def _translate_single(self, text: str) -> str:
        """
        Translate a single text (implementation specific)
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        pass
    
    @abstractmethod
    def _translate_batch_internal(self, texts: List[str]) -> List[str]:
        """
        Internal batch translation (implementation specific)
        
        Args:
            texts: List of texts to translate
        
        Returns:
            List of translated texts
        """
        pass
    
    def translate(self, text: str) -> TranslationResult:
        """
        Translate text with caching
        
        Args:
            text: Text to translate
        
        Returns:
            TranslationResult
        """
        if not text or not text.strip():
            return TranslationResult(
                original=text,
                translated="",
                confidence=0.0
            )
        
        # Check cache
        cache_key = text.strip().lower()
        with self._cache_lock:
            if cache_key in self._cache:
                return TranslationResult(
                    original=text,
                    translated=self._cache[cache_key],
                    confidence=1.0,
                    metadata={'cached': True}
                )
        
        # Translate
        try:
            translated = self._translate_single(text)
            
            # Cache result
            with self._cache_lock:
                if len(self._cache) >= self._cache_size:
                    # Simple cache eviction: remove first 100 items
                    keys_to_remove = list(self._cache.keys())[:100]
                    for key in keys_to_remove:
                        del self._cache[key]
                
                self._cache[cache_key] = translated
            
            return TranslationResult(
                original=text,
                translated=translated,
                confidence=0.9,  # Default confidence
                metadata={'cached': False}
            )
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return TranslationResult(
                original=text,
                translated=text,  # Fallback to original
                confidence=0.0,
                metadata={'error': str(e)}
            )
    
    def translate_batch(
        self, 
        texts: List[str],
        show_progress: bool = True
    ) -> List[TranslationResult]:
        """
        Translate multiple texts with caching
        
        Args:
            texts: List of texts to translate
            show_progress: Whether to show progress
        
        Returns:
            List of TranslationResults
        """
        if not texts:
            return []
        
        results = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache for each text
        with self._cache_lock:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results.append(TranslationResult(original=text, translated="", confidence=0.0))
                else:
                    cache_key = text.strip().lower()
                    if cache_key in self._cache:
                        results.append(TranslationResult(
                            original=text,
                            translated=self._cache[cache_key],
                            confidence=1.0,
                            metadata={'cached': True}
                        ))
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(i)
        
        # Translate uncached texts
        if uncached_texts:
            try:
                translated = self._translate_batch_internal(uncached_texts)
                
                # Cache and create results
                with self._cache_lock:
                    for i, (idx, orig_text) in enumerate(zip(uncached_indices, uncached_texts)):
                        trans_text = translated[i] if i < len(translated) else orig_text
                        cache_key = orig_text.strip().lower()
                        self._cache[cache_key] = trans_text
                        
                        results.append(TranslationResult(
                            original=orig_text,
                            translated=trans_text,
                            confidence=0.9,
                            metadata={'cached': False}
                        ))
                        
            except Exception as e:
                logger.error(f"Batch translation error: {e}")
                # Fallback: use original texts
                for idx in uncached_indices:
                    results.append(TranslationResult(
                        original=texts[idx],
                        translated=texts[idx],
                        confidence=0.0,
                        metadata={'error': str(e)}
                    ))
        
        # Sort results to original order
        results.sort(key=lambda x: texts.index(x.original) if x.original in texts else -1)
        
        return results
    
    def clear_cache(self):
        """Clear translation cache"""
        with self._cache_lock:
            self._cache.clear()
        logger.info("Translation cache cleared")
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        with self._cache_lock:
            return len(self._cache)
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if translator is available"""
        pass
