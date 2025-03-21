#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script pour lancer l'API Bioforce et ouvrir l'interface de chat
Ce script est conçu pour lancer l'API et ouvrir directement l'interface de chat
sans modifier le comportement standard de l'API.
"""

import os
import sys
import time
import webbrowser
import subprocess
import signal
import atexit

# Configuration
HOST = "localhost"  # ou "0.0.0.0" pour accès externe
PORT = 8000
CHAT_INTERFACE_PATH = "demo_interface/chat.html"  # Chemin vers la nouvelle interface de chat

# Variables globales pour les processus
api_process = None

def cleanup():
    """Nettoyage à la sortie du programme"""
    global api_process
    if api_process:
        print("\nArrêt de l'API...")
        try:
            if os.name == 'nt':  # Windows
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(api_process.pid)])
            else:  # Unix/Linux/Mac
                os.killpg(os.getpgid(api_process.pid), signal.SIGTERM)
        except Exception as e:
            print(f"Erreur lors de l'arrêt du processus: {e}")

def start_api():
    """Démarrer l'API"""
    python_exec = sys.executable
    cmd = [python_exec, "-m", "bioforce_scraper.api.app"]
    
    # Lancer l'API dans un processus séparé
    global api_process
    print("Démarrage de l'API en cours...")
    
    if os.name == 'nt':  # Windows
        api_process = subprocess.Popen(cmd, shell=True)
    else:  # Unix/Linux/Mac
        api_process = subprocess.Popen(cmd, preexec_fn=os.setsid)
    
    # Attendre que l'API démarre
    time.sleep(3)  # Attendre 3 secondes pour le démarrage

def open_chat_interface():
    """Ouvre le navigateur avec l'interface de chat"""
    # Construire le chemin absolu vers l'interface de chat
    current_dir = os.path.dirname(os.path.abspath(__file__))
    chat_interface = os.path.join(current_dir, CHAT_INTERFACE_PATH)
    
    # Vérifier que le fichier existe
    if not os.path.exists(chat_interface):
        print(f"Erreur: L'interface de chat n'a pas été trouvée à {chat_interface}")
        return False
    
    # Construire l'URL avec le protocole file://
    chat_url = f"file://{chat_interface}"
    admin_url = f"http://{HOST}:{PORT}/admin"
    
    print(f"\nOuverture de l'interface de chat à l'adresse: {chat_url}")
    print(f"Interface d'administration accessible à l'adresse: {admin_url}")
    print(f"API accessible à l'adresse: http://{HOST}:{PORT}")
    
    # Ouvrir le navigateur
    webbrowser.open(chat_url)
    return True

def main():
    """Fonction principale"""
    # Enregistrer la fonction de nettoyage pour une sortie propre
    atexit.register(cleanup)
    
    print("\n========================")
    print(" Bioforce Chat v1.0")
    print("========================\n")
    
    # Démarrer l'API
    start_api()
    
    # Ouvrir l'interface de chat
    if open_chat_interface():
        # Afficher des informations sur les collections (comme dans launch.py)
        # Ces informations seront disponibles une fois l'API démarrée
        print("\nL'API est en cours d'exécution. Appuyez sur Ctrl+C pour quitter.")
        
        try:
            # Maintenir le script en vie jusqu'à ce que l'utilisateur appuie sur Ctrl+C
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt des services...")
    else:
        print("Impossible d'ouvrir l'interface de chat. L'API reste en cours d'exécution.")
        print("Vous pouvez accéder à l'interface d'administration à l'adresse:")
        print(f"http://{HOST}:{PORT}/admin")
        print("\nAppuyez sur Ctrl+C pour quitter.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt des services...")

if __name__ == "__main__":
    main()
