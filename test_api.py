import asyncio
import httpx
import json

async def test_debug_api():
    """Test de l'endpoint de débogage de l'API"""
    url = "http://localhost:8000/debug"
    headers = {"Content-Type": "application/json"}
    data = {"test": "value"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            print(f"Statut: {response.status_code}")
            print(f"Réponse: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Erreur: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_debug_api())
