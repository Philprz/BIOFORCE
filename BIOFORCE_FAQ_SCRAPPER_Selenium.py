from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

URL = "https://www.bioforce.org/faq/"
GECKO_DRIVER_PATH = "c:/geckodriver.exe"

options = Options()
options.add_argument("--headless")  # mode headless pour ne pas ouvrir le navigateur en mode visible (optionnel)
driver = webdriver.Firefox(service=Service(GECKO_DRIVER_PATH), options=options)

faq_data = []

try:
    driver.get(URL)

    # Attendre que les titres des FAQ soient présents
    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.accordion li .title"))
    )

    # Récupération des éléments FAQ
    faq_blocks = driver.find_elements(By.CSS_SELECTOR, "ul.accordion > li")

    for block in faq_blocks:
        try:
            title_element = block.find_element(By.CSS_SELECTOR, "h4.title")
            driver.execute_script("arguments[0].click();", title_element)  # Cliquer via JS pour éviter problèmes de clic

            # Attendre que la réponse devienne visible
            answer_element = WebDriverWait(block, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.desc"))
            )

            question = title_element.text.strip()
            answer = answer_element.text.strip()

            faq_data.append({"question": question, "answer": answer})

        except Exception as e:
            print(f"Erreur lors de l'extraction d'un bloc : {e}")

finally:
    driver.quit()

# Sauvegarde en JSON
with open("faq_data.json", "w", encoding="utf-8") as f:
    json.dump(faq_data, f, ensure_ascii=False, indent=4)

print("Extraction terminée, données enregistrées dans faq_data.json.")