import requests
import json

url = "https://bioforce.onrender.com/chat"
payload = {
    "user_id": "test_user",
    "messages": [
        {
            "role": "user",
            "content": "Combien de temps faut-il pour recevoir une réponse après avoir soumis ma candidature ?"
        }
    ],
    "context": {}
}

response = requests.post(url, json=payload)
print(f"Status code: {response.status_code}")
print(json.dumps(response.json(), indent=2))