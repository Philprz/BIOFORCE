"""
Simple serveur HTTP pour tester l'interface localement sans problèmes CORS
"""
import http.server
import socketserver
import os
import socket

# On essaie plusieurs ports jusqu'à en trouver un disponible
def find_free_port(start_port=8080, max_attempts=10):
    for port_attempt in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port_attempt))
                return port_attempt
            except OSError:
                print(f"Port {port_attempt} déjà utilisé, essai du port suivant...")
    
    # Si on ne trouve pas de port libre, on retourne un port moins conventionnel
    return 9876

PORT = find_free_port()
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_interface")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        # Ajouter les en-têtes CORS
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    
    print(f"\nServeur en cours d'exécution sur le port {PORT}")
    print(f"Ouvrir http://localhost:{PORT}/test_api.html dans votre navigateur")
    print(f"Pour arrêter le serveur : appuyer sur Ctrl+C\n")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServeur arrêté par l'utilisateur")
            httpd.server_close()
