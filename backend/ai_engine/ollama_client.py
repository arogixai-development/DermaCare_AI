import ollama

def run_ai(prompt: str):
    response = ollama.chat(
        model="phi3",
        messages=[
            {"role": "user", "content": prompt}
        ],
        options={
            "temperature": 0.2,
            "num_predict": 512, # Sufficient for medical notes/diagnoses
            "top_p": 0.9
        }
    )
    return response["message"]["content"]
