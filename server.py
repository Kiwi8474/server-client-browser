from flask import Flask, jsonify, send_from_directory, request, Response
import os
import json
import re
import requests
import time

app = Flask(__name__)

websites_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "websites"))
images_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "images"))

WEBSITES_DATA = {}
WIKI_DATA = {}
R34_CACHE = {}
R34_CACHE_LIFETIME = 300

def load_server_config():
    config_path = os.path.join(os.path.dirname(__file__), "server_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

config = load_server_config()
SERVER_KEY = config.get("key", "")

def load_all_data():
    global WEBSITES_DATA
    global WIKI_DATA
    
    print("Loading all website data into memory...")

    for website_file in os.listdir(websites_folder):
        filepath = os.path.join(websites_folder, website_file)
        if os.path.isfile(filepath) and not filepath.endswith('maxipedia'):
            try:
                with open(filepath, "r") as f:
                    website_content = json.load(f)
                
                url = website_content.get("url")
                if url:
                    cleaned_content = re.sub(r'[^\w\s]', '', website_content.get("content", "").lower())
                    
                    WEBSITES_DATA[url] = {
                        "tags": [tag.lower() for tag in website_content.get("tags", [])],
                        "content_words": cleaned_content.split(),
                        "content": website_content.get("content"),
                        "source_code": website_content.get("source_code")
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing file {website_file}: {e}")

    wiki_folder = os.path.join(websites_folder, 'maxipedia')
    if os.path.isdir(wiki_folder):
        for wiki_file in os.listdir(wiki_folder):
            filepath = os.path.join(wiki_folder, wiki_file)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, 'r') as f:
                        wiki_content = json.load(f)
                    
                    url = wiki_content.get("url")
                    if url:
                        cleaned_content = re.sub(r'[^\w\s]', '', wiki_content.get("content", "").lower())
                        
                        WIKI_DATA[url] = {
                            "tags": [tag.lower() for tag in wiki_content.get("tags", [])],
                            "content_words": cleaned_content.split(),
                            "content": wiki_content.get("content"),
                            "source_code": wiki_content.get("source_code")
                        }
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error processing wiki file {wiki_file}: {e}")

load_all_data()

print("-"*80)
print(f"Server key loaded: {SERVER_KEY}")
print("-"*80)

@app.before_request
def check_auth():
    print("-"*80)
    print(f"Connection from IP: {request.remote_addr}, requested URL: {request.url}")

    if request.path.startswith("/images") or request.path.startswith("/website") or request.path.startswith("/search") or request.path.startswith("/r34"):
        client_key = request.headers.get("X-API-Key")
        print(f"Client key received: '{client_key}'")
        if client_key != SERVER_KEY or not SERVER_KEY:
            return jsonify({"error": "Unauthorized"}), 401
    print("-"*80)

def _search_for_tags(search_terms, tags, url, scores):
    normalized_search_terms = [term.lower() for term in search_terms]
    for term in normalized_search_terms:
        if term in tags:
            scores[url] += 1

def _search_for_content(search_terms, content_words, url, scores):
    normalized_search_terms = [term.lower() for term in search_terms]
    for term in normalized_search_terms:
        if term in content_words:
            scores[url] += 1

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(images_folder, filename.strip())

@app.route('/website/<path:url>')
def get_website_page(url):
    for site_url, site_data in WEBSITES_DATA.items():
        if site_url.endswith(url):
            data = {
                "url": site_url,
                "tags": site_data["tags"],
                "content": site_data["content"],
                "source_code": site_data["source_code"]
            }
            return jsonify(data)

    for site_url, site_data in WIKI_DATA.items():
        if site_url.endswith(url):
            data = {
                "url": site_url,
                "tags": site_data["tags"],
                "content": site_data["content"],
                "source_code": site_data["source_code"]
            }
            return jsonify(data)

    return jsonify({"error": "Website not found"}), 404

@app.route('/search/', defaults={'search_terms': ''})
@app.route('/search/<search_terms>')
def search_api(search_terms):
    terms = search_terms.split()
    if not search_terms:
        results = [{"url": url, "content": data["content"]} for url, data in WEBSITES_DATA.items()]
    else:
        scores = {url: 0 for url in WEBSITES_DATA}
        for url, data in WEBSITES_DATA.items():
            _search_for_tags(terms, data["tags"], url, scores)
            _search_for_content(terms, data["content_words"], url, scores)

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = [{"url": url, "content": WEBSITES_DATA[url]["content"]} for url, score in sorted_scores if score > 0]
    
    return jsonify(results)

@app.route('/wiki_search/', defaults={'wiki_term': ''})
@app.route('/wiki_search/<wiki_term>')
def wiki_search_api(wiki_term):
    terms = wiki_term.split()
    if not wiki_term:
        results = [{"url": url, "content": data["content"]} for url, data in WIKI_DATA.items()]
    else:
        scores = {url: 0 for url in WIKI_DATA}
        for url, data in WIKI_DATA.items():
            _search_for_tags(terms, data["tags"], url, scores)
            _search_for_content(terms, data["content_words"], url, scores)
        
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = [{"url": url, "content": WIKI_DATA[url]["content"]} for url, score in sorted_scores if score > 0]
        
    if results:
        return jsonify(results)
    else:
        return jsonify(), 404

@app.route('/list_images/<path:directory>')
def list_images(directory):
    path = os.path.join(images_folder, directory.strip())
    if not os.path.isdir(path):
        return jsonify({"error": "Directory not found"}), 404
    
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    return jsonify(files)

@app.route('/r34/<tag>')
def fetch_r34_tags(tag):
    global R34_CACHE

    if tag in R34_CACHE and time.time() - R34_CACHE[tag]["timestamp"] < R34_CACHE_LIFETIME:
        print(f"Returning cached data for tag: {tag}")
        return jsonify(R34_CACHE[tag]["data"])

    try:
        api_url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&limit=100&tags={tag}&json=1"
        
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()
        
        if not data:
            return jsonify({"error": "No results found"}), 404
        
        processed_images = []
        for post in data:
            image_url = post.get("file_url")
            image_tags = post.get("tags")
            
            if image_url and image_tags:
                processed_images.append({
                    "url": image_url,
                    "tags": image_tags.split()
                })

        R34_CACHE[tag] = {
            "timestamp": time.time(),
            "data": processed_images
        }

        return jsonify(processed_images)

    except requests.exceptions.RequestException as e:
        print(f"Network Error fetching from rule34.xxx: {e}")
        return jsonify({"error": "Failed to fetch data from external API"}), 500
    except json.JSONDecodeError:
        print("JSON Decode Error: Malformed response from rule34.xxx")
        return jsonify({"error": "Invalid response format"}), 500

@app.route('/raw/<path:url>')
def get_raw_json(url):
    for dataset in (WEBSITES_DATA, WIKI_DATA):
        for site_url, site_data in dataset.items():
            if site_url.endswith(url):
                return jsonify(site_data)
    return jsonify({"error": "Website not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
