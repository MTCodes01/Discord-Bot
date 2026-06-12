from dataclasses import dataclass
from typing import Optional, List, Tuple
import re
from rapidfuzz import fuzz
from .config import ProfanityConfig
from .normalization import URLHandler, TextNormalizer, Tokenizer

@dataclass
class DetectionResult:
    is_profane: bool
    confidence: int
    matched_word: Optional[str]
    detection_method: Optional[str]
    original_text: str
    normalized_text: str

class ProfanityDetector:
    def __init__(self, config: ProfanityConfig):
        self.config = config

    def analyze(self, text: str) -> DetectionResult:
        """
        Analyzes text for profanity and returns a DetectionResult.
        """
        if not text:
            return DetectionResult(False, self.config.CONFIDENCE_SAFE, None, None, text, "")

        # 1. URL Handling - Extract and strip URLs
        clean_text, urls = URLHandler.extract_and_strip_urls(text)
        
        if not clean_text.strip():
            return DetectionResult(False, self.config.CONFIDENCE_SAFE, None, None, text, "")

        # 2. Normalization
        leetspeak_normalized = TextNormalizer.normalize_leetspeak(clean_text)
        no_punct_text = TextNormalizer.remove_punctuation(leetspeak_normalized)
        
        # 3. Tokenization
        words = Tokenizer.tokenize(no_punct_text)
        
        # We will keep track of the highest confidence found
        best_confidence = self.config.CONFIDENCE_SAFE
        best_match = None
        best_method = None

        def update_best(conf, match, method):
            nonlocal best_confidence, best_match, best_method
            if conf > best_confidence:
                best_confidence = conf
                best_match = match
                best_method = method

        # 4. Exact Match Detection
        for word in words:
            if word in self.config.whitelist:
                continue
                
            if word in self.config.bad_words:
                update_best(self.config.CONFIDENCE_EXACT, word, "Exact Match")
                break # 100 confidence, can't get higher

        # If we found an exact match, return early to save CPU
        if best_confidence == self.config.CONFIDENCE_EXACT:
            return DetectionResult(True, best_confidence, best_match, best_method, text, no_punct_text)

        # 5. Obfuscation Detection
        # To avoid false positives (e.g. "class" -> "ass"), remove whitelisted words first
        obfuscation_text = no_punct_text
        for w in self.config.whitelist:
            # Replace whitelisted words with spaces to avoid creating new false positives by concatenating
            obfuscation_text = re.sub(r'\b' + re.escape(w) + r'\b', ' ', obfuscation_text)
            
        compressed_text = TextNormalizer.compress_text(obfuscation_text)
        
        for bad_word in self.config.bad_words:
            if bad_word in compressed_text:
                # To be safe against very short bad words matching random letter combinations,
                # we only trigger obfuscation for words >= 3 chars.
                if len(bad_word) >= 3:
                    update_best(self.config.CONFIDENCE_OBFUSCATION, bad_word, "Obfuscation")

        if best_confidence >= self.config.CONFIDENCE_OBFUSCATION:
            return DetectionResult(True, best_confidence, best_match, best_method, text, compressed_text)

        # 6. Fuzzy Matching
        for word in words:
            if word in self.config.whitelist:
                continue
                
            collapsed_word = TextNormalizer.collapse_repeated_characters(word)
            if collapsed_word in self.config.whitelist:
                continue

            for bad_word in self.config.bad_words:
                # Only compare words of similar length to prevent excessive CPU usage and false positives
                if abs(len(collapsed_word) - len(bad_word)) <= 2:
                    score = fuzz.ratio(collapsed_word, bad_word)
                    
                    if score >= 85:
                        update_best(self.config.CONFIDENCE_CLOSE_VARIATION, bad_word, "Fuzzy Match (Close)")
                    elif score >= 70:
                        update_best(self.config.CONFIDENCE_SUSPICIOUS, bad_word, "Fuzzy Match (Suspicious)")

        is_profane = best_confidence >= self.config.CONFIDENCE_SUSPICIOUS
        
        return DetectionResult(
            is_profane=is_profane,
            confidence=best_confidence,
            matched_word=best_match,
            detection_method=best_method,
            original_text=text,
            normalized_text=no_punct_text
        )
