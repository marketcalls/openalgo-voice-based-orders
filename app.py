from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from word2number import w2n
from openalgo.orders import api
import os
from dotenv import load_dotenv
import requests
from ratelimit import limits, sleep_and_retry
import logging
import re
import json
import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Verify required environment variables
required_env_vars = [
    'GROQ_API_KEY',
    'OPENALGO_API_KEY',
    'OPENALGO_HOST',
    'VOICE_ACTIVATE_COMMAND',
    'SECRET_KEY'  # Ensure SECRET_KEY is also defined
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key')
CORS(app)

# OpenAlgo client setup
openalgo_client = api(api_key=os.getenv('OPENALGO_API_KEY'), host=os.getenv('OPENALGO_HOST'))

# Get the Voice Activation Commands
voice_activate_commands_env = os.getenv('VOICE_ACTIVATE_COMMAND', '["MILO"]')
try:
    voice_activate_commands = json.loads(voice_activate_commands_env)
    if not isinstance(voice_activate_commands, list):
        raise ValueError("VOICE_ACTIVATE_COMMAND must be a JSON array.")
except json.JSONDecodeError as e:
    logger.error(f"Error parsing VOICE_ACTIVATE_COMMAND: {str(e)}")
    raise ValueError("VOICE_ACTIVATE_COMMAND must be a valid JSON array.")

# Command synonyms to handle speech recognition variations
command_synonyms = {
    "bhai": "BUY",  "bi": "BUY",
    "by": "BUY",    "bye": "BUY",
    "buy": "BUY",   "cell": "SELL",
    "cel": "SELL",  "self": "SELL",
    "sale": "SELL", "sel": "SELL",
    "sell": "SELL"
}

@app.route('/')
def index():
    return render_template('index.html', 
                           title='Voice-Activated Trading System',
                           header='Voice-Activated Trading System')

@sleep_and_retry
@limits(calls=15, period=60)  # 15 calls per minute
def call_groq_api(file_data):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"
    }
    
    try:
        files = {
            "file": ("audio.webm", file_data, "audio/webm")
        }
        data = {
            "model": "whisper-large-v3",
            "language": "en",
            "response_format": "verbose_json"
        }
        
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        logger.debug("Successfully received response from Groq API")
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Groq API HTTP error: {str(e)} - Response: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error when calling Groq API: {str(e)}")
        raise

def remove_punctuation(text):
    return re.sub(r'[^\w\s]', '', text)

def parse_command(transcript):
    words = transcript.upper().split()
    try:
        for activate_command in voice_activate_commands:
            activate_command_upper = activate_command.upper()
            if activate_command_upper in words:
                action_index = words.index(activate_command_upper) + 1
                if action_index >= len(words):
                    logger.error("Action word missing after activation command.")
                    return None, None, None
                
                action_word = words[action_index].lower()
                action = command_synonyms.get(action_word, action_word.upper())
                
                quantity_index = action_index + 1
                if quantity_index >= len(words):
                    logger.error("Quantity word missing after action word.")
                    return None, None, None
                
                quantity_word = words[quantity_index].lower()
                try:
                    quantity = int(quantity_word)
                except ValueError:
                    quantity = w2n.word_to_num(quantity_word)
                
                tradingsymbol = words[-1]
                
                logger.info(f'Parsed command - Action: {action}, Quantity: {quantity}, Symbol: {tradingsymbol}')
                return action, quantity, tradingsymbol
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing command: {str(e)}")
    return None, None, None

def place_order(action, quantity, tradingsymbol):
    try:
        response = openalgo_client.placeorder(
            strategy="VoiceOrder",
            symbol=tradingsymbol,
            action=action,
            exchange="NSE",
            price_type="MARKET",
            product="MIS",
            quantity=quantity
        )
        logger.info(f"Order placed: {response}")
        return response
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        return {"error": str(e)}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        logger.error("No file part in the request")
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file")
        return jsonify({"error": "No selected file"}), 400
    
    if file.mimetype not in ['audio/webm', 'audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/ogg', 'audio/flac']:
        logger.error(f"Unsupported audio format: {file.mimetype}")
        return jsonify({"error": "Unsupported audio format"}), 400
    
    try:
        file_data = file.read()
        logger.info(f"Received audio file: name={file.filename}, size={len(file_data)} bytes, content_type={file.content_type}")
        result = call_groq_api(file_data)
        logger.info(f"Transcription result: {result}")
        
        # Process the transcription and place order if valid
        transcription = remove_punctuation(result.get('text', '').strip())
        action, quantity, tradingsymbol = parse_command(transcription)
        
        if all([action, quantity, tradingsymbol]):
            order_response = place_order(action, quantity, tradingsymbol)
            result['order_response'] = order_response
        else:
            result['order_response'] = {"error": "Invalid command"}
        
        result['text'] = transcription  # Update the text with punctuation removed
        return jsonify(result)
    except ValueError as e:
        logger.error(f"Audio Processing Error: {str(e)}")
        return jsonify({"error": f"Audio Processing Error: {str(e)}"}), 400
    except requests.exceptions.HTTPError as e:
        logger.error(f"Groq API error: {str(e)}")
        return jsonify({"error": f"Groq API error: {str(e)}", "details": e.response.text}), e.response.status_code
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)