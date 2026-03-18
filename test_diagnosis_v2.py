
import sys
import os
import asyncio
import json
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

# Setup detailed logging to stdout
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

from backend.ai_engine.ollama_client import run_ai_optimized
from backend.prompts.diagnosis_prompt import build_diagnosis_prompt_optimized

case_data = {
    "patient_age": 45,
    "geographic_region": "North America",
    "complaint": "Itchy red rash on elbows",
    "lesion": "Symmetric erythematous plaques with silvery scale",
    "symptoms": "Itching, mild burning, bleeding when scratched (Auspitz sign)",
    "tests": "None"
}

print("Building prompt...")
prompt = build_diagnosis_prompt_optimized(case_data)
print("Prompt length:", len(prompt))

print("\nCalling Ollama with format='json'...")
try:
    # Call directly to see what ollama.chat returns
    raw_response = run_ai_optimized(prompt, max_tokens=1536, format="json")
    print("\nRAW RESPONSE FROM OLLAMA:")
    print("-" * 50)
    print(raw_response)
    print("-" * 50)
    
    print("\nAttempting to parse as JSON...")
    try:
        parsed = json.loads(raw_response)
        print("PARSING SUCCESS!")
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError as e:
        print(f"PARSING FAILED: {e}")
        # Try to clean it using the same logic as our validator
        from backend.ai_engine.json_validator import extract_json_from_text
        cleaned = extract_json_from_text(raw_response)
        print("\nCLEANED JSON:")
        print(cleaned)
        try:
            parsed = json.loads(cleaned)
            print("PARSING SUCCESS AFTER CLEANING!")
        except Exception as e2:
            print(f"PARSING STILL FAILED: {e2}")

except Exception as e:
    print(f"ERROR calling Ollama: {e}")
