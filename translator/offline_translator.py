"""
Offline Translator using MarianMT (Helsinki-NLP)
Chinese to Vietnamese translation model
"""
import os
from typing import List, Optional, Dict, Any
import threading
from concurrent.futures import ThreadPoolExecutor
import time

import numpy as np

from utils.logger import get_logger
from .translator import BaseTranslator


logger = get_logger(__name__)


class OfflineTranslator(BaseTranslator):
    """
    Offline translator using HuggingFace Transformers
    Uses MarianMT model for Chinese to Vietnamese translation
    """
    
    _instance = None
    _init_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        source_lang: str = 'zh',
        target_lang: str = 'vi',
        cache_size: int = 10000,
        model_name: Optional[str] = None,
        use_gpu: bool = True,
        batch_size: int = 32,
        max_length: int = 512
    ):
        """
        Initialize offline translator
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            cache_size: Translation cache size
            model_name: HuggingFace model name (auto-selected if None)
            use_gpu: Use GPU if available
            batch_size: Batch size for translation
            max_length: Maximum sequence length
        """
        # Skip if already initialized
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        super().__init__(source_lang, target_lang, cache_size)
        
        self.model_name = model_name or self._get_default_model()
        self.use_gpu = use_gpu
        self.batch_size = batch_size
        self.max_length = max_length
        
        self._device = None
        self._model = None
        self._tokenizer = None
        self._workers = 4
        
        logger.info(f"OfflineTranslator initializing with model: {self.model_name}")
    
    def _get_default_model(self) -> str:
        """Get default model for Chinese to Vietnamese"""
        # MarianMT models from Helsinki-NLP
        return "Helsinki-NLP/opus-mt-zh-vi"
    
    def _initialize(self):
        """Initialize the translation model"""
        if self._initialized:
            return
        
        try:
            import torch
            from transformers import MarianMTModel, MarianTokenizer
            
            # Determine device
            if self.use_gpu and torch.cuda.is_available():
                self._device = torch.device('cuda')
                logger.info("Using GPU for translation")
            else:
                self._device = torch.device('cpu')
                logger.info("Using CPU for translation")
            
            # Load tokenizer
            logger.info(f"Loading tokenizer: {self.model_name}")
            self._tokenizer = MarianTokenizer.from_pretrained(self.model_name)
            
            # Load model
            logger.info(f"Loading model: {self.model_name}")
            self._model = MarianMTModel.from_pretrained(self.model_name)
            self._model.to(self._device)
            self._model.eval()
            
            self._initialized = True
            logger.info("OfflineTranslator initialized successfully")
            
        except ImportError as e:
            logger.error(f"Required packages not installed: {e}")
            logger.info("Install with: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize translator: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if translator is available"""
        return self._initialized and self._model is not None
    
    def _translate_single(self, text: str) -> str:
        """Translate single text"""
        if not self._initialized:
            self._initialize()
        
        try:
            # Tokenize
            inputs = self._tokenizer(
                text, 
                return_tensors="pt", 
                padding=True,
                max_length=self.max_length,
                truncation=True
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Translate
            with torch.no_grad():
                outputs = self._model.generate(**inputs)
            
            # Decode
            translated = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            return translated.strip()
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
    
    def _translate_batch_internal(self, texts: List[str]) -> List[str]:
        """Translate batch of texts"""
        if not self._initialized:
            self._initialize()
        
        if not texts:
            return []
        
        try:
            # Tokenize all texts
            inputs = self._tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                max_length=self.max_length,
                truncation=True
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Translate in batches
            all_outputs = []
            batch_size = self.batch_size
            
            with torch.no_grad():
                for i in range(0, len(texts), batch_size):
                    batch_inputs = {
                        k: v[i:i+batch_size] for k, v in inputs.items()
                    }
                    outputs = self._model.generate(**batch_inputs)
                    all_outputs.extend(outputs)
            
            # Decode all
            translated = [
                self._tokenizer.decode(out, skip_special_tokens=True).strip()
                for out in all_outputs
            ]
            
            return translated
            
        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            return texts  # Fallback
    
    def translate_with_context(
        self,
        texts: List[str],
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None
    ) -> List[str]:
        """
        Translate with surrounding context for better translation
        
        Args:
            texts: Texts to translate
            context_before: Context before each text
            context_after: Context after each text
        
        Returns:
            List of translations
        """
        if not self._initialized:
            self._initialize()
        
        if not context_before:
            context_before = [""] * len(texts)
        if not context_after:
            context_after = [""] * len(texts)
        
        # Prepend and append context
        extended_texts = [
            f"{ctx_b} {text} {ctx_a}".strip()
            for text, ctx_b, ctx_a in zip(texts, context_before, context_after)
        ]
        
        # Translate
        translated = self._translate_batch_internal(extended_texts)
        
        # Remove context (crude but works for short contexts)
        results = []
        for orig, trans in zip(texts, translated):
            # Try to find and remove original text from translation
            if orig in trans:
                trans = trans.replace(orig, "", 1).strip()
            # Also try reversed
            if orig[::-1] in trans[::-1]:
                results.append(trans.replace(orig, "", 1).strip())
            else:
                results.append(trans)
        
        return results
    
    def warmup(self):
        """Warmup the model with dummy input"""
        if not self._initialized:
            self._initialize()
        
        dummy_texts = ["你好", "你好吗", "很好"] * 3
        self._translate_batch_internal(dummy_texts)
        logger.info("Translator warmup complete")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        if not self._initialized:
            return {'initialized': False}
        
        return {
            'initialized': self._initialized,
            'model_name': self.model_name,
            'device': str(self._device),
            'batch_size': self.batch_size,
            'max_length': self.max_length,
            'cache_size': self.get_cache_size()
        }


class SimpleOfflineTranslator(BaseTranslator):
    """
    Simple dictionary-based translator for offline use
    Used as fallback when model is not available
    """
    
    def __init__(
        self,
        source_lang: str = 'zh',
        target_lang: str = 'vi'
    ):
        super().__init__(source_lang, target_lang, cache_size=5000)
        
        # Common Chinese phrases dictionary
        self._dictionary = self._build_dictionary()
        self._initialized = True
    
    def _build_dictionary(self) -> Dict[str, str]:
        """Build basic dictionary"""
        # Basic common phrases
        return {
            # Greetings
            "你好": "Xin chào",
            "您好": "Xin chào",
            "早上好": "Chào buổi sáng",
            "晚上好": "Chào buổi tối",
            "晚安": "Ngủ ngon",
            "再见": "Tạm biệt",
            "拜拜": "Tạm biệt",
            
            # Common words
            "谢谢": "Cảm ơn",
            "感谢": "Cảm ơn",
            "对不起": "Xin lỗi",
            "抱歉": "Xin lỗi",
            "请": "Xin vui lòng",
            "是": "Vâng",
            "不是": "Không phải",
            "好的": "Được",
            "可以": "Có thể",
            "知道": "Biết",
            "不知道": "Không biết",
            
            # Questions
            "什么": "Gì",
            "谁": "Ai",
            "哪里": "Ở đâu",
            "怎么": "Làm sao",
            "为什么": "Tại sao",
            "多少": "Bao nhiêu",
            "几": "Mấy",
            
            # Time
            "现在": "Bây giờ",
            "今天": "Hôm nay",
            "明天": "Ngày mai",
            "昨天": "Hôm qua",
            "时间": "Thời gian",
            
            # Common phrases
            "我知道了": "Tôi hiểu rồi",
            "我明白了": "Tôi hiểu rồi",
            "没关系": "Không sao",
            "没问题": "Không vấn đề gì",
            "一定": "Nhất định",
            "可能": "Có thể",
            "应该": "Nên",
            
            # Numbers (1-10)
            "一": "Một",
            "二": "Hai",
            "三": "Ba",
            "四": "Bốn",
            "五": "Năm",
            "六": "Sáu",
            "七": "Bảy",
            "八": "Tám",
            "九": "Chín",
            "十": "Mười",
        }
    
    def is_available(self) -> bool:
        return True
    
    def _translate_single(self, text: str) -> str:
        """Translate using dictionary lookup"""
        # Check dictionary
        if text in self._dictionary:
            return self._dictionary[text]
        
        # Try word by word
        words = list(text)
        translated_words = []
        
        for word in words:
            if word in self._dictionary:
                translated_words.append(self._dictionary[word])
            else:
                translated_words.append(word)
        
        result = " ".join(translated_words)
        
        if result == text:
            logger.warning(f"No translation found for: {text}")
        
        return result
    
    def _translate_batch_internal(self, texts: List[str]) -> List[str]:
        """Translate batch using dictionary"""
        return [self._translate_single(text) for text in texts]


def create_translator(
    use_offline: bool = True,
    use_gpu: bool = True,
    **kwargs
) -> BaseTranslator:
    """
    Factory function to create translator
    
    Args:
        use_offline: Use offline translation (MarianMT)
        use_gpu: Use GPU if available
        **kwargs: Additional arguments
    
    Returns:
        Translator instance
    """
    if use_offline:
        try:
            return OfflineTranslator(use_gpu=use_gpu, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to create OfflineTranslator: {e}")
            logger.info("Falling back to SimpleOfflineTranslator")
            return SimpleOfflineTranslator()
    else:
        return SimpleOfflineTranslator()
