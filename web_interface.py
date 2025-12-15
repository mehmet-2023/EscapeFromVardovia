from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
import time
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from main import call_groq, parse_model_response, pretty_print_state, minimal_sanity_check, ENABLE_IMAGE_GENERATION

load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='static')

log_dir = Path('logs')
log_dir.mkdir(exist_ok=True, mode=0o755)
log_file = log_dir / 'access.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

def get_client_ip():
    """Get the client's IP address, handling proxy headers"""
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr or 'unknown'
    return ip

def log_action(ip, action, status='success'):
    """Log user action with IP and timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"{timestamp} - IP: {ip} - Action: {action} - Status: {status}"
    logging.info(log_entry)

static_dir = Path('static')
static_dir.mkdir(exist_ok=True, mode=0o755)

static_abs_path = os.path.abspath('static')
print(f"Static files directory: {static_abs_path}")
print(f"Logging to: {os.path.abspath(log_file)}")

@app.route('/static/<path:filename>')
def static_files(filename):
    try:
        print(f"Serving static file: {filename}")
        file_path = os.path.join(static_abs_path, filename)
        print(f"Full path: {file_path}")
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return "File not found", 404
        if not os.access(file_path, os.R_OK):
            print(f"Permission denied for file: {file_path}")
            return "Permission denied", 403
        return send_file(file_path)
    except Exception as e:
        print(f"Error serving static file {filename}: {str(e)}")
        return str(e), 500

current_state = {
    "player_name": "Arsen Dvorak",
    "location": "Basement",
    "inventory": ["wristwatch", "crumpled note"],
    "health": 90,
    "danger": 1,
    "time": "night",
    "flags": {"initialized": False}
}

previous_state_json = json.dumps(current_state, separators=(',', ':'))

story_log = []
MAX_STORY_LOG = 20

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/settings/image_generation', methods=['POST'])
def toggle_image_generation():
    """Update image generation setting"""
    global ENABLE_IMAGE_GENERATION
    data = request.get_json()
    if data is not None and 'enabled' in data:
        ENABLE_IMAGE_GENERATION = bool(data['enabled'])
        print(f"Image generation {'enabled' if ENABLE_IMAGE_GENERATION else 'disabled'}")
    return jsonify({"enabled": ENABLE_IMAGE_GENERATION})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    return jsonify({"image_generation": ENABLE_IMAGE_GENERATION})

@app.route('/api/action', methods=['POST'])
def handle_action():
    global current_state, previous_state_json, story_log, ENABLE_IMAGE_GENERATION
    
    client_ip = get_client_ip()
    
    try:
        data = request.get_json()
        if not data:
            log_action(client_ip, "No data provided", "error")
            return jsonify({"error": "No data provided"}), 400
            
        player_action = data.get('action', '').strip()
        if not player_action:
            log_action(client_ip, "Empty action", "error")
            return jsonify({"error": "No action provided"}), 400
            
        log_action(client_ip, player_action)
            
        image_generation_enabled = data.get('image_generation_enabled', ENABLE_IMAGE_GENERATION)
        
        print(f"Processing action: {player_action}")
        try:
            response = call_groq(
                previous_state_json=previous_state_json,
                story_log=story_log,
                player_action=player_action,
                api_key=os.getenv('GROQ_API_KEY')
            )
            if not response:
                raise ValueError("Empty response from API")
            print(f"API Response: {response[:200]}...")
        except Exception as e:
            print(f"Error in call_groq: {str(e)}", file=sys.stderr)
            log_action(client_ip, f"Error in call_groq: {str(e)}", "error")
            return jsonify({"error": f"Error processing your request: {str(e)}"}), 500
            
        image_url = None
        if image_generation_enabled and ENABLE_IMAGE_GENERATION and '[IMAGE_PROMPT:' in response and ']' in response:
            before_prompt, after_prompt = response.split('[IMAGE_PROMPT:', 1)
            prompt_part, after = after_prompt.split(']', 1)
            clean_response = before_prompt.strip() + after.strip()
            from main import generate_image
            try:
                success, image_path = generate_image(prompt_part.strip())
                if success and image_path:
                    image_url = image_path
                else:
                    print("Image generation failed")
            except Exception as e:
                print(f"Error generating image: {str(e)}")
        else:
            clean_response = response
        state_obj, narration = parse_model_response(clean_response)
        story_log.append(narration)
        if len(story_log) > MAX_STORY_LOG:
            story_log[:] = story_log[-MAX_STORY_LOG:]
        current_state = state_obj
        previous_state_json = json.dumps(state_obj, separators=(',', ':'))
        return jsonify({
            "narration": narration,
            "state": state_obj,
            "image_url": image_url
        })
    except Exception as e:
        log_action(client_ip, f"Server error: {str(e)}", "error")
        return jsonify({"error": str(e)}), 500

@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(current_state)

@app.route('/static/output.png')
def serve_image():
    try:
        return send_from_directory('static', 'output.png', mimetype='image/png')
    except FileNotFoundError:
        try:
            return send_file('output.png', mimetype='image/png')
        except FileNotFoundError:
            print("Image not found in both static and root directories", file=sys.stderr)
            return "Image not found", 404

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
