import sys
from pathlib import Path

# Add the parent directory to the path so we can import util
sys.path.append(str(Path(__file__).parent))

from util.profanity.config import ProfanityConfig
from util.profanity.detector import ProfanityDetector

def run_tests():
    data_dir = Path("./data")
    config = ProfanityConfig(data_dir)
    # Add a fake bad word to test with
    config.bad_words.add("badword")
    config.bad_words.add("fuck")
    config.bad_words.add("bitch")
    config.bad_words.add("ass")
    config.bad_words.add("shit")

    detector = ProfanityDetector(config)

    tests = [
        ("Hello there!", 0, "whitelist / safe"),
        ("You are a badword", 100, "exact match"),
        ("f.u.c.k you", 95, "obfuscation with dots"),
        ("f_u_c_k", 95, "obfuscation with underscores"),
        ("f u c k", 95, "obfuscation with spaces"),
        ("b!tch", 70, "leetspeak exact / fuzzy"), # wait, "b!tch" -> "bitch" (leetspeak) -> Exact match! Should be 100
        ("b1tch", 85, "leetspeak exact / fuzzy"), # "b1tch" -> "bitch" -> Exact match 100
        ("biiitch", 85, "repeated chars"), # fuzzy match (collapse to bich, fuzzy against bitch) -> wait, collapse to bich. len(bich)=4, len(bitch)=5. ratio = 88 -> 85
        ("fuuuuuck", 85, "repeated chars"), 
        ("This is my class.", 0, "false positive: class -> ass"),
        ("What a classic!", 0, "false positive: classic -> ass"),
        ("Have a good night", 0, "false positive: night -> nig"),
        ("https://badword.com", 0, "URL handling"),
    ]

    print("Running Profanity Detector Tests...")
    print("-" * 50)
    for text, expected_min_confidence, desc in tests:
        result = detector.analyze(text)
        status = "PASS" if result.confidence >= expected_min_confidence else "FAIL"
        if result.confidence == 0 and expected_min_confidence == 0:
            status = "PASS"
        if result.confidence > 0 and expected_min_confidence == 0:
            status = "FAIL (False Positive)"
            
        print(f"{status} | '{text}' -> Conf: {result.confidence} (Method: {result.detection_method}) - {desc}")
        
    print("-" * 50)

if __name__ == "__main__":
    run_tests()
