from flask import Flask, request, render_template, jsonify, session, redirect, url_for, send_from_directory, make_response
import os
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash # Kept in case internal auth is needed later
from datetime import datetime, timedelta
import urllib.parse 
import gzip 
import shutil
from PIL import Image 
import numpy as np
import pytesseract # For OCR
import sys # ADDED for Tesseract check

# --- Tesseract Path Fix (CRITICAL ADDITION) ---
if sys.platform == "win32":
    # Set the absolute path to the Tesseract executable to bypass PATH issues
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except Exception:
        # Ignore if this fails here; it will crash later but allows the app to start
        pass
# ---------------------------------------------

# --- Embedded Custom Logic Functions ---

# --- Helper Logic (determine_directory depends on this global) ---
global EXISTING_CATEGORIES
EXISTING_CATEGORIES = {
    "photos_of_people": ["face", "portrait", "selfie"],
    "documents": ["text", "invoice", "receipt"],
    "nature_and_landscapes": ["green", "blue", "sky", "water"]
}

def analyze_image_for_tags(filepath):
    """Generates simple tags based on image properties (stub/MVP)"""
    ext = filepath.split('.')[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp']: return ["document", "text"] 
    try:
        img = Image.open(filepath)
        tags = []
        width, height = img.size
        if height / width > 1.2: tags.append("portrait")
        elif width / height > 1.2: tags.append("landscape")
        small_img = img.resize((50, 50)).convert('RGB')
        avg_color = np.array(small_img).mean(axis=(0, 1))
        if avg_color[0] > 180 and avg_color[1] < 100: tags.append("red_heavy")
        if avg_color[1] > 180: tags.append("green")
        if avg_color[2] > 180: tags.append("blue") 
        return tags
    except Exception as e:
        return ["file_error", "unsupported"] 

def determine_directory(tags):
    """Intelligently matches tags to an existing or new category."""
    global EXISTING_CATEGORIES
    best_match_dir = "unclassified"
    max_matches = 0
    for directory, keywords in EXISTING_CATEGORIES.items():
        matches = sum(1 for tag in tags if tag in keywords)
        if matches > max_matches:
            max_matches = matches
            best_match_dir = directory
    if max_matches > 0 and max_matches >= 1:
        return best_match_dir
    elif tags and tags[0] != "file_error":
        new_dir_name = f"new_category_{tags[0]}"
        if new_dir_name not in EXISTING_CATEGORIES:
             EXISTING_CATEGORIES[new_dir_name] = [tags[0]]
        return new_dir_name
    else:
        return "unclassified"
# --- End of Media Helpers ---


# --- process_media_file (CORRECTED Implementation for Compression) ---
def process_media_file(file_storage_object, base_dir, metadata_comment, auto_compress=False):
    filename = secure_filename(file_storage_object.filename)
    # 1. Save file temporarily for analysis
    temp_path = os.path.join(base_dir, "temp_" + filename)
    
    try:
        # Save the uploaded file object to a temporary path
        file_storage_object.save(temp_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to save file temporarily: {e}", "error_details": str(e)}

    # 2. Analyze and Categorize
    tags = analyze_image_for_tags(temp_path)
    
    if metadata_comment: tags.extend(metadata_comment.lower().split())

    target_dir_name = determine_directory(tags)
    final_dir = os.path.join(base_dir, target_dir_name)
    os.makedirs(final_dir, exist_ok=True)
    
    # Base path for the final (uncompressed) file name
    final_filename = filename
    final_path_base = os.path.join(final_dir, filename)
    intelligence_action = f"Classified and placed in **{target_dir_name}**"

    # 3. Compress file if requested
    if auto_compress:
        compressed_path = final_path_base + ".gz"
        
        try:
            # Compress the file from the temporary location (temp_path)
            with open(temp_path, 'rb') as f_in:
                # Use standard gzip module which is generally fast enough
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Update paths and info to reflect the compressed file
            final_path = compressed_path
            final_filename = filename + ".gz"
            intelligence_action += " and **auto-compressed**."
            
            # Remove the temporary file
            os.remove(temp_path)
            
        except Exception as e:
            # If compression fails, store the original file instead
            final_path = final_path_base
            os.rename(temp_path, final_path)
            intelligence_action += f" (Compression failed: {e}). Stored uncompressed."
            
    else:
        # If no compression, just move the temporary file to the final location
        final_path = final_path_base
        try:
            os.rename(temp_path, final_path)
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path) 
            return {"status": "error", "message": f"Failed to move file to final directory: {e}", "error_details": str(e)}
            
    # 4. Return Success
    return {
        "status": "success",
        "type": "Media/File",
        "filename": final_filename, # Return the name including .gz if compressed
        "classification_tags": tags,
        "storage_location": final_path,
        "intelligence_action": intelligence_action
    }
# --- End process_media_file ---


# --- process_json_data (REPLACED STUB with Compression) ---
def process_json_data(data, metadata_comment, base_dir, auto_compress=False): 
    # Logic to classify the JSON data
    target_dir_name = "Structured_JSON" 
    final_dir = os.path.join(base_dir, target_dir_name)
    os.makedirs(final_dir, exist_ok=True)
    
    # Simple hash for unique filename creation
    file_hash = hash(json.dumps(data, sort_keys=True)) 
    
    filename_base = f"data_batch_{datetime.now().strftime('%Y%m%d%H%M')}_{abs(file_hash)}.json"
    
    intelligence_action = "Designated for NoSQL collection."
    
    if auto_compress:
        filename = filename_base + ".gz"
        final_path = os.path.join(final_dir, filename)
        try:
            # Write compressed text (using 'wt' mode for text compression)
            with gzip.open(final_path, "wt", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            intelligence_action += " Data **auto-compressed**."
        except Exception as e:
            return {"status": "error", "message": f"Failed to write compressed JSON file: {e}"}
    else:
        filename = filename_base
        final_path = os.path.join(final_dir, filename)
        try:
            with open(final_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            return {"status": "error", "message": f"Failed to write JSON file: {e}"}

    return {
        "status": "success", 
        "type": "Structured JSON",
        "filename": filename,
        "storage_location": final_path,
        "intelligence_action": intelligence_action
    }
# --- End process_json_data ---

# --- process_ocr_scan (New Logic) ---
def process_ocr_scan(f, base_dir, metadata_comment):
    """
    Handles file saving, OCR processing, file movement, and result generation.
    f is the werkzeug.FileStorage object.
    """
    filename = secure_filename(f.filename)
    temp_path = os.path.join(base_dir, "temp_" + filename)
    f.save(temp_path)
    
    # Check if the saved file is compressed
    is_compressed = filename.lower().endswith('.gz')
    read_path = temp_path
    temp_decompressed_path = None

    if is_compressed:
        try:
            original_file_name_base = filename[:-3] 
            temp_decompressed_path = os.path.join(base_dir, "decompressed_" + original_file_name_base)
            
            with gzip.open(temp_path, 'rb') as f_in:
                with open(temp_decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            read_path = temp_decompressed_path 
        
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            if temp_decompressed_path and os.path.exists(temp_decompressed_path): os.remove(temp_decompressed_path)
            return {"status": "error", "message": f"Decompression failed for OCR: {str(e)}"}


    extracted_text = ""
    try:
        # 2. Use Pillow/Tesseract on the uncompressed file
        img = Image.open(read_path)
        extracted_text = pytesseract.image_to_string(img)
        
        # 3. Tagging
        text_lower = extracted_text.lower()
        tags = ["ocr_document"]
        
        if any(keyword in text_lower for keyword in ["invoice", "bill", "receipt"]): tags.append("financial_document")
        if any(keyword in text_lower for keyword in ["address", "phone", "email"]): tags.append("potential_pii")
        if any(keyword in text_lower for keyword in ["class", "import", "def", "function"]): tags.append("code_snippet") 

        # 4. Save searchable text as a separate .txt file
        searchable_text_summary = extracted_text.strip().replace('\n', ' ')[:500]
        
        text_base_name = original_file_name_base.rsplit('.', 1)[0] if is_compressed else filename.rsplit('.', 1)[0]
        text_filename = text_base_name + "_ocr.txt"
        
        categorization_tags = tags + ["text", "document"]
        target_dir_name = determine_directory(categorization_tags) 
        final_dir = os.path.join(base_dir, target_dir_name)
        os.makedirs(final_dir, exist_ok=True)
        
        text_filepath = os.path.join(final_dir, text_filename)
        with open(text_filepath, "w", encoding="utf-8") as f_out:
            f_out.write(extracted_text)

        # 5. Clean up temporary files
        if os.path.exists(temp_path): os.remove(temp_path)
        if temp_decompressed_path and os.path.exists(temp_decompressed_path): os.remove(temp_decompressed_path)

        return {
            "status": "success",
            "type": "OCR_Result",
            "source_file": filename,
            "generated_text_file": text_filename,
            "extracted_text_summary": searchable_text_summary,
            "classification_tags": tags,
            "storage_location": text_filepath, # Return text file location
            "intelligence_action": f"OCR successful. Text file saved in **{target_dir_name}**."
        }
        
    except pytesseract.TesseractNotFoundError:
        if os.path.exists(temp_path): os.remove(temp_path)
        if temp_decompressed_path and os.path.exists(temp_decompressed_path): os.remove(temp_decompressed_path)
        return {"status": "error", "message": "Tesseract OCR engine not found. Ensure it is installed and configured (e.g., via Homebrew/apt)."}
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        if temp_decompressed_path and os.path.exists(temp_decompressed_path): os.remove(temp_decompressed_path)
        return {"status": "error", "message": f"OCR processing failed: {str(e)}"}
# --- End process_ocr_scan ---


app = Flask(__name__)
# IMPORTANT: Set a secret key for session management!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_secret_key_for_dev_do_not_use_in_prod')

app.config['UPLOAD_FOLDER'] = 'storage'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# -----------------
# Helper Functions (Unchanged)
# -----------------
def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"

def time_ago(timestamp):
    if timestamp == 0:
        return "N/A"
        
    now = datetime.now()
    dt_object = datetime.fromtimestamp(timestamp)
    diff = now - dt_object

    if diff < timedelta(minutes=1):
        return "Just now"
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() // 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = diff.days
        return f"{days} day{'s' if days > 1 else ''} ago"

# ------------------------------------
# Authentication Endpoints (Simplified for Demo)
# ------------------------------------
@app.route('/api/status', methods=['GET'])
def get_login_status():
    # SIMPLIFIED: Assume logged in for demo purposes
    return jsonify({
        "logged_in": True,
        "username": 'DemoUser' 
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    # SIMPLIFIED: Just report success, no actual session invalidation needed for this demo mode
    return jsonify({"status": "success", "message": "Logged out successfully."})

# ------------------------------------
# File Viewing Endpoint 
# ------------------------------------
@app.route('/api/view_file/<path:path_info>', methods=['GET'])
def view_file(path_info):
    try:
        # 1. Decode path (CRUCIAL for paths with special characters/slashes)
        path_info = urllib.parse.unquote(path_info)
        category_dir, filename = path_info.split('/', 1)
        
        # Sanity check to prevent directory traversal
        if '..' in category_dir or '..' in filename:
            return jsonify({"error": "Invalid path."}), 403
        
        full_directory = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
        filepath = os.path.join(full_directory, filename) # Calculate full path

        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({"error": f"File not found on server at path: {category_dir}/{filename}"}), 404
        
        # 2. Handle Compressed Files (.gz) - Uses make_response for binary reliability
        if filename.endswith('.gz'):
            try:
                # Read compressed data and decompress the bytes
                with gzip.open(filepath, 'rb') as f_in:
                    decompressed_content = f_in.read() # This is binary data (bytes)
                
                # Determine the content type based on the *original* extension
                original_filename = filename.replace('.gz', '')
                original_ext = original_filename.split('.')[-1].lower() if '.' in original_filename else 'bin'
                
                # Determine Content-Type (Expanded MIME map)
                mimetype_map = {
                    'pdf': 'application/pdf',
                    'json': 'application/json',
                    'txt': 'text/plain',
                    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'mp4': 'video/mp4', 'mov': 'video/quicktime',
                    'mp3': 'audio/mpeg', 'wav': 'audio/wav',
                }
                mimetype = mimetype_map.get(original_ext, 'application/octet-stream')

                # FIX: Create a response object manually to ensure binary content is served correctly
                response = make_response(decompressed_content)
                response.headers['Content-Type'] = mimetype
                return response
                
            except Exception as e:
                return jsonify({"error": f"Failed to decompress and serve file: {e}"}), 500
        
        # 3. Handle Uncompressed Files (relying on send_from_directory for correct MIME inference)
        return send_from_directory(
            full_directory, 
            filename, 
            as_attachment=False
        )

    except ValueError:
        return jsonify({"error": "Invalid file path format."}), 400
    except Exception as e:
        print(f"Error viewing file: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500


# ------------------------------------
# Search Endpoint (ADDED)
# ------------------------------------
@app.route('/api/search', methods=['GET'])
def search_files():
    query = request.args.get('q', '').lower().strip()
    if not query:
        # Returning an empty result instead of an error is often better for an empty search
        return jsonify({"results": []}) 

    search_results = []
    
    file_type_map = {
        'pdf': 'Document', 'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
        'mp4': 'Video', 'mov': 'Video', 'mp3': 'Audio', 'wav': 'Audio',
        'zip': 'Archive', 'json': 'JSON', 'txt': 'Document', 'gz': 'Archive'
    }

    try:
        # 1. Iterate through all files in storage
        for category_dir in os.listdir(app.config['UPLOAD_FOLDER']):
            category_path = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
            
            if not os.path.isdir(category_path):
                continue

            for filename in os.listdir(category_path):
                filepath = os.path.join(category_path, filename)
                
                if not os.path.isfile(filepath):
                    continue

                # 2. Search Logic: Match by filename or full text content
                is_match = False
                
                # A. Match by filename/category
                if query in filename.lower() or query in category_dir.lower():
                    is_match = True
                
                # B. Match by file content (specifically OCR-generated .txt files)
                if filename.lower().endswith('_ocr.txt'):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            if query in content:
                                is_match = True
                    except Exception:
                        # Silently skip files that cannot be read
                        pass

                # 3. If a match is found, add it to the results
                if is_match:
                    size_bytes = os.path.getsize(filepath)
                    mod_time = os.path.getmtime(filepath)
                    
                    ext = filename.split('.')[-1].lower() if '.' in filename else ''
                    type_label = file_type_map.get(ext, 'Other')
                    
                    path_info = os.path.join(category_dir, filename).replace('\\', '/')

                    file_list.append({
                        "name": filename, 
                        "size": format_size(size_bytes),
                        "type": type_label,
                        "category": category_dir,
                        "timestamp": mod_time,
                        "server_path_info": path_info 
                    })

    except Exception as e:
        print(f"Error during file search: {e}")
        return jsonify({"error": f"Internal server error during search: {str(e)}"}), 500

    # Sort by recentness 
    search_results.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return a unique set of results
    unique_results = []
    seen_paths = set()
    for res in search_results:
        if res['server_path_info'] not in seen_paths:
            unique_results.append(res)
            seen_paths.add(res['server_path_info'])

    return jsonify({"results": unique_results})


# -----------------
# Data & Utility Endpoints 
# -----------------
@app.route('/api/store', methods=['POST'])
def store_data():
    metadata_comment = request.form.get('metadata_comment', '')
    auto_compress = 'auto_compress' in request.form

    if 'file' in request.files and request.files['file'].filename != '':
        f = request.files['file']
        
        # 🚨 OCR LOGIC PATHWAY
        if 'ocr_scan_request' in metadata_comment.lower():
             # The uploaded file object 'f' is passed to the OCR processing function
             result = process_ocr_scan(f, app.config['UPLOAD_FOLDER'], metadata_comment)
             return jsonify(result)
        
        # Fallback to regular media processing
        result = process_media_file(f, app.config['UPLOAD_FOLDER'], metadata_comment, auto_compress)
        return jsonify(result)
    
    elif 'json_data' in request.form and request.form['json_data'].strip():
        try:
            json_string = request.form['json_data']
            data = json.loads(json_string)
            result = process_json_data(data, metadata_comment, app.config['UPLOAD_FOLDER'], auto_compress)
            return jsonify(result)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON format."}), 400
    
    else:
        return jsonify({"status": "error", "message": "No file or JSON data provided."}), 400

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    total_size = 0
    total_files = 0
    last_upload_time = 0 
    MAX_STORAGE = 100 * 1024 * 1024 * 1024 

    try:
        for category_dir in os.listdir(app.config['UPLOAD_FOLDER']):
            category_path = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
            if os.path.isdir(category_path):
                for filename in os.listdir(category_path):
                    filepath = os.path.join(category_path, filename)
                    if os.path.isfile(filepath):
                        total_files += 1
                        size = os.path.getsize(filepath)
                        total_size += size
                        last_upload_time = max(last_upload_time, os.path.getmtime(filepath))
    except Exception:
        return jsonify({
            "storage_used": "Error",
            "storage_total": format_size(MAX_STORAGE),
            "files_processed": "Error",
            "last_upload": "Error"
        }), 500

    last_upload_string = time_ago(last_upload_time) if last_upload_time > 0 else "N/A"

    return jsonify({
        "storage_used": format_size(total_size),
        "storage_total": format_size(MAX_STORAGE),
        "files_processed": total_files,
        "last_upload": last_upload_string
    })


@app.route('/api/recent_files', methods=['GET'])
def get_recent_files():
    file_list = []
    file_type_map = {
        'pdf': 'Document', 'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
        'mp4': 'Video', 'mov': 'Video', 'mp3': 'Audio', 'wav': 'Audio',
        'zip': 'Archive', 'json': 'JSON', 'txt': 'Document', 'gz': 'Archive'
    }

    try:
        for category_dir in os.listdir(app.config['UPLOAD_FOLDER']):
            category_path = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
            
            if os.path.isdir(category_path):
                for filename in os.listdir(category_path):
                    filepath = os.path.join(category_path, filename)
                    
                    if os.path.isfile(filepath):
                        size_bytes = os.path.getsize(filepath)
                        mod_time = os.path.getmtime(filepath)
                        
                        original_filename = filename 
                        
                        if filename.endswith('.gz'):
                            ext = 'gz'
                        else:
                            ext = filename.split('.')[-1].lower() if '.' in filename else ''
                        
                        type_label = file_type_map.get(ext, 'Other')
                        
                        # Create the path string needed by the new view_file endpoint
                        path_info = os.path.join(category_dir, filename).replace('\\', '/')

                        file_list.append({
                            "name": original_filename, 
                            "size": format_size(size_bytes),
                            "type": type_label,
                            "category": category_dir,
                            "timestamp": mod_time,
                            "server_path_info": path_info 
                        })

    except Exception as e:
        print(f"Error fetching recent files: {e}")
        return jsonify({"error": f"Failed to list files: {str(e)}", "recent_files": []}), 500

    file_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify({"recent_files": file_list[:6]})

# -----------------
# Main page route (UNPROTECTED)
# -----------------
@app.route('/')
def index():
    # SIMPLIFIED: Assume user is always logged in as 'DemoUser'
    return render_template('index.html', 
                           logged_in=True,
                           username='DemoUser')

if __name__ == '__main__':
    # No Google Client ID warning needed as Google auth is removed
    app.run(debug=True)