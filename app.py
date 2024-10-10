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
    'SECRET_KEY',
    'TRADING_SYMBOLS_MAPPING'  # Ensure TRADING_SYMBOLS_MAPPING is defined
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
    "BHai": "BUY",  "BI": "BUY",
    "BY": "BUY",    "BYE": "BUY",
    "BUY": "BUY",   "CELL": "SELL",
    "CEL": "SELL",  "SELF": "SELL",
    "SALE": "SELL", "SEL": "SELL",
    "SELL": "SELL"
}

# Load Trading Symbols Mapping from .env
trading_symbols_mapping_env = os.getenv('TRADING_SYMBOLS_MAPPING', '{}')
try:
    trading_symbols_mapping = json.loads(trading_symbols_mapping_env)
    if not isinstance(trading_symbols_mapping, dict):
        raise ValueError("TRADING_SYMBOLS_MAPPING must be a JSON object.")
except json.JSONDecodeError as e:
    logger.error(f"Error parsing TRADING_SYMBOLS_MAPPING: {str(e)}")
    raise ValueError("TRADING_SYMBOLS_MAPPING must be a valid JSON object.")

# Reverse the Trading Symbols Mapping for easy lookup
# Map each variation to its standardized symbol
symbol_variation_map = {}
for standard_symbol, variations in trading_symbols_mapping.items():
    for variation in variations:
        symbol_variation_map[variation.upper()] = standard_symbol.upper()

def normalize_action_words(text, synonyms):
    """
    Replace synonyms in the text with their standardized forms.

    Args:
        text (str): The input text to normalize.
        synonyms (dict): A dictionary mapping synonyms to standardized words.

    Returns:
        str: The normalized text with synonyms replaced.
    """
    words = text.split()
    normalized_words = []
    for word in words:
        # Check if the word is a key in synonyms; if so, replace it
        normalized_word = synonyms.get(word.upper(), word.upper())
        normalized_words.append(normalized_word)
    return ' '.join(normalized_words)

def map_trading_symbol(spoken_symbol):
    """
    Map the spoken/mistyped trading symbol to the standardized symbol.

    Args:
        spoken_symbol (str): The trading symbol as spoken by the user.

    Returns:
        str: The standardized trading symbol if found, else None.
    """
    return symbol_variation_map.get(spoken_symbol.upper())

@app.route('/')
def index():
    return render_template('index.html', 
                           title='Voice-Activated Trading System',
                           header='Voice-Activated Trading System')

