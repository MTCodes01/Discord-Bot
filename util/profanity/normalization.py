import re
from typing import Tuple, List

class URLHandler:
    # Basic URL regex
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )

    @staticmethod
    def extract_and_strip_urls(text: str) -> Tuple[str, List[str]]:
        """Finds URLs, removes them from text, and returns the cleaned text + list of URLs."""
        urls = URLHandler.URL_PATTERN.findall(text)
        stripped_text = URLHandler.URL_PATTERN.sub('', text)
        return stripped_text, urls


class TextNormalizer:
    LEET_MAPPING = {
        '0': 'o',
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '@': 'a',
        '$': 's',
        '8': 'b',
        '9': 'g',
        '7': 't',
        '2': 'z'
    }

    @staticmethod
    def normalize_leetspeak(text: str) -> str:
        """Converts leetspeak characters to their normal equivalents."""
        result = text.lower()
        for leet_char, normal_char in TextNormalizer.LEET_MAPPING.items():
            result = result.replace(leet_char, normal_char)
        return result

    @staticmethod
    def collapse_repeated_characters(text: str) -> str:
        """Collapses 2 or more repeated characters down to 1 (e.g. fuuuuuck -> fuck)."""
        return re.sub(r'(.)\1+', r'\1', text)

    @staticmethod
    def remove_punctuation(text: str) -> str:
        """Removes excessive punctuation including underscores."""
        return re.sub(r'[^a-zA-Z0-9\s]', '', text)

    @staticmethod
    def compress_text(text: str) -> str:
        """Removes all spaces and punctuation to detect obfuscation (e.g. f u c k -> fuck)."""
        return re.sub(r'\s+', '', text)


class Tokenizer:
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Splits normalized text into words using word boundary detection."""
        # Split by whitespace
        return text.split()
