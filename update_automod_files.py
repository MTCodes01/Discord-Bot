import json
import os
import glob
from pathlib import Path

# Load the new config to get the current BAD_WORDS
import config

def update_automod_files():
    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory not found.")
        return

    # Find all automod config files
    automod_files = glob.glob(str(data_dir / "automod_*.json"))
    
    updated_count = 0
    for file_path in automod_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if the file has the bad_words module
            if "modules" in data and "bad_words" in data["modules"]:
                current_words = data["modules"]["bad_words"].get("words", [])
                
                # We only want to append new words from the global config
                # without removing any custom adjustments they might have made to 'words'
                changed = False
                for word in config.BAD_WORDS:
                    if word not in current_words:
                        current_words.append(word)
                        changed = True
                
                if changed:
                    data["modules"]["bad_words"]["words"] = current_words
                    
                    # Write the updated config back to the file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    
                    print(f"Updated {os.path.basename(file_path)} with new bad words.")
                    updated_count += 1
                else:
                    print(f"No changes needed for {os.path.basename(file_path)}.")
                    
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print(f"\nSuccessfully updated {updated_count} automod configuration files.")

if __name__ == "__main__":
    update_automod_files()
