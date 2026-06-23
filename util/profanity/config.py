import json
from pathlib import Path
from typing import Set, List
import config as root_config

class ProfanityConfig:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.bad_words_file = self.data_dir / "bad_words.json"
        self.whitelist_file = self.data_dir / "whitelist.json"
        
        self.bad_words: Set[str] = set()
        self.whitelist: Set[str] = set()
        self.common_safe_words: Set[str] = {
            "hello", "assistant", "class", "night", "classroom", 
            "pass", "grass", "glass", "mass", "bass", "classic", 
            "analyze", "title", "button", "document", "assignment",
            "country", "count", "this", "that", "they", "them", "what",
            "with", "from", "have", "good", "there", "cant", "cannot", "can't"
        }
        
        # Confidence Thresholds
        self.CONFIDENCE_EXACT = 100
        self.CONFIDENCE_OBFUSCATION = 95
        self.CONFIDENCE_CLOSE_VARIATION = 85
        self.CONFIDENCE_SUSPICIOUS = 70
        self.CONFIDENCE_SAFE = 0
        
        self.load_config()
        
    def load_config(self):
        """Loads bad words and whitelist into memory as sets for O(1) lookups."""
        # Load Bad Words
        if self.bad_words_file.exists():
            try:
                with open(self.bad_words_file, 'r', encoding='utf-8') as f:
                    custom_bad_words = set(json.load(f))
                    self.bad_words.update(custom_bad_words)
            except Exception:
                pass
        
        # Always add root config BAD_WORDS to memory
        if hasattr(root_config, 'BAD_WORDS') and root_config.BAD_WORDS:
            self.bad_words.update(root_config.BAD_WORDS)
            
        # Load Whitelist
        if self.whitelist_file.exists():
            try:
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    self.whitelist = set(json.load(f))
            except Exception:
                pass
                
        # Add common safe words to whitelist for the detector
        self.whitelist.update(self.common_safe_words)
        
        # Normalize bad words just in case
        self.bad_words = {word.lower() for word in self.bad_words}
        self.whitelist = {word.lower() for word in self.whitelist}

    def add_bad_word(self, word: str) -> bool:
        word = word.lower()
        if word in self.bad_words:
            return False
        
        self.bad_words.add(word)
        self._save_bad_words()
        return True
        
    def remove_bad_word(self, word: str) -> bool:
        word = word.lower()
        if word in self.bad_words:
            self.bad_words.remove(word)
            self._save_bad_words()
            return True
        return False
        
    def add_whitelist_word(self, word: str) -> bool:
        word = word.lower()
        if word in self.whitelist:
            return False
            
        self.whitelist.add(word)
        # We only save non-default whitelist words to file
        save_list = [w for w in self.whitelist if w not in self.common_safe_words]
        self._save_json(self.whitelist_file, save_list)
        return True
        
    def _save_bad_words(self):
        # Only save words that are not in the root config to prevent duplication
        root_words = set(getattr(root_config, 'BAD_WORDS', []))
        custom_words = [w for w in self.bad_words if w not in root_words]
        self._save_json(self.bad_words_file, custom_words)
        
    def _save_json(self, path: Path, data: List[str]):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(list(data), f, indent=2)
        except Exception:
            pass
