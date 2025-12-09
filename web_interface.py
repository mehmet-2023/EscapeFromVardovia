from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
import time
import sys
from pathlib import Path
from dotenv import load_dotenv
from main import call_groq, parse_model_response, pretty_print_state, minimal_sanity_check

load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='static')

import os
static_dir = Path('static')
static_dir.mkdir(exist_ok=True, mode=0o755)  

static_abs_path = os.path.abspath('static')
print(f"Static files directory: {static_abs_path}")

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

previous_state_json = json.dumps(current_state, separators=(',',':'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/action', methods=['POST'])
def handle_action():
    global current_state, previous_state_json
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        player_action = data.get('action', '').strip()
        if not player_action:
            return jsonify({"error": "No action provided"}), 400
        
        print(f"Processing action: {player_action}")  
        
        try:
            response = call_groq(
                previous_state_json=previous_state_json,
                player_action=player_action,
                api_key=os.getenv('GROQ_API_KEY')
            )
            if not response:
                raise ValueError("Empty response from API")
                
            print(f"API Response: {response[:200]}...")  
            
        except Exception as e:
            print(f"Error in call_groq: {str(e)}", file=sys.stderr)  
            return jsonify({"error": f"Error processing your request: {str(e)}"}), 500
        
        image_url = None
        if '[IMAGE_PROMPT:' in response and ']' in response:
            before_prompt, after_prompt = response.split('[IMAGE_PROMPT:', 1)
            prompt_part, after = after_prompt.split(']', 1)
            clean_response = before_prompt.strip() + after.strip()
            
            from main import generate_image
            try:
                success, image_path = generate_image(prompt_part.strip())
                if success and image_path:
                    image_url = image_path
                else:
                    print(f"Image generation failed:")
            except Exception as e:
                print(f"Error generating image: {str(e)}")
        else:
            clean_response = response
        
        state_obj, narration = parse_model_response(clean_response)
        
        current_state = state_obj
        previous_state_json = json.dumps(state_obj, separators=(',',':'))
        
        return jsonify({
            "narration": narration,
            "state": state_obj,
            "image_url": image_url
        })
        
    except Exception as e:
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
