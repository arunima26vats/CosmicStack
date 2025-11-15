from flask import Flask, request, render_template, jsonify, session, redirect, url_for, send_from_directory
import os
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import urllib.parse # NEW import for safe path handling

# NEW Google Imports
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests # Alias for clarity

# Import the custom logic functions (assuming these exist and work)
from logic_media import process_media_file 
from logic_structured import process_json_data 

app = Flask(__name__)
# IMPORTANT: Set a secret key for session management!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_secret_key_for_dev_do_not_use_in_prod')

app.config['UPLOAD_FOLDER'] = 'storage'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 🚨 IMPORTANT: REPLACE THIS with the Client ID from your Google Cloud Console
# This must match the ID used in your index.html file.
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID" 

# -----------------
# IN-MEMORY USER STORAGE (DEMO ONLY - Use a DB for production)
# Structure: {email: {username: str, password_hash: str | None, is_google: bool}}
# -----------------
USERS = {}

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
# NEW: Login Status Check (Crucial for Frontend)
# ------------------------------------
@app.route('/api/status', methods=['GET'])
def get_login_status():
    return jsonify({
        "logged_in": session.get('logged_in', False),
        "username": session.get('username', 'Guest')
    })


# ------------------------------------
# Google Authentication Route (Unchanged)
# ------------------------------------
@app.route('/api/google_signin', methods=['POST'])
def google_signin():
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({"status": "error", "message": "No token provided."}), 400

    try:
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID)

        google_email = idinfo['email']
        google_name = idinfo.get('name', google_email.split('@')[0])
        
    except ValueError as e:
        print(f"Token verification failed: {e}")
        return jsonify({"status": "error", "message": "Invalid Google token. Token expired or tampered."}), 401
    
    if google_email not in USERS:
        USERS[google_email] = {
            'username': google_name,
            'password_hash': None, 
            'is_google': True
        }
        message = "Google account linked and signed up successfully!"
    else:
        message = "Signed in successfully via Google."
        if USERS[google_email].get('password_hash') is not None and not USERS[google_email].get('is_google'):
             USERS[google_email]['is_google'] = True

    session['logged_in'] = True
    session['username'] = USERS[google_email]['username']
    session['email'] = google_email 

    return jsonify({
        "status": "success", 
        "message": message, 
        "username": USERS[google_email]['username']
    })

# -----------------
# Existing Authentication Routes (Unchanged)
# -----------------
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({"status": "error", "message": "Missing required fields."}), 400

    if email in USERS:
        if USERS[email].get('is_google'):
            return jsonify({"status": "error", "message": "This email is already registered via Google. Please use Google Sign-In."}), 409
        return jsonify({"status": "error", "message": "User with this email already exists."}), 409

    hashed_password = generate_password_hash(password)
    
    USERS[email] = {
        'username': username,
        'password_hash': hashed_password,
        'is_google': False
    }
    
    session['logged_in'] = True
    session['username'] = username
    session['email'] = email
    
    return jsonify({"status": "success", "message": "Account created and logged in!", "username": username})

@app.route('/api/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"status": "error", "message": "Missing email or password."}), 400

    user_data = USERS.get(email)
    
    if user_data and user_data.get('is_google'):
        return jsonify({"status": "error", "message": "This email is registered via Google. Please use Google Sign-In."}), 401

    if user_data and check_password_hash(user_data['password_hash'], password):
        session['logged_in'] = True
        session['username'] = user_data['username']
        session['email'] = email
        return jsonify({"status": "success", "message": "Logged in successfully!", "username": user_data['username']})
    else:
        return jsonify({"status": "error", "message": "Invalid email or password."}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('email', None) 
    return jsonify({"status": "success", "message": "Logged out successfully."})

# ------------------------------------
# NEW: File Viewing Endpoint
# ------------------------------------
@app.route('/api/view_file/<path:path_info>', methods=['GET'])
def view_file(path_info):
    # path_info format is expected to be CATEGORY/FILENAME (e.g., 'Document_JSON/report.json')
    try:
        # Decode URL-encoded characters (like spaces)
        path_info = urllib.parse.unquote(path_info)
        
        # Split into directory and filename
        category_dir, filename = path_info.split('/', 1)
        
        # Ensure path traversal is not possible (security check)
        if '..' in category_dir or '..' in filename:
            return jsonify({"error": "Invalid path."}), 400

        full_directory = os.path.join(app.config['UPLOAD_FOLDER'], category_dir)
        
        # Flask's send_from_directory handles streaming the file and setting headers correctly
        return send_from_directory(
            full_directory, 
            filename, 
            as_attachment=False # Display in browser instead of downloading
        )
        
    except ValueError:
        return jsonify({"error": "Invalid file path format."}), 400
    except FileNotFoundError:
        return jsonify({"error": "File not found."}), 404
    except Exception as e:
        print(f"Error viewing file: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500


# -----------------
# Data & Utility Endpoints (Unchanged)
# -----------------
@app.route('/api/store', methods=['POST'])
def store_data():
    metadata_comment = request.form.get('metadata_comment', '')
    auto_compress = 'auto_compress' in request.form

    if 'file' in request.files and request.files['file'].filename != '':
        f = request.files['file']
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
                            "server_path_info": path_info # NEW: Path info for the frontend
                        })

    except Exception as e:
        print(f"Error fetching recent files: {e}")
        return jsonify({"error": f"Failed to list files: {str(e)}", "recent_files": []}), 500

    file_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify({"recent_files": file_list[:6]})

# -----------------
# Main page route (PROTECTED)
# -----------------
@app.route('/')
def index():
    return render_template('index.html', 
                           logged_in=session.get('logged_in', False),
                           username=session.get('username', 'Guest'))

if __name__ == '__main__':
    app.run(debug=True)