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

def parse_arguments():
    """Parse les arguments en ligne de commande"""
    parser = argparse.ArgumentParser(description='Bioforce Scraper - Outil de lancement')
    parser.add_argument('--faq', action='store_true', help='Lancer uniquement le scraper de FAQ')
    parser.add_argument('--full', action='store_true', help='Lancer le scraper de site complet')
    parser.add_argument('--api', action='store_true', help='Lancer l\'API FastAPI avec l\'interface admin')
    parser.add_argument('--all', action='store_true', help='Lancer toutes les fonctionnalités')
    parser.add_argument('--host', type=str, default=API_HOST, help=f'Hôte pour l\'API (défaut: {API_HOST})')
    parser.add_argument('--port', type=int, default=API_PORT, help=f'Port pour l\'API (défaut: {API_PORT})')
    parser.add_argument('--no-browser', action='store_true', help='Ne pas ouvrir automatiquement le navigateur')
    return parser.parse_args()

def main():
    """Fonction principale"""
    args = parse_arguments()
    
    # Si aucune option n'est spécifiée, activer --api par défaut
    if not (args.faq or args.full or args.api or args.all):
        args.api = True
    
    # Si --all est spécifié, activer toutes les options
    if args.all:
        args.faq = True
        args.full = True
        args.api = True
    
    # Variable d'environnement pour l'hôte et le port
    os.environ['API_HOST'] = args.host
    os.environ['API_PORT'] = str(args.port)
    
    # Message d'accueil
    print("=" * 80)
    print("BIOFORCE SCRAPER - OUTIL DE LANCEMENT")
    print("=" * 80)
    print(f"Configuration:")
    print(f"- API Host: {args.host}")
    print(f"- API Port: {args.port}")
    print(f"- Mode: {'Scraper FAQ' if args.faq else ''} {'Scraper complet' if args.full else ''} {'API' if args.api else ''}")
    print("=" * 80)
    
    # Exécuter les scrapers si demandé
    if args.faq:
        print("\n[1/3] Lancement du scraper de FAQ...")
        python_exec = sys.executable
        cmd = [python_exec, "-m", "bioforce_scraper.run_scraper", "--faq-only"]
        run_command(cmd)
    
    if args.full:
        print("\n[2/3] Lancement du scraper de site complet...")
        python_exec = sys.executable
        cmd = [python_exec, "-m", "bioforce_scraper.run_scraper", "--full"]
        run_command(cmd)
    
    # Lancer l'API si demandé
    if args.api:
        print("\n[3/3] Lancement de l'API FastAPI avec l'interface d'administration...")
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
        
        # Si le serveur est prêt et qu'on n'a pas demandé de ne pas ouvrir le navigateur
        if server_ready and not args.no_browser:
            # Attendre un peu pour s'assurer que le serveur est complètement prêt
            time.sleep(1)
            # Ouvrir le navigateur
            display_host = "localhost" if args.host == "0.0.0.0" else args.host
            open_browser(display_host, args.port)
        
        # Continuer à afficher la sortie du serveur
        for line in api_process.stdout:
            print(line, end='')
    
    print("\nTous les processus demandés ont été lancés.")
    
    # Si l'API a été lancée, garder le script en cours d'exécution
    if args.api and 'api_process' in locals():
        try:
            api_process.wait()
        except KeyboardInterrupt:
            print("\nInterruption détectée. Arrêt des processus...")
            api_process.terminate()
            print("Serveur arrêté.")

if __name__ == "__main__":
    main()
