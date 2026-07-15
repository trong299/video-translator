"""
Translator module for Chinese to Vietnamese translation
"""
from .translator import BaseTranslator, TranslationResult
from .offline_translator import OfflineTranslator

__all__ = ['BaseTranslator', 'TranslationResult', 'OfflineTranslator']
