import requests
import json
import os
import sys

DEFAULT_SERVER = "192.168.178.67:5000"
CLIENT_KEY = "lsz4/+!R[fJ]rsTI|9QPl{cfc3\"OV0#Z$ldbgC!\"bQ<49sPVC5T`jys1MovLqX"

def fetch_and_render(url):
    try:
        if "://" not in url:
            url = f"http://{url}"
        
        headers = {"X-API-Key": CLIENT_KEY}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        page_data = response.json()
        
        links = []
        
        if isinstance(page_data, list):
            print(f"\n--- Suchergebnisse für '{url}' ---")
            if not page_data:
                print("Keine Ergebnisse gefunden.")
            
            for item in page_data:
                if isinstance(item, dict) and "url" in item and "content" in item:
                    links.append(item["url"])
                    print(f"[{len(links)}] {item['url']}\n    {item['content']}")
            return links
        
        elif isinstance(page_data, dict):
            markup_content = page_data.get("markup")
            if markup_content is None and isinstance(page_data.get("source_code"), dict):
                markup_content = page_data["source_code"].get("markup")

            if markup_content:
                print(f"\n--- Seite '{url}' wird geladen ---")
                
                for line in markup_content:
                    line_stripped = line.strip()
                    if not line_stripped.startswith("<"):
                        continue

                    if line_stripped.startswith("<t>"):
                        text_part = line_stripped.split(";", 1)[0].replace("<t>", "").replace(" <nl> ", '\n').strip()
                        print(text_part)

                    elif line_stripped.startswith("<e>"):
                        entry_text = line_stripped.split(";", 1)[0].replace("<e>", "").strip()
                        print(f"[{entry_text}]")
                        
                    elif line_stripped.startswith("<a>"):
                        parts = line_stripped.split("href")
                        if len(parts) > 1:
                            link_text = parts[0].replace("<a>", "").strip()
                            href_url = parts[1].split()[0]
                            links.append(href_url)
                            print(f"[{len(links)}] {link_text}")

                    elif line_stripped.startswith("<img>"):
                        image_url = line_stripped.split()[1]
                        print(f"[Bild: {image_url}]")
                    
                    elif line_stripped.startswith("<mainbg>"):
                        bg_color = line_stripped.split()[1]
                        print(f"[Hintergrundfarbe: {bg_color}]")
                        
                    elif line_stripped.startswith("<script>"):
                        print("[Skript wird ausgeführt]")

        return links
        
    except requests.exceptions.RequestException as e:
        print(f"Fehler: {e}")
        return None
    except json.JSONDecodeError:
        print("Fehler: Server-Antwort ist kein gültiges JSON.")
        return None

def main_loop():
    print("Willkommen im Konsolen-Browser!")
    
    initial_url = input("URL eingeben (z.B. homepage://): ")
    current_links = fetch_and_render(initial_url)
    
    while True:
        user_input = input("\n> ")
        
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Client wird geschlossen.")
            sys.exit()

        if user_input.isdigit():
            link_index = int(user_input) - 1
            if current_links and 0 <= link_index < len(current_links):
                url_to_fetch = current_links[link_index]
                print(f"Öffne Link [{link_index+1}]...")
                current_links = fetch_and_render(url_to_fetch)
            else:
                print("Ungültige Link-Nummer.")
            continue

        if user_input.startswith(("http://", "https://", "homepage://")):
            processed_url = user_input
        elif user_input.startswith("/"):
            processed_url = f"http://{DEFAULT_SERVER}{user_input}"
        elif " " in user_input:
            processed_url = f"http://{DEFAULT_SERVER}/search/{user_input.replace(' ', '%20')}"
        else:
            processed_url = f"http://{DEFAULT_SERVER}/search/{user_input}"

        print(f"Lade URL: {processed_url}...")
        current_links = fetch_and_render(processed_url)

if __name__ == "__main__":
    main_loop()
