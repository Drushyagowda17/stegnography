from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import io
import os
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime
import json
import base64

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Database initialization
def init_db():
    conn = sqlite3.connect('steganography.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS operations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  operation_type TEXT,
                  timestamp DATETIME,
                  message_length INTEGER,
                  image_name TEXT,
                  status TEXT,
                  data_type TEXT)''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_operation(operation_type, message_length, image_name, status, data_type='text'):
    conn = sqlite3.connect('steganography.db')
    c = conn.cursor()
    c.execute('''INSERT INTO operations (operation_type, timestamp, message_length, image_name, status, data_type)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (operation_type, datetime.now(), message_length, image_name, status, data_type))
    conn.commit()
    conn.close()

def detect_data_type(data):
    """Detect if data is text, audio, video, or binary"""
    if isinstance(data, str):
        try:
            data.encode('utf-8')
            return 'text'
        except:
            return 'binary'
    return 'binary'

def encode_message_to_image(image, message, data_type='text'):
    """
    Encode a message into an image using LSB steganography
    """
    try:
        # Convert image to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert message to binary
        if isinstance(message, str):
            message_bytes = message.encode('utf-8')
        else:
            message_bytes = message
        
        message_length = len(message_bytes)
        
        # Check if message fits in image
        pixels = image.width * image.height
        max_bytes = pixels * 3 // 8  # 3 bytes per pixel, 8 bits per byte
        
        if message_length > max_bytes:
            raise ValueError(f"Message too large for image. Max: {max_bytes} bytes")
        
        # Create binary string: type (8 bits) + length (32 bits) + message
        type_binary = format(ord(data_type[0]) if data_type else ord('t'), '08b')
        length_binary = format(message_length, '032b')
        message_binary = ''.join(format(byte, '08b') for byte in message_bytes)
        full_binary = type_binary + length_binary + message_binary
        
        # Get pixel data
        pixels_data = list(image.getdata())
        
        # Encode binary data into LSBs
        bit_index = 0
        for pixel_index in range(len(pixels_data)):
            if bit_index >= len(full_binary):
                break
            
            pixel = list(pixels_data[pixel_index])
            
            for color_index in range(3):  # RGB
                if bit_index >= len(full_binary):
                    break
                
                # Clear LSB and set new bit
                pixel[color_index] = (pixel[color_index] & 0xFE) | int(full_binary[bit_index])
                bit_index += 1
            
            pixels_data[pixel_index] = tuple(pixel)
        
        # Create new image with encoded data
        encoded_image = Image.new('RGB', (image.width, image.height))
        encoded_image.putdata(pixels_data)
        
        return encoded_image
    
    except Exception as e:
        raise Exception(f"Encoding error: {str(e)}")

def decode_message_from_image(image):
    """
    Decode a message from an image using LSB steganography
    """
    try:
        # Convert image to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extract binary data from LSBs
        pixels_data = list(image.getdata())
        binary_string = ''
        
        for pixel in pixels_data:
            for color_value in pixel:
                binary_string += str(color_value & 1)
        
        # Extract data type (first 8 bits)
        if len(binary_string) < 8:
            raise ValueError("Image does not contain valid encoded data")
        
        data_type_code = int(binary_string[:8], 2)
        data_type = chr(data_type_code) if data_type_code < 128 else 't'
        
        # Extract message length (next 32 bits)
        if len(binary_string) < 40:
            raise ValueError("Image does not contain valid encoded data")
        
        message_length = int(binary_string[8:40], 2)
        
        # Extract message
        message_binary = binary_string[40:40 + (message_length * 8)]
        
        if len(message_binary) < message_length * 8:
            raise ValueError("Incomplete message in image")
        
        # Convert binary to message
        message_bytes = bytes(int(message_binary[i:i+8], 2) for i in range(0, len(message_binary), 8))
        
        try:
            message = message_bytes.decode('utf-8')
        except:
            message = base64.b64encode(message_bytes).decode('utf-8')
            data_type = 'binary'
        
        return {
            'message': message,
            'data_type': data_type,
            'length': message_length
        }
    
    except Exception as e:
        raise Exception(f"Decoding error: {str(e)}")

@app.route('/encode', methods=['POST'])
def encode():
    try:
        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        if 'message' not in request.form:
            return jsonify({'error': 'No message provided'}), 400
        
        file = request.files['image']
        message = request.form['message']
        data_type = request.form.get('data_type', 'text')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, GIF, BMP'}), 400
        
        if len(message) == 0:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if len(message) > 100000:
            return jsonify({'error': 'Message too long (max 100000 characters)'}), 400
        
        # Open image
        image = Image.open(file.stream)
        
        # Encode message
        encoded_image = encode_message_to_image(image, message, data_type)
        
        # Save to bytes
        img_io = io.BytesIO()
        encoded_image.save(img_io, 'PNG', quality=95)
        img_io.seek(0)
        
        # Log operation
        log_operation('encode', len(message), secure_filename(file.filename), 'success', data_type)
        
        return app.response_class(
            response=img_io.getvalue(),
            status=200,
            mimetype='image/png'
        )
    
    except Exception as e:
        log_operation('encode', 0, '', 'failed', 'text')
        return jsonify({'error': str(e)}), 500

@app.route('/decode', methods=['POST'])
def decode():
    try:
        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, GIF, BMP'}), 400
        
        # Open image
        image = Image.open(file.stream)
        
        # Decode message
        result = decode_message_from_image(image)
        
        # Log operation
        log_operation('decode', result['length'], secure_filename(file.filename), 'success', result['data_type'])
        
        return jsonify({
            'message': result['message'],
            'data_type': result['data_type'],
            'length': result['length'],
            'has_data': True
        }), 200
    
    except Exception as e:
        # Check if it's a "no data" error
        if "does not contain valid encoded data" in str(e):
            return jsonify({
                'has_data': False,
                'message': 'No hidden data found in this image'
            }), 200
        
        log_operation('decode', 0, '', 'failed', 'text')
        return jsonify({'error': str(e), 'has_data': False}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        conn = sqlite3.connect('steganography.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM operations WHERE status = "success"')
        total_operations = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM operations WHERE operation_type = "encode" AND status = "success"')
        encode_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM operations WHERE operation_type = "decode" AND status = "success"')
        decode_count = c.fetchone()[0]
        
        c.execute('SELECT SUM(message_length) FROM operations WHERE status = "success"')
        total_chars = c.fetchone()[0] or 0
        
        c.execute('SELECT data_type, COUNT(*) FROM operations WHERE status = "success" GROUP BY data_type')
        data_types = dict(c.fetchall())
        
        conn.close()
        
        return jsonify({
            'total_operations': total_operations,
            'encode_count': encode_count,
            'decode_count': decode_count,
            'total_characters': total_chars,
            'data_types': data_types
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
