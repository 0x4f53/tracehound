import os
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "codellama:latest"  # Or use another LLM like 'codebert', if available in Ollama

def read_text_files_from_directory(directory_path):
    file_contents = {}
    for filename in os.listdir(directory_path):
        with open(os.path.join(directory_path, filename), 'r', encoding='utf-8') as file:
            file_contents[filename] = file.read()
    return file_contents

def analyze_code_with_ollama(code, model=MODEL_NAME):
    prompt = f"""
You are a security research assistant. Analyze the given code and provide a structured summary with the following information if found:
- Detected secrets (e.g., API keys, passwords, tokens), their names/types, and counts.
- Vulnerable code snippets (with line numbers or context).
- URLs or domains present in the code.
- Any other suspicious or risky patterns, such as:
    - Use of hardcoded credentials
    - Unsafe eval/exec
    - Insecure cryptography
    - Obfuscated code
    - Dangerous environment variable usage
    - Anything else that seems unusual or high risk.
Respond in JSON with fields: detected_secrets (list), secret_names (list), secret_count (int), vulnerable_snippets (list), urls (list), domains (list), suspicious_observations (list).
Here is the code:
---
{code}
---
"""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    try:
        # Ollama streams output as chunks; for non-stream, parse main response or last chunk.
        data = response.json()
        # Some models may return their output inside a "response" key.
        output = data.get("response", data)
        # Try parsing as JSON (LLM may return pre-formatted JSON)
        try:
            result = json.loads(output)
        except Exception:
            result = {"raw_response": output}
        return result
    except Exception as e:
        return {"error": str(e), "raw_response": response.text}

def main(directory_path="./code_files"):
    files = read_text_files_from_directory(directory_path)
    for fname, code in files.items():
        print(f"Analyzing file: {fname}")
        result = analyze_code_with_ollama(code)
        print(json.dumps(result, indent=2))
        print("\n" + "-"*50 + "\n")

if __name__ == "__main__":
    main()
