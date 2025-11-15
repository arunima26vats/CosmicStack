from flask import Flask, request, render_template, jsonify
import os, json
from werkzeug.utils import secure_filename
import time
from datetime import datetime, timedelta # <--- ADDED: Necessary for real-time stats

# Import the custom logic functions (to be created in Phase 2 & 3)
from logic_media import process_media_file 
from logic_structured import process_json_data 

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'storage'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Helper function for file size conversion
def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"

# Helper function to get "time ago" string <--- ADDED
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

# -----------------
# The SINGLE ENTRY POINT
# -----------------
@app.route('/api/store', methods=['POST'])
def store_data():
    metadata_comment = request.form.get('metadata_comment', '')

    # 1. CHECK FOR FILE (Media Data)
    if 'file' in request.files and request.files['file'].filename != '':
        f = request.files['file']
        result = process_media_file(f, app.config['UPLOAD_FOLDER'], metadata_comment)
        return jsonify(result)
    
    # 2. CHECK FOR JSON (Structured Data)
    elif 'json_data' in request.form and request.form['json_data'].strip():
        try:
            json_string = request.form['json_data']
            data = json.loads(json_string)
            result = process_json_data(data, metadata_comment)
            return jsonify(result)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON format."}), 400
    
    else:
        return jsonify({"status": "error", "message": "No file or JSON data provided."}), 400

# -----------------
# Endpoint for REAL-TIME Dashboard Statistics <--- ADDED
# -----------------
@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    total_size = 0
    total_files = 0
    last_upload_time = 0 
    MAX_STORAGE = 100 * 1024 * 1024 * 1024 # 100 GB in bytes (for mockup)

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
        # If folder scan fails, return safe defaults
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


# -----------------
# Endpoint to list recent files for the dashboard
# -----------------
@app.route('/api/recent_files', methods=['GET'])
def get_recent_files():
    file_list = []
    # Map extensions to friendly labels for the frontend
    file_type_map = {
        'pdf': 'Document', 'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
        'mp4': 'Video', 'mov': 'Video', 'mp3': 'Audio', 'wav': 'Audio',
        'zip': 'Archive', 'json': 'JSON', 'txt': 'Document'
    }

    try:
        # 1. Iterate through the subdirectories (categories) in 'storage'
        for category_dir in os.listdir(app.config['UPLOAD_FOLDER']):
            category_path = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
            
            if os.path.isdir(category_path):
                
                # 2. Iterate through files inside each category
                for filename in os.listdir(category_path):
                    filepath = os.path.join(category_path, filename)
                    
                    if os.path.isfile(filepath):
                        
                        size_bytes = os.path.getsize(filepath)
                        mod_time = os.path.getmtime(filepath)
                        
                        # Determine file type
                        ext = filename.split('.')[-1].lower() if '.' in filename else ''
                        type_label = file_type_map.get(ext, 'Other')
                        
                        file_list.append({
                            "name": filename,
                            "size": format_size(size_bytes),
                            "type": type_label,
                            "category": category_dir,
                            "timestamp": mod_time # Use timestamp for sorting
                        })

    except Exception as e:
        # Handle case where storage folder might not be accessible
        return jsonify({"error": f"Failed to list files: {str(e)}", "recent_files": []}), 500

    # 3. Sort files by modification time (most recent first)
    file_list.sort(key=lambda x: x['timestamp'], reverse=True)

    # 4. Return up to the 6 most recent files
    return jsonify({"recent_files": file_list[:6]})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Set debug=True for easy development during the hackathon
    app.run(debug=True)