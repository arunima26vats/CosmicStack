# logic_structured.py
import json
import os
import gzip
import hashlib
from datetime import datetime

def has_nested_complexity(data):
    """
    Checks if the data contains nested objects or arrays, favoring NoSQL.
    Returns True if complex, False if flat.
    """
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, (dict, list)):
                return True
    elif isinstance(data, list) and data:
        # Check the first item in a batch for complexity
        if isinstance(data[0], dict):
            return has_nested_complexity(data[0])
        elif isinstance(data[0], list):
            return True # Array of arrays is complex
            
    return False

def generate_sql_schema_and_types(data):
    """Analyzes flat data structure to suggest SQL column names and types (MVP)."""
    # Use the first element in the batch, or the single item
    item = data[0] if isinstance(data, list) else data
    schema = {}
    
    for key, value in item.items():
        # Simple Type Guessing
        if isinstance(value, int):
            db_type = "INTEGER"
        elif isinstance(value, float):
            db_type = "REAL"
        elif isinstance(value, bool):
            db_type = "BOOLEAN"
        elif isinstance(value, str):
            # Check for potential date/time format
            if any(x in key.lower() for x in ["date", "time", "created_at", "timestamp"]):
                db_type = "TIMESTAMP"
            else:
                db_type = "VARCHAR(255)"
        else:
            db_type = "TEXT" # Fallback for odd types
        
        schema[key] = db_type
        
    # Construct a mock SQL CREATE TABLE statement
    columns = [f"{k} {v}" for k, v in schema.items()]
    # Simple table naming: Use hash if data keys are generic, or a custom name
    table_name = "analyzed_table_" + hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:6]
    
    return f"CREATE TABLE {table_name} (ID INTEGER PRIMARY KEY, " + ", ".join(columns) + ");"


def process_json_data(data, metadata_comment, base_dir, auto_compress=False):
    """
    Intelligently determines storage type (SQL/NoSQL), generates schema/collection 
    info, and saves the file.
    """
    
    # 1. Determine Storage Choice (Decision Logic)
    storage_choice = "SQL (Heuristic: Flat/Homogeneous)" # Default assumption
    
    if "relational" in metadata_comment.lower():
        storage_choice = "SQL (Forced by Comment)"
    elif "document" in metadata_comment.lower() or "flexible" in metadata_comment.lower():
        storage_choice = "NoSQL (Forced by Comment)"
    elif has_nested_complexity(data):
        storage_choice = "NoSQL (Heuristic: Nested Complexity)"

    # 2. Prepare Storage Metadata
    
    # Generate a consistent name for the file/entity
    file_hash = hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:10]
    
    db_entity_name = f"data_batch_{datetime.now().strftime('%Y%m%d%H%M')}_{file_hash}"
    
    target_dir_name = "Structured_JSON"
    final_dir = os.path.join(base_dir, target_dir_name)
    os.makedirs(final_dir, exist_ok=True)
    
    filename = f"{db_entity_name}.json"
    intelligence_action = ""
    schema_output = ""

    if storage_choice.startswith("SQL"):
        schema_output = generate_sql_schema_and_types(data)
        intelligence_action = f"Generated Table Schema for **{db_entity_name}**."
    else:
        schema_output = "No fixed schema required (Document-based storage)."
        intelligence_action = f"Designated for NoSQL Collection **{db_entity_name}**."

    # 3. Save the File (Compressed or not)
    if auto_compress:
        filename += ".gz"
        final_path = os.path.join(final_dir, filename)
        try:
            # Write compressed text
            with gzip.open(final_path, "wt", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            intelligence_action += " Data **auto-compressed**."
        except Exception as e:
            return {"status": "error", "message": f"Failed to write compressed file: {e}"}
            
    else:
        # Write plain text
        final_path = os.path.join(final_dir, filename)
        try:
            with open(final_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            intelligence_action += " Data stored as plain JSON."
        except Exception as e:
            return {"status": "error", "message": f"Failed to write file: {e}"}
            
    # Return the full result
    return {
        "status": "success",
        "type": "Structured JSON",
        "storage_choice": storage_choice,
        "db_entity_name": db_entity_name,
        "filename": filename,
        "storage_location": final_path,
        "generated_schema": schema_output,
        "intelligence_action": intelligence_action
    }