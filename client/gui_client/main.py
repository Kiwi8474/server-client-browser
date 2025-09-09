import os
import json
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
from tkinter.font import nametofont
import requests
from PIL import Image, ImageTk
import PIL
import io
import threading
from queue import Queue
import interpreter

DEFAULT_SERVER = ""
HOMEPAGE_URL = "homepage://"
HOMEPAGE = {}
history = []
history_index = -1
WINDOW_SIZE = ""
CLIENT_KEY = ""
style = None
fonts = {}
styles = {}
_current_bg_color = None
widgets = {}
_gallery_state = {"images": [], "index": 0, "parent_frame": None, "load_button": None}
_image_queue = Queue()
_image_loader_thread = None

def _load_config():
    global DEFAULT_SERVER, HOMEPAGE_URL, HOMEPAGE, history, history_index, WINDOW_SIZE, CLIENT_KEY
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error reading config.json: {e}")
                config = {}
        
        DEFAULT_SERVER = config.get("default_server", "127.0.0.1:5000")
        HOMEPAGE = config.get("homepage_code", {})
        HOMEPAGE_URL = config.get("homepage_url", "homepage://")
        WINDOW_SIZE = config.get("window_size", "640x480")
        CLIENT_KEY = config.get("key", "")
    else:
        DEFAULT_SERVER = "127.0.0.1:5000"
        HOMEPAGE_URL = "homepage://"
        HOMEPAGE = {}
        WINDOW_SIZE = "640x480"
        CLIENT_KEY = ""
        _save_config()

def _save_config():
    global DEFAULT_SERVER, HOMEPAGE_URL, HOMEPAGE, history, history_index, WINDOW_SIZE, CLIENT_KEY
    config = {
        "default_server": DEFAULT_SERVER,
        "homepage_url": HOMEPAGE_URL,
        "homepage_code": HOMEPAGE,
        "window_size": WINDOW_SIZE,
        "key": CLIENT_KEY
    }
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

def _get_style_name(widget_type, font=None, foreground=None, background=None):
    font_key = tuple(font.actual().values()) if font else None
    style_key = (widget_type, font_key, foreground, background)

    if style_key in styles:
        return styles[style_key]
        
    style_name = f'Custom{widget_type}{len(styles)}.T{widget_type}'
    style_config = {}
    
    if font:
        style_config['font'] = font
    
    if foreground:
        style_config['foreground'] = foreground
    if background:
        style_config['background'] = background

    style.configure(style_name, **style_config)
    styles[style_key] = style_name
    return style_name

def _create_label(root, text, id=None, font=None, foreground=None, background=None):
    label = ttk.Label(root, text=text)
    if font: label.configure(font=font)
    if foreground: label.configure(foreground=foreground)
    if background: label.configure(background=background)
    label.pack(anchor="w")
    if id:
        widgets[id] = label
    return label

def _create_button(root, text, id=None, command=None, font=None, foreground=None, background=None):
    button_style = _get_style_name('Button', font, foreground, background)
    button = ttk.Button(root, text=text, command=command, style=button_style)
    button.pack(anchor="w")
    if id:
        widgets[id] = button
    return button

def _create_entry(root, font=None, foreground=None, background=None):
    entry = ttk.Entry(root)
    if font: entry.configure(font=font)
    if foreground: entry.configure(foreground=foreground)
    if background: entry.configure(background=background)
    entry.pack(anchor="w")
    return entry

def _create_image(root, src, width=None, height=None, id=None):
    try:
        if not src:
            raise ValueError("No image source provided")
        
        headers = {"X-API-Key": CLIENT_KEY}
        
        image = None
        if src.startswith("http"):
            response= requests.get(src, headers=headers)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
            image = Image.open(image_data)
        else:
            image = Image.open(src)
        
        original_width, original_height = image.size
        new_width, new_height = original_width, original_height

        if width == "auto" and isinstance(height, int):
            new_width = int(height * (original_width / original_height))
            new_height = height
        elif height == "auto" and isinstance(width, int):
            new_height = int(width / (original_width / original_height))
            new_width = width
        elif isinstance(width, int) and isinstance(height, int):
            new_width = width
            new_height = height

        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        photo_image = ImageTk.PhotoImage(image)
        label = ttk.Label(root, image=photo_image, **{'borderwidth': 0, 'relief': 'flat'})
        label.image = photo_image
        label.pack(anchor="w")
        if id:
            widgets[id] = label

    except Exception as e:
        _create_label(root, f"Error loading image from {src}: {e}")

def _create_image_button_on_main_thread(parent_frame, img, image_url, tags, root, url_entry):
    photo_image = ImageTk.PhotoImage(img)
    button = ttk.Button(parent_frame, image=photo_image, command=lambda: _perform_search(root, parent_frame, url_entry, image_url))
    button.image = photo_image
    button.pack(padx=5, pady=5)

def _process_image_queue(root, url_entry):
    global _gallery_state, _image_queue, _image_loader_thread
    parent_frame = _gallery_state["parent_frame"]
    headers = {"X-API-Key": CLIENT_KEY}
    
    while not _image_queue.empty():
        image_url = _image_queue.get()
        try:
            if image_url.endswith(('.mp4', '.webm', '.gif')):
                continue

            response = requests.get(image_url, headers=headers)
            response.raise_for_status()

            if not response.headers.get('Content-Type', '').startswith('image/'):
                parent_frame.after(0, _create_label, parent_frame, f"URL {image_url} did not return an image. Content-Type: {response.headers.get('Content-Type')}")
                continue

            image_data = io.BytesIO(response.content)
            image = Image.open(image_data)

            width = 400
            height = "auto"
            
            original_width, original_height = image.size
            new_width, new_height = original_width, original_height

            if width == "auto" and isinstance(height, int):
                new_width = int(height * (original_width / original_height))
                new_height = height
            elif height == "auto" and isinstance(width, int):
                new_height = int(width / (original_width / original_height))
                new_width = width
            elif isinstance(width, int) and isinstance(height, int):
                new_width = width
                new_height = height

            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            parent_frame.after(0, _create_image_button_on_main_thread, parent_frame, image, image_url, None, root, url_entry)
            
        except requests.exceptions.RequestException as e:
            parent_frame.after(0, _create_label, parent_frame, f"Network Error for image {image_url}: {e}")
        except PIL.UnidentifiedImageError:
            parent_frame.after(0, _create_label, parent_frame, f"Could not open image file from URL: {e}")
        
    _image_queue.task_done()

def _show_batch(root, url_entry, batch_size=10):
    global _gallery_state, _image_queue, _image_loader_thread
    
    parent_frame = _gallery_state["parent_frame"]
    for widget in parent_frame.winfo_children():
        widget.destroy()

    _image_queue = Queue()
    
    start_index = _gallery_state["index"]
    end_index = min(start_index + batch_size, len(_gallery_state["images"]))

    for i in range(start_index, end_index):
        image_info = _gallery_state["images"][i]
        image_url = image_info.get("url")
        if image_url:
            _image_queue.put(image_url)

    _image_loader_thread = threading.Thread(target=_process_image_queue, args=(root, url_entry), daemon=True)
    _image_loader_thread.start()

    _setup_navigation_buttons(root, url_entry, batch_size)

def _setup_navigation_buttons(root, url_entry, batch_size):
    global _gallery_state
    parent_frame = _gallery_state["parent_frame"]
    
    nav_frame = ttk.Frame(parent_frame)
    nav_frame.pack(pady=10)
    
    if _gallery_state["index"] > 0:
        back_button = ttk.Button(nav_frame, text="< Back", command=lambda: _go_back_batch(root, url_entry, batch_size))
        back_button.pack(side=tk.LEFT, padx=5)

    if _gallery_state["index"] + batch_size < len(_gallery_state["images"]):
        next_button = ttk.Button(nav_frame, text="Next >", command=lambda: _go_next_batch(root, url_entry, batch_size))
        next_button.pack(side=tk.LEFT, padx=5)

def _go_back_batch(root, url_entry, batch_size):
    global _gallery_state
    _gallery_state["index"] = max(0, _gallery_state["index"] - batch_size)
    _show_batch(root, url_entry, batch_size)

def _go_next_batch(root, url_entry, batch_size):
    global _gallery_state
    _gallery_state["index"] = _gallery_state["index"] + batch_size
    _show_batch(root, url_entry, batch_size)

def _display_image_on_main_thread(root_frame, image, image_tokens):
    try:
        idx = 0
        while idx < len(image_tokens) and image_tokens[idx] != ':':
            idx += 1
        
        params = {"width": None, "height": None, "id": None}
        param_parts = image_tokens[1:idx]
        
        if "width" in param_parts:
            try:
                width_index = param_parts.index("width")
                if width_index + 1 < len(param_parts):
                    val = param_parts[width_index + 1]
                    if val.isdigit(): params["width"] = int(val)
                    elif val == "auto": params["width"] = "auto"
            except (ValueError, IndexError): pass

        if "height" in param_parts:
            try:
                height_index = param_parts.index("height")
                if height_index + 1 < len(param_parts):
                    val = param_parts[height_index + 1]
                    if val.isdigit(): params["height"] = int(val)
                    elif val == "auto": params["height"] = "auto"
            except (ValueError, IndexError): pass

        if "id" in param_parts:
            try:
                id_index = param_parts.index("id")
                if id_index + 1 < len(param_parts):
                    params["id"] = param_parts[id_index + 1]
            except (ValueError, IndexError): pass

        original_width, original_height = image.size
        new_width, new_height = original_width, original_height

        if params["width"] == "auto" and isinstance(params["height"], int):
            new_width = int(params["height"] * (original_width / original_height))
            new_height = params["height"]
        elif params["height"] == "auto" and isinstance(params["width"], int):
            new_height = int(params["width"] / (original_width / original_height))
            new_width = params["width"]
        elif isinstance(params["width"], int) and isinstance(params["height"], int):
            new_width = params["width"]
            new_height = params["height"]

        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        photo_image = ImageTk.PhotoImage(image)
        label = ttk.Label(root_frame, image=photo_image, **{'borderwidth': 0, 'relief': 'flat'})
        label.image = photo_image
        label.pack(anchor="w")
        if params["id"]:
            widgets[params["id"]] = label

    except Exception as e:
        _create_label(root_frame, f"Error displaying image: {e}")

def _show_image_viewer(parent, image, url, width=None, height=None):
    viewer = tk.Toplevel(parent)
    viewer.title("Image Viewer")
    
    original_width, original_height = image.size
    new_width, new_height = original_width, original_height

    if width is not None and width != "auto" and height == "auto":
        new_width = int(width)
        new_height = int(new_width * (original_height / original_width))
    elif height is not None and height != "auto" and width == "auto":
        new_height = int(height)
        new_width = int(new_height * (original_width / original_height))
    elif width is not None and width != "auto" and height is not None and height != "auto":
        new_width = int(width)
        new_height = int(height)
    
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    photo_image = ImageTk.PhotoImage(image)

    image_label = ttk.Label(viewer, image=photo_image)
    image_label.image = photo_image
    image_label.pack(fill=tk.BOTH, expand=True)

    viewer.title(f"Image Viewer - {url}")

def _handle_search(text, root, content_frame, url_entry):
    _perform_search(root, content_frame, url_entry, text)

def _handle_wiki_search(text, root, content_frame, url_entry):
    _perform_search(root, content_frame, url_entry, f"http://{DEFAULT_SERVER}/wiki_search/{text}")

def _fetch_and_render_page(root, content_frame, url_entry, url_to_request, search_terms, loading_label):
    global CLIENT_KEY
    results = None
    
    try:
        headers = {"X-API-Key": CLIENT_KEY}
        
        if url_to_request.startswith("file://"):
            with open(url_to_request.replace("file://", ""), 'r') as f:
                results = json.load(f)

        elif url_to_request.startswith("http://") or url_to_request.startswith("https://"):
            response = requests.get(url_to_request, headers=headers)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if content_type.startswith('image/'):
                image_data = io.BytesIO(response.content)
                image = Image.open(image_data)
                
                size_params = {}
                if ';' in url_to_request:
                    url_parts = url_to_request.split(';')
                    for part in url_parts[1:]:
                        if '=' in part:
                            key, value = part.split('=')
                            size_params[key.strip()] = value.strip()
                
                root.after(0, lambda: [loading_label.destroy(), _show_image_viewer(root, image, url_to_request, width=500, height="auto")])
                return
            
            results = response.json()
        
        else:
            if ' ' in url_to_request or not ('.' in url_to_request or ':' in url_to_request):
                url_to_request = f"http://{DEFAULT_SERVER}/search/{url_to_request}"
            else:
                url_to_request = f"http://{url_to_request}"
            
            response = requests.get(url_to_request, headers=headers)
            response.raise_for_status()
            results = response.json()

        root.after(0, lambda: [loading_label.destroy(), _handle_search_results(results, url_to_request, root, content_frame, url_entry, search_terms)])
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, f"Error 404: '{url_to_request}' not found.")])
        elif e.response.status_code == 401:
            root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, "Error 401: Unauthorized")])
        else:
            root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, f"HTTP Error: {e}")])
    except requests.exceptions.RequestException as e:
        root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, f"Network Error: {e}")])

def _perform_search(root, content_frame, url_entry, search_terms, push_to_history=True):
    global history, history_index, CLIENT_KEY, _current_bg_color, _image_loader_thread

    if isinstance(search_terms, list):
        search_terms = ' '.join(search_terms)

    if push_to_history:
        if history_index < len(history) - 1:
            history = history[:history_index + 1]
        history.append(search_terms)
        history_index = len(history) - 1

    if _image_loader_thread and _image_loader_thread.is_alive():
        _image_queue.queue.clear()

    if search_terms.lower() == "homepage://":
        for widget in content_frame.winfo_children():
            widget.destroy()
        root.title("Homepage")
        url_entry.delete(0, tk.END)
        url_entry.insert(0, "homepage://")
        render_page(content_frame, HOMEPAGE, root, url_entry)
        return

    if search_terms.startswith(f"http://{DEFAULT_SERVER}/wiki_search/"):
        wiki_term = search_terms.replace(f"http://{DEFAULT_SERVER}/wiki_search/", "")
        url_to_request = f"http://{DEFAULT_SERVER}/wiki_search/{wiki_term}"

        loading_label = _create_label(content_frame, "Lade...", font=tkFont.Font(family="TkFixedFont", size=18, weight="bold"))
        
        def fetch_wiki_data():
            try:
                response = requests.get(url_to_request, headers={"X-API-Key": CLIENT_KEY})
                if response.status_code == 400:
                    root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, "Error: No search term provided. Please enter a word or phrase.")])
                    return
                if response.status_code == 404:
                    root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, f"Error: No wiki entries found for '{wiki_term}'.")])
                    return
                response.raise_for_status()
                wiki_data = response.json()
                
                root.after(0, lambda: [
                    loading_label.destroy(),
                    _handle_search_results(wiki_data, url_to_request, root, content_frame, url_entry, wiki_term)
                ])
            except requests.exceptions.RequestException as e:
                root.after(0, lambda: [loading_label.destroy(), _create_label(content_frame, f"Network Error: {e}")])
        
        threading.Thread(target=fetch_wiki_data).start()
        return

    url_to_request = search_terms
    if url_to_request.startswith("/"):
        url_to_request = f"http://{DEFAULT_SERVER}{search_terms}"
    
    loading_label = _create_label(content_frame, "Lade...", font=tkFont.Font(family="TkFixedFont", size=18, weight="bold"))

    url_entry.delete(0, tk.END)
    url_entry.insert(0, url_to_request.replace(" ", "%20"))

    threading.Thread(target=_fetch_and_render_page, args=(root, content_frame, url_entry, url_to_request, search_terms, loading_label)).start()

def _handle_search_results(results, url_to_request, root, content_frame, url_entry, search_terms):
    global _current_bg_color, style, fonts

    for widget in content_frame.winfo_children():
        widget.destroy()

    if isinstance(results, dict):
        root.title(results.get("url", "Browser"))
        source_code = results.get("source_code")
        if isinstance(source_code, dict):
            render_page(content_frame, source_code, root, url_entry)
        else:
            _create_label(content_frame, "Error: Invalid website format. \"source_code\" needs to be a dictionary.")
    elif isinstance(results, list):
        _current_bg_color = "#C0C0C0"
        style.configure("Page.TFrame", background=_current_bg_color)
        content_frame.configure(style="Page.TFrame")
        content_frame.master.configure(bg=_current_bg_color)
        if url_to_request.startswith(f"http://{DEFAULT_SERVER}/wiki_search/"):
            root.title(f"Wiki Search for {search_terms}")
            _create_label(content_frame, f"{len(results)} Wiki Results:", font=tkFont.Font(family="TkFixedFont", size=18, weight="bold"), background=_current_bg_color)
            _create_label(content_frame, "", font=tkFont.Font(family="TkFixedFont", size=12), background=_current_bg_color)
            
            for result in results:
                if "content" in result and "url" in result:
                    _create_button(content_frame, result["url"], command=lambda url=result["url"]: _perform_search(root, content_frame, url_entry, url))
                    _create_label(content_frame, result["content"], background=_current_bg_color)
        else:
            root.title(f"Results for {search_terms}")
            _create_label(content_frame, f"AllKnow-er", font=tkFont.Font(family="TkFixedFont", size=22, weight="bold"), background=_current_bg_color)
            _create_label(content_frame, "", font=tkFont.Font(family="TkFixedFont", size=12), background=_current_bg_color)

            font_params = {
                "family": "TkFixedFont",
                "size": 10,
                "weight": "normal",
                "slant": "roman"
            }

            font_key = tuple(font_params.values())
            if font_key not in fonts:
                fonts[font_key] = tkFont.Font(**font_params)

            entry_field = _create_entry(content_frame, font=fonts[font_key], foreground="#000000", background="#FFFFFF")
            _create_button(content_frame, text="Search", command=lambda: _perform_search(root, content_frame, url_entry, entry_field.get()), font=fonts[font_key])
            entry_field.insert(0, search_terms.replace(f"http://{DEFAULT_SERVER}/search/", ""))

            _create_label(content_frame, f"{len(results)} Results:", font=tkFont.Font(family="TkFixedFont", size=18, weight="bold"), background=_current_bg_color)
            
            for result in results:
                if "url" in result and "content" in result:
                    _create_button(content_frame, result["url"], command=lambda url=result["url"]: _perform_search(root, content_frame, url_entry, url), font=fonts[font_key])
                    _create_label(content_frame, result["content"], background=_current_bg_color)
            
    else:
        _create_label(content_frame, f"Error: '{search_terms}' not found.")

COMMAND_HANDLERS = {
    "search": lambda text, root, content_frame, url_entry: _handle_search(text, root, content_frame, url_entry),
    "wiki_search": lambda text, root, content_frame, url_entry, default_server: _perform_search(root, content_frame, url_entry, f"http://{default_server}/wiki_search/{text}"),
}

SCRIPT_HANDLERS = {
    "set_command": interpreter.set_command_command,
    "set_text": interpreter.set_text_command,
    "set_text_input": interpreter.set_text_input,
}

TAG_HANDLERS = {
    "<t>": interpreter.handle_text_tag,
    "<a>": interpreter.handle_link_tag,
    "<e>": interpreter.handle_entry_tag,
    "<img>": interpreter.handle_image_tag,
    "<mainbg>": interpreter.handle_mainbg_tag,
    "<script>": interpreter.handle_script_tag,
    "<button>": interpreter.handle_button_tag,
    "<gallery>": interpreter.handle_gallery_tag,
}

def render_page(root_frame, website_data, root, url_entry):
    global widgets, _current_bg_color, style, fonts
    widgets.clear()
    
    bg_color = website_data.get("background_color", "#C0C0C0")
    _current_bg_color = bg_color
    style.configure("Page.TFrame", background=_current_bg_color)
    root_frame.configure(style="Page.TFrame")
    
    canvas = root_frame.master
    canvas.configure(bg=_current_bg_color)
    
    markup_lines = website_data.get("markup", [])

    script_blocks = []
    idx = 0
    while idx < len(markup_lines):
        line = markup_lines[idx].strip()
        
        if line.startswith("<script>"):
            script_block = []
            inner_idx = idx + 1
            while inner_idx < len(markup_lines) and not markup_lines[inner_idx].strip().endswith(":"):
                script_block.append(markup_lines[inner_idx])
                inner_idx += 1
            if inner_idx < len(markup_lines):
                script_block.append(markup_lines[inner_idx].replace(":", ""))
            
            script_blocks.append("\n".join(script_block))
            idx = inner_idx + 1
        else:
            tokens = line.split()
            if tokens and tokens[0] in TAG_HANDLERS:
                handler = TAG_HANDLERS[tokens[0]]
                if tokens[0] != "<script>":
                    if tokens[0] == "<a>":
                        handler(root_frame, tokens, 0, root, url_entry, root_frame, fonts, tkFont, _create_button, _perform_search)
                    elif tokens[0] == "<e>":
                        handler(root_frame, tokens, 0, root, url_entry, root_frame, fonts, tkFont, _create_entry, widgets, _create_button)
                    elif tokens[0] == "<img>":
                        handler(root_frame, tokens, 0, _create_image)
                    elif tokens[0] == "<mainbg>":
                        handler(root_frame, tokens, 0, style, _current_bg_color)
                    elif tokens[0] == "<button>":
                        handler(root_frame, tokens, 0, fonts, tkFont, _create_button)
                    elif tokens[0] == "<gallery>":
                        handler(root_frame, tokens, 0, root, url_entry, _gallery_state, DEFAULT_SERVER, requests, CLIENT_KEY, ttk, tk, _create_label, _show_batch)
                    elif tokens[0] == "<t>":
                        handler(root_frame, tokens, 0, fonts, tkFont, _create_label)
            idx += 1

    for script_content in script_blocks:
        interpreter.handle_script_tag(root_frame, script_content, root, url_entry, SCRIPT_HANDLERS, widgets, _handle_search, DEFAULT_SERVER, _perform_search, _handle_wiki_search)

def close_browser(root):
    root.destroy()

def main():
    global style, _current_bg_color
    _load_config()
    root = tk.Tk()
    root.title("Homepage")
    root.geometry(WINDOW_SIZE)
    root.resizable(False, False)

    default_font = nametofont("TkDefaultFont")
    default_font.configure(family="TkFixedFont", size=10)
    root.option_add("*Font", default_font)

    style = ttk.Style()
    style.theme_use("alt")
    style.configure('.', background="#C0C0C0", foreground="#000000")
    style.configure('TButton', relief="raised", borderwidth=2)
    style.configure('Button', padding=5)

    url_frame = ttk.Frame(root)
    url_frame.pack(fill=tk.X, pady=2, padx=2)

    def _go_back(root, inner_content_frame, url_entry):
        global history, history_index
        if history_index > 0:
            history_index -= 1
            _perform_search(root, inner_content_frame, url_entry, history[history_index], push_to_history=False)

    def _go_forward(root, inner_content_frame, url_entry):
        global history, history_index
        if history_index < len(history) - 1:
            history_index += 1
            _perform_search(root, inner_content_frame, url_entry, history[history_index], push_to_history=False)

    back_button = ttk.Button(url_frame, text="<", width=3, command=lambda: _go_back(root, inner_content_frame, url_entry))
    back_button.pack(side=tk.LEFT, padx=5)

    forward_button = ttk.Button(url_frame, text=">", width=3, command=lambda: _go_forward(root, inner_content_frame, url_entry))
    forward_button.pack(side=tk.LEFT, padx=5)
    
    url_entry = ttk.Entry(url_frame)
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    search_button = ttk.Button(url_frame, text="Search", width=8, command=lambda: _perform_search(root, inner_content_frame, url_entry, url_entry.get()))
    search_button.pack(side=tk.LEFT, padx=5)
    
    def on_closing():
        _save_config()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)

    close_button = ttk.Button(url_frame, text="X", width=2, command=on_closing)
    close_button.pack(side=tk.RIGHT, padx=5)

    content_container = ttk.Frame(root)
    content_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    canvas = tk.Canvas(content_container, highlightthickness=0, bg="#C0C0C0")
    scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar_x = ttk.Scrollbar(content_container, orient="horizontal", command=canvas.xview)
    canvas.configure(xscrollcommand=scrollbar_x.set)

    scrollbar.pack(side="right", fill="y")
    scrollbar_x.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)
    
    inner_content_frame = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=inner_content_frame, anchor="nw")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    inner_content_frame.bind("<Configure>", on_frame_configure)

    _current_bg_color = "#C0C0C0"
    style.configure("Page.TFrame", background=_current_bg_color)
    inner_content_frame.configure(style="Page.TFrame")
    canvas.configure(bg=_current_bg_color)

    start_url = HOMEPAGE_URL
    
    url_entry.insert(0, start_url.replace(" ", "%20"))
    _perform_search(root, inner_content_frame, url_entry, start_url, push_to_history=True)
    
    root.mainloop()

if __name__ == "__main__":
    main()
