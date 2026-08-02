import os

def exec_list_directory(path: str = ".") -> str:
    try:
        resolved_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(resolved_path):
            return f"Error: Path '{resolved_path}' does not exist."
        if not os.path.isdir(resolved_path):
            return f"Error: Path '{resolved_path}' is not a directory."

        items = os.listdir(resolved_path)
        output = []
        for item in items[:100]: # Limit to 100 items to avoid token explosion
            item_path = os.path.join(resolved_path, item)
            if os.path.isdir(item_path):
                output.append(f"[DIR]  {item}")
            else:
                size = os.path.getsize(item_path)
                output.append(f"[FILE] {item} ({size} bytes)")

        if len(items) > 100:
            output.append(f"... and {len(items) - 100} more items.")

        return "\n".join(output)
    except Exception as e:
        return f"Error listing directory: {e}"

def exec_read_file(file_path: str, max_lines: int = 200) -> str:
    try:
        resolved_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(resolved_path):
            return f"Error: File '{resolved_path}' does not exist."
        if not os.path.isfile(resolved_path):
            return f"Error: Path '{resolved_path}' is not a file."

        with open(resolved_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) > max_lines:
            truncated = lines[:max_lines]
            return "".join(truncated) + f"\n\n... (File truncated. {len(lines) - max_lines} more lines)"
        return "".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"

def exec_write_file(file_path: str, content: str) -> str:
    try:
        resolved_path = os.path.abspath(os.path.expanduser(file_path))
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

        with open(resolved_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to '{resolved_path}'."
    except Exception as e:
        return f"Error writing file: {e}"

def exec_search_files(query: str, path: str = None, **kwargs) -> str:
    import os
    
    query_lower = query.lower().strip()
    
    # If no path is provided, search in common user directories
    if path:
        resolved_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(resolved_path):
            return f"Error: Path '{resolved_path}' does not exist."
        search_dirs = [resolved_path]
    else:
        user_profile = os.path.expanduser("~")
        search_dirs = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "Documents"),
            os.path.join(user_profile, "Downloads")
        ]
        
    results = []
    
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
            
        for root, dirs, files in os.walk(s_dir):
            # Skip common heavy/hidden directories to speed up search
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.git')]
            
            for file in files:
                if query_lower in file.lower():
                    results.append(os.path.join(root, file))
                    
                # Stop if we find too many to prevent token explosion and slow search
                if len(results) > 50:
                    break
            if len(results) > 50:
                break
        if len(results) > 50:
            break
                
    if not results:
        return f"No files found matching '{query}' in {', '.join(search_dirs)}"
        
    output = [f"Found {len(results)} matches:"]
    for res in results[:20]: # Only show top 20 to the LLM
        output.append(res)
        
    if len(results) > 20:
        output.append(f"... and {len(results) - 20} more.")
        
    return "\n".join(output)

