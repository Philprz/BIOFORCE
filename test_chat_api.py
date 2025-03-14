import asyncio
import httpx
import json

async def test_chat_api():
    """Test de l'endpoint chat de l'API"""
    url = "http://localhost:8000/chat"
    headers = {"Content-Type": "application/json"}
    
    # Format précis attendu par l'API
    data = {
        "user_id": "test-user-123",
        "messages": [
            {
                "role": "user",
                "content": "Bonjour, pouvez-vous me donner des informations sur les formations Bioforce?"
            }
        ],
        "context": {
            "page": "/index.html",
            "candidature_id": "00080932"
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("Envoi de la requête à l'API chat...")
            response = await client.post(url, json=data, headers=headers, timeout=30.0)
            print(f"Statut: {response.status_code}")
            
            if response.status_code == 200:
                print(f"Réponse: {json.dumps(response.json(), indent=2)}")
            else:
                print(f"Erreur: {response.text}")
                
        except Exception as e:
            print(f"Erreur: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_chat_api())
