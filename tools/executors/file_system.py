import os
import glob
import json

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