@sleep_and_retry
@limits(calls=15, period=60)  # 15 calls per minute
def call_groq_api(file_data, model):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"
    }
    
    try:
        files = {
            "file": ("audio.webm", file_data, "audio/webm")
        }
        data = {
            "model": model,
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
    """
    Parse the transcribed text to extract trading commands.

    Args:
        transcript (str): The transcribed text from the audio.

    Returns:
        tuple: (action, quantity, tradingsymbol) or (None, None, None) if parsing fails.
    """
    transcript_upper = transcript.upper()
    
    # Normalize action words using synonyms before regex matching
    normalized_transcript = normalize_action_words(transcript_upper, command_synonyms)
    logger.debug(f"Normalized Transcript: {normalized_transcript}")
    
    try:
        for activate_command in voice_activate_commands:
            activate_command_upper = activate_command.upper()
            # Use regex to search for the activation command as a whole word or phrase
            pattern = r'\b' + re.escape(activate_command_upper) + r'\b'
            match = re.search(pattern, normalized_transcript)
            if match:
                # Extract the portion of the transcript after the activation command
                command_after = normalized_transcript[match.end():].strip()
                logger.debug(f"Command After Activation: {command_after}")
                
                # Define regex pattern to extract action, quantity, and symbol
                # This pattern allows for optional "SHARES OF" between quantity and symbol
                command_pattern = r'^(BUY|SELL)\s+(\d+|\w+)\s+(?:SHARES\s+OF\s+)?(.+)$'
                command_match = re.match(command_pattern, command_after)
                
                if command_match:
                    action = command_match.group(1)  # Already standardized (BUY/SELL)
                    quantity_word = command_match.group(2)
                    spoken_tradingsymbol = command_match.group(3).strip().upper()
                    
                    # Map the spoken trading symbol to the standardized symbol
                    tradingsymbol = map_trading_symbol(spoken_tradingsymbol)
                    
                    if not tradingsymbol:
                        logger.error(f"Trading symbol '{spoken_tradingsymbol}' not recognized.")
                        return None, None, None
                    
                    try:
                        quantity = int(quantity_word)
                    except ValueError:
                        # Convert word numbers to integers (e.g., "twenty-three" -> 23)
                        try:
                            quantity = w2n.word_to_num(quantity_word)
                        except ValueError:
                            logger.error(f"Invalid quantity: {quantity_word}")
                            return None, None, None
                    
                    logger.info(f'Parsed command - Action: {action}, Quantity: {quantity}, Symbol: {tradingsymbol}')
                    return action, quantity, tradingsymbol
                else:
                    logger.error("Command pattern not matched.")
    except Exception as e:
        logger.error(f"Error parsing command: {str(e)}")
    return None, None, None

def place_order(action, quantity, tradingsymbol, exchange, product_type):
    """
    Place an order using the OpenAlgo API.

    Args:
        action (str): 'BUY' or 'SELL'.
        quantity (int): Number of shares to trade.
        tradingsymbol (str): Ticker symbol of the asset.
        exchange (str): Selected exchange (e.g., 'NSE').
        product_type (str): Type of product (e.g., 'CNC', 'NRML', 'MIS').

    Returns:
        dict: Response from the OpenAlgo API or an error message.
    """
    try:
        response = openalgo_client.placeorder(
            strategy="VoiceOrder",
            symbol=tradingsymbol,
            action=action,
            exchange=exchange,
            price_type="MARKET",
            product=product_type,
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
    
    # Retrieve Exchange, Product Type, and Model from form data
    exchange = request.form.get('exchange')
    product_type = request.form.get('product_type')
    model = request.form.get('model')
    
    # Validate Exchange and Product Type
    valid_exchanges = ["NSE", "NFO", "CDS", "BSE", "BFO", "BCD", "MCX", "NCDEX"]
    valid_product_types = ["CNC", "NRML", "MIS"]
    valid_models = ["whisper-large-v3", "whisper-large-v3-turbo", "distil-whisper-large-v3-en"]
    
    if exchange not in valid_exchanges:
        logger.error(f"Invalid exchange selected: {exchange}")
        return jsonify({"error": f"Invalid exchange selected: {exchange}"}), 400
    
    if product_type not in valid_product_types:
        logger.error(f"Invalid product type selected: {product_type}")
        return jsonify({"error": f"Invalid product type selected: {product_type}"}), 400
    
    if model not in valid_models:
        logger.error(f"Invalid model selected: {model}")
        return jsonify({"error": f"Invalid model selected: {model}"}), 400
    
    try:
        file_data = file.read()
        logger.info(f"Received audio file: name={file.filename}, size={len(file_data)} bytes, content_type={file.content_type}")
        result = call_groq_api(file_data, model)
        logger.info(f"Transcription result: {result}")
        
        # Process the transcription and place order if valid
        transcription = remove_punctuation(result.get('text', '').strip())
        logger.debug(f"Transcription after removing punctuation: {transcription}")
        action, quantity, tradingsymbol = parse_command(transcription)
        
        if all([action, quantity, tradingsymbol]):
            order_response = place_order(action, quantity, tradingsymbol, exchange, product_type)
            result['order_response'] = order_response
            result['action'] = action
            result['quantity'] = quantity
            result['symbol'] = tradingsymbol  # Updated field name
        else:
            result['order_response'] = {"error": "Invalid command"}
            result['action'] = None
            result['quantity'] = None
            result['symbol'] = None  # Ensure 'symbol' is set to None when command is invalid
        
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
    app.run(debug=True, port=5001)