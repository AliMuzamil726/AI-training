import requests

API_KEY = "sk_4864bd6f9c07410dbe4892fee904f32b6385408576fbd131"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

url = (
    f"https://api.elevenlabs.io/v1/text-to-speech/"
    f"{VOICE_ID}?output_format=mp3_44100_128"
)

headers = {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "text": "The first move is what sets everything in motion.",
    "model_id": "eleven_multilingual_v2"
}

response = requests.post(
    url,
    headers=headers,
    json=payload
)

print("Status:", response.status_code)

if response.ok:
    with open("speech.mp3", "wb") as f:
        f.write(response.content)
    print("Audio saved as speech.mp3")
else:
    print(response.text)
    import requests

API_KEY = "sk_4864bd6f9c07410dbe4892fee904f32b6385408576fbd131"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

url = (
    f"https://api.elevenlabs.io/v1/text-to-speech/"
    f"{VOICE_ID}?output_format=mp3_44100_128"
)

headers = {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "text": "The first move is what sets everything in motion.",
    "model_id": "eleven_multilingual_v2"
}

response = requests.post(
    url,
    headers=headers,
    json=payload
)

print("Status:", response.status_code)

if response.ok:
    with open("speech.mp3", "wb") as f:
        f.write(response.content)
    print("Audio saved as speech.mp3")
else:
    print(response.text)