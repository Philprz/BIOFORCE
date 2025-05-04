import requests
import json

url = "https://bioforce.onrender.com/chat"
payload = {
    "user_id": "test_user",
    "messages": [
        {
            "role": "user",
            "content": "Comment puis-je modifier mes informations personnelles dans mon espace candidat ?"
        }
    ],
    "context": {}
}

response = requests.post(url, json=payload)
print(f"Status code: {response.status_code}")
print(json.dumps(response.json(), indent=2))