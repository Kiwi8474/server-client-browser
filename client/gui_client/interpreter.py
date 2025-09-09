def _parse_tag_content_and_params(tokens, idx, special_params=None):
    if special_params is None:
        special_params = {}
    
    content_parts = []
    inner_idx = idx + 1
    while inner_idx < len(tokens) and tokens[inner_idx] != ';':
        inner_token = tokens[inner_idx]
        if inner_token == "<nl>":
            content_parts.append('\n')
        else:
            content_parts.append(inner_token)
        inner_idx += 1
    content = ' '.join(content_parts).replace(" \n ", "\n").replace(" \n", "\n").replace("\n ", "\n")

    param_parts = []
    param_idx = inner_idx + 1
    while param_idx < len(tokens) and tokens[param_idx] != ':':
        param_parts.append(tokens[param_idx])
        param_idx += 1

    params = {"size": 10, "bold": False, "italic": False, "fg": None, "bg": None, "id": None}
    params.update(special_params)
    
    if "size" in param_parts:
        try:
            size_index = param_parts.index("size")
            if size_index + 1 < len(param_parts):
                params["size"] = int(param_parts[size_index + 1])
        except (ValueError, IndexError):
            pass

    if "bold" in param_parts:
        params["bold"] = True

    if "italic" in param_parts:
        params["italic"] = True

    if "fg" in param_parts:
        try:
            color_index = param_parts.index("fg")
            if color_index + 1 < len(param_parts):
                params["fg"] = param_parts[color_index + 1]
        except (ValueError, IndexError):
            pass
            
    if "bg" in param_parts:
        try:
            bg_index = param_parts.index("bg")
            if bg_index + 1 < len(param_parts):
                params["bg"] = param_parts[bg_index + 1]
        except (ValueError, IndexError):
            pass
            
    if "id" in param_parts:
        try:
            id_index = param_parts.index("id")
            if id_index + 1 < len(param_parts):
                params["id"] = param_parts[id_index + 1]
        except (ValueError, IndexError):
            pass

    for key in special_params.keys():
        if key in param_parts:
            try:
                key_index = param_parts.index(key)
                if key_index + 1 < len(param_parts):
                    params[key] = param_parts[key_index + 1]
            except (ValueError, IndexError):
                pass

    return content, params, param_idx + 1

def _get_font_from_params(params, fonts, tkFont):
    font_params = {
        "family": "TkFixedFont",
        "size": params["size"],
        "weight": "bold" if params["bold"] else "normal",
        "slant": "italic" if params["italic"] else "roman"
    }
    font_key = tuple(font_params.values())
    if font_key not in fonts:
        fonts[font_key] = tkFont.Font(**font_params)
    return fonts[font_key]

def handle_text_tag(root, tokens, idx, fonts, tkFont, _create_label):
    text, params, new_idx = _parse_tag_content_and_params(tokens, idx)
    font = _get_font_from_params(params, fonts, tkFont)
    _create_label(root, text, id=params["id"], font=font, foreground=params["fg"], background=params["bg"])
    return new_idx

def handle_link_tag(root_frame, tokens, idx, root, url_entry, content_frame, fonts, tkFont, _create_button, _perform_search):
    special_params = {"href": None}
    text, params, new_idx = _parse_tag_content_and_params(tokens, idx, special_params)
    font = _get_font_from_params(params, fonts, tkFont)
    _create_button(root_frame, text, id=params["id"], command=lambda: _perform_search(root, content_frame, url_entry, params["href"]), font=font, foreground=params["fg"], background=params["bg"])
    return new_idx

def handle_entry_tag(root_frame, tokens, idx, root, url_entry, content_frame, fonts, tkFont, _create_entry, widgets, _create_button):
    special_params = {"btn_id": None}
    text, params, new_idx = _parse_tag_content_and_params(tokens, idx, special_params)
    font = _get_font_from_params(params, fonts, tkFont)
    
    entry_field = _create_entry(root_frame, font=font, foreground=params["fg"], background=params["bg"])
    if params["id"]:
        widgets[params["id"]] = entry_field

    _create_button(root_frame, text=text, id=params["btn_id"], font=font, foreground=params["fg"], background=params["bg"])
    return new_idx

def handle_image_tag(root_frame, tokens, idx, _create_image):
    special_params = {"width": None, "height": None}
    src, params, new_idx = _parse_tag_content_and_params(tokens, idx, special_params)
    
    width_val = params["width"]
    height_val = params["height"]
    
    if isinstance(width_val, str) and width_val.isdigit(): width_val = int(width_val)
    if isinstance(height_val, str) and height_val.isdigit(): height_val = int(height_val)

    _create_image(root_frame, src, width=width_val, height=height_val, id=params["id"])
    return new_idx

def handle_mainbg_tag(root_frame, tokens, idx, style, _current_bg_color):
    color = None
    color_idx = idx + 1
    if color_idx < len(tokens):
        color = tokens[color_idx]
    param_idx = color_idx + 1
    while param_idx < len(tokens) and tokens[param_idx] != ':':
        param_idx += 1
    if color:
        _current_bg_color = color
        style.configure("Page.TFrame", background=_current_bg_color)
        root_frame.configure(style="Page.TFrame")
        canvas = root_frame.master
        canvas.configure(bg=_current_bg_color)
    return param_idx + 1

def handle_button_tag(root_frame, tokens, idx, fonts, tkFont, _create_button):
    text, params, new_idx = _parse_tag_content_and_params(tokens, idx)
    font = _get_font_from_params(params, fonts, tkFont)
    _create_button(root_frame, text, id=params["id"], font=font, foreground=params["fg"], background=params["bg"])
    return new_idx

def set_text_command(args, root, content_frame, url_entry, widgets):
    if len(args) >= 2 and args[0] in widgets:
        text_to_set = ' '.join(args[1:])
        
        if text_to_set.startswith('"') and text_to_set.endswith('"'):
            text_to_set = text_to_set[1:-1]
            
        widgets[args[0]].configure(text=text_to_set)

def set_command_command(args, root, content_frame, url_entry, widgets, _handle_search, _handle_wiki_search):
    if len(args) >= 2 and args[0] in widgets:
        button_id = args[0]
        function_name = args[1]
    
    if function_name == "search":
        widgets[button_id].configure(command=lambda: _handle_search(text=widgets["2"].get(), root=root, content_frame=content_frame, url_entry=url_entry))
    elif function_name == "wiki_search":
        widgets[button_id].configure(command=lambda: _handle_wiki_search(text=widgets["2"].get(), root=root, content_frame=content_frame, url_entry=url_entry))

def set_text_input(args, root, content_frame, url_entry, widgets):
    if len(args) >= 2 and args[0] in widgets:
        text_to_set = ' '.join(args[1:])
        
        if text_to_set.startswith('"') and text_to_set.endswith('"'):
            text_to_set = text_to_set[1:-1]
            
        widgets[args[0]].delete(0, 'end')
        widgets[args[0]].insert(0, text_to_set)

def handle_script_tag(root_frame, script_content, root, url_entry, SCRIPT_HANDLERS, widgets, _handle_search, DEFAULT_SERVER, _perform_search, _handle_wiki_search):
    script_commands = script_content.strip().split(';')
    
    for command_line in script_commands:
        command_line = command_line.strip()
        if not command_line:
            continue
        
        parts = command_line.split()
        if not parts:
            continue
        
        command = parts[0]
        args = parts[1:]
        
        if command in SCRIPT_HANDLERS:
            if command == "set_command":
                SCRIPT_HANDLERS[command](args, root, root_frame, url_entry, widgets, _handle_search, _handle_wiki_search)
            elif command == "set_text":
                SCRIPT_HANDLERS[command](args, root, root_frame, url_entry, widgets)
            elif command == "set_text_input":
                SCRIPT_HANDLERS[command](args, root, root_frame, url_entry, widgets)
            else:
                SCRIPT_HANDLERS[command](args, root, root_frame, url_entry)

def handle_gallery_tag(root_frame, tokens, idx, root, url_entry, _gallery_state, DEFAULT_SERVER, requests, CLIENT_KEY, ttk, tk, _create_label, show_batch_callback):
    loading_label = None
    
    try:
        gallery_content_frame = ttk.Frame(root_frame, style="Page.TFrame")
        gallery_content_frame.pack(fill=tk.BOTH, expand=True)

        param_parts = []
        inner_idx = idx + 1
        while inner_idx < len(tokens) and tokens[inner_idx] != ':':
            param_parts.append(tokens[inner_idx])
            inner_idx += 1

        if "tag" in param_parts:
            tag_index = param_parts.index("tag")
            if tag_index + 1 < len(param_parts):
                tag = param_parts[tag_index + 1]
                url_to_fetch = f"http://{DEFAULT_SERVER}/r34/{tag}"
                
                try:
                    response = requests.get(url_to_fetch, headers={"X-API-Key": CLIENT_KEY})
                    response.raise_for_status()
                    images_data = response.json()
                    
                    _gallery_state["images"] = images_data
                    _gallery_state["index"] = 0
                    _gallery_state["parent_frame"] = gallery_content_frame

                    show_batch_callback(root, url_entry)

                except requests.exceptions.RequestException as e:
                    _create_label(root_frame, f"Error fetching images for tag '{tag}': {e}")
    finally:
        pass
            
    return inner_idx + 1
