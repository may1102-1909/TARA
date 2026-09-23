import httpx
import json

def test_stream():
    client = httpx.Client(timeout=30.0)
    payload = {
        "model": "qwen2.5:7b",
        "messages": [
            {
                "role": "system",
                "content": "You are a Senior Python Developer. Output ONLY valid, executable Python code with no markdown formatting or fences."
            },
            {
                "role": "user",
                "content": "Replace the name 'RTI ONE CLICK' with 'RTI OneClick' in the following code:\n\napp_name = 'RTI ONE CLICK'\nversion = '1.0.0'\n"
            }
        ],
        "stream": True,
        "temperature": 0.1
    }
    with client.stream("POST", "http://localhost:11434/v1/chat/completions", json=payload) as resp:
        for line in resp.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                delta = data["choices"][0]["delta"].get("content", "")
                print(delta, end="", flush=True)
    print("\n[STREAM COMPLETE]")

if __name__ == "__main__":
    test_stream()
