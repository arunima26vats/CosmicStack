import json

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
        # Simple Type Guessing (Highly effective for MVP)
        if isinstance(value, int):
            db_type = "INTEGER"
        elif isinstance(value, float):
            db_type = "REAL"
        elif isinstance(value, bool):
            db_type = "BOOLEAN"
        elif isinstance(value, str):
            # Check for potential date/time format (Advanced for time crunch)
            if any(x in value.lower() for x in ["date", "time", "created_at"]):
                 db_type = "TIMESTAMP"
            else:
                 db_type = "VARCHAR(255)"
        else:
            db_type = "TEXT" # Fallback for odd types
        
        schema[key] = db_type
        
    # Construct a mock SQL CREATE TABLE statement
    columns = [f"{k} {v}" for k, v in schema.items()]
    table_name = next(iter(item.keys())) + "_table" # Simple table naming
    
    return f"CREATE TABLE {table_name} (ID INTEGER PRIMARY KEY, " + ", ".join(columns) + ");"


def process_json_data(data, metadata_comment):
    """Intelligently determines storage type and generates schema/collection."""
    
    # 1. Force Check (Highest priority for hackathon demo)
    if "relational" in metadata_comment.lower():
        storage_choice = "SQL (Forced by Comment)"
    elif "document" in metadata_comment.lower() or "flexible" in metadata_comment.lower():
        storage_choice = "NoSQL (Forced by Comment)"
    
    # 2. Heuristic Check (The core intelligence)
    elif has_nested_complexity(data):
        storage_choice = "NoSQL (Heuristic: Nested Complexity)"
    else:
        storage_choice = "SQL (Heuristic: Flat/Homogeneous)"

    # --- Result Generation (Simulate DB Creation) ---
    
    if storage_choice.startswith("SQL"):
        # Simulate creating a SQL table and schema
        schema_output = generate_sql_schema_and_types(data)
        collection_name = schema_output.split()[2]
        intelligence_action = f"Generated Table Schema for **{collection_name}**"
    else:
        # Simulate creating a NoSQL collection
        # Use the first key of the first object to name the collection
        collection_name = next(iter(data[0].keys())) + "_collection" if isinstance(data, list) and data else "unknown_collection"
        schema_output = "No fixed schema required (Document-based storage). Data stored as JSON objects."
        intelligence_action = f"Created NoSQL Collection **{collection_name}**"
        
    return {
        "status": "success",
        "type": "Structured JSON",
        "storage_choice": storage_choice,
        "db_entity_name": collection_name,
        "generated_schema": schema_output,
        "intelligence_action": intelligence_action
    }