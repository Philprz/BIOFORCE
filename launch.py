"""
Script de lancement unifié pour Bioforce Scraper
Ce script permet de lancer l'application FastAPI avec l'interface d'administration
"""
import os
import sys
import argparse
import asyncio
import subprocess
import webbrowser
import time
from pathlib import Path
import requests

# Ajouter le répertoire courant au path pour les imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from bioforce_scraper.config import API_HOST, API_PORT

def run_command(command):
    """Exécute une commande système"""
    print(f"Exécution de: {' '.join(command)}")
    process = subprocess.Popen(
        command, 
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    for line in process.stdout:
        print(line, end='')
    
    process.wait()
    return process.returncode

def open_browser(host, port):
    """Ouvre le navigateur avec l'interface admin"""
    url = f"http://{host}:{port}/admin" if host != "0.0.0.0" else f"http://localhost:{port}/admin"
    print(f"\nOuverture du navigateur à l'adresse: {url}")
    webbrowser.open(url)

def start_api(open_browser):
    """Démarrer l'API"""
    python_exec = sys.executable
    cmd = [python_exec, "-m", "bioforce_scraper.api.app"]
    
    # Lancer l'API dans un processus séparé
    api_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    # Attendre que le serveur soit prêt (en vérifiant la sortie)
    server_ready = False
    for line in api_process.stdout:
        print(line, end='')
        if "Application startup complete" in line:
            server_ready = True
            break
    
    # Si le serveur est prêt et qu'on a demandé d'ouvrir le navigateur
    if server_ready and open_browser:
        # Attendre un peu pour s'assurer que le serveur est complètement prêt
        time.sleep(1)
        # Ouvrir le navigateur
        display_host = "localhost" if API_HOST == "0.0.0.0" else API_HOST
        open_browser(display_host, API_PORT)
    
    return api_process

def parse_args():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(description="Lance l'API et les scrapers Bioforce")
    parser.add_argument("--faq", action="store_true", help="Lance aussi le scraper de FAQ")
    parser.add_argument("--full", action="store_true", help="Lance aussi le scraper de site complet")
    parser.add_argument("--all", action="store_true", help="Lance tous les composants (API, FAQ, site complet)")
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir le navigateur automatiquement")
    parser.add_argument("--force-update", action="store_true", help="Force la mise à jour des scrapers")
    return parser.parse_args()

def main():
    """Fonction principale"""
    args = parse_args()
    
    print("\n========================")
    print(" Bioforce Scraper v1.0")
    print("========================\n")
    
    # Si --all est spécifié, activer tous les composants
    if args.all:
        args.faq = True
        args.full = True
    
    # Démarrer l'API (toujours)
    api_process = start_api(not args.no_browser)
    
    try:
        # Attendre 3 secondes que l'API démarre avant de continuer
        print("Démarrage de l'API en cours...")
        time.sleep(3)
        
        # Lancer les scrapers si demandé
        if args.faq:
            print("\nDémarrage du scraper FAQ...")
            response = requests.post(
                f"http://{API_HOST}:{API_PORT}/scrape/faq",
                json={"force_update": args.force_update}
            )
            if response.status_code == 200:
                print(f"Scraper FAQ démarré: {response.json().get('message')}")
            else:
                print(f"Erreur lors du démarrage du scraper FAQ: {response.text}")
        
        if args.full:
            print("\nDémarrage du scraper de site complet...")
            response = requests.post(
                f"http://{API_HOST}:{API_PORT}/scrape/full",
                json={"force_update": args.force_update}
            )
            if response.status_code == 200:
                print(f"Scraper de site complet démarré: {response.json().get('message')}")
            else:
                print(f"Erreur lors du démarrage du scraper de site complet: {response.text}")
        
        # Afficher les informations sur les collections
        time.sleep(3)  # Attendre que les scrapers démarrent
        
        print("\nInformations sur les collections:")
        try:
            response = requests.get(f"http://{API_HOST}:{API_PORT}/qdrant-stats")
            if response.status_code == 200:
                stats = response.json()
                faq_stats = stats.get("faq_collection", {})
                full_stats = stats.get("full_site_collection", {})
                
                print(f"- Collection FAQ (BIOFORCE): {faq_stats.get('points_count', 0)} points")
                print(f"- Collection Site Complet (BIOFORCE_ALL): {full_stats.get('points_count', 0)} points")
            else:
                print("Impossible de récupérer les statistiques des collections")
        except Exception as e:
            print(f"Erreur lors de la récupération des statistiques: {e}")
        
        print("\nL'API est en cours d'exécution. Appuyez sur Ctrl+C pour quitter.")
        
        # Attendre que l'API se termine
        api_process.wait()
    
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur...")
    finally:
        # S'assurer que tous les processus sont arrêtés
        if api_process:
            try:
                api_process.terminate()
                print("API arrêtée.")
            except:
                pass

if __name__ == "__main__":
    main()
