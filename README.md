# Image Steganography Project

A beautiful web application for hiding and revealing secret messages within images using LSB (Least Significant Bit) steganography.

## Features

✨ **Beautiful UI**
- Modern gradient design with glassmorphism effects
- Responsive layout for all devices
- Smooth animations and transitions
- Real-time image previews

🔐 **Steganography**
- Hide messages in images using LSB encoding
- Reveal hidden messages from encoded images
- Support for PNG, JPG, GIF, and BMP formats
- Up to 1000 character messages

💾 **Database**
- SQLite database to track all operations
- Statistics on encode/decode operations
- Timestamp logging for all activities

🚀 **Performance**
- Fast encoding/decoding
- Efficient image processing
- Secure file handling

## Project Structure

```
project/
├── index.html          # Frontend UI
├── app.py              # Python Flask backend
├── requirements.txt    # Python dependencies
├── steganography.db    # SQLite database (auto-created)
├── uploads/            # Temporary upload folder (auto-created)
└── README.md           # This file
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser

### Setup Steps

1. **Clone or navigate to the project directory**
   ```bash
   cd c:\Users\vaish\OneDrive\Desktop\project
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Flask backend**
   ```bash
   python app.py
   ```
   The backend will start on `http://localhost:5000`

5. **Open the frontend**
   - Open `index.html` in your web browser
   - Or use a local server: `python -m http.server 8000`
   - Then navigate to `http://localhost:8000`

## Usage

### Encoding a Message

1. Click on the **"Encode Message"** tab
2. Upload an image (PNG, JPG, GIF, or BMP)
3. Enter your secret message (max 1000 characters)
4. Click **"Encode Message"** button
5. Download the encoded image
6. Share the image safely - the message is hidden inside!

### Decoding a Message

1. Click on the **"Decode Message"** tab
2. Upload an encoded image
3. Click **"Decode Message"** button
4. The hidden message will be revealed
5. Copy the message to clipboard if needed

## How It Works

### LSB Steganography

The application uses Least Significant Bit (LSB) steganography:

1. **Encoding Process:**
   - Convert the message to binary
   - Store the message length in the first 32 bits
   - Replace the LSB of each pixel's color channel with message bits
   - The changes are imperceptible to the human eye

2. **Decoding Process:**
   - Extract the LSBs from pixel color channels
   - Read the first 32 bits to get message length
   - Extract the remaining bits to reconstruct the message
   - Decode the binary back to text

### Example
- Original pixel: RGB(255, 128, 64)
- After encoding 'A' (01000001):
  - R: 255 → 254 (LSB: 0)
  - G: 128 → 129 (LSB: 1)
  - B: 64 → 64 (LSB: 0)
  - And so on...

## API Endpoints

### POST /encode
Encodes a message into an image.

**Request:**
- `image` (file): Image file to encode
- `message` (string): Message to hide

**Response:**
- PNG image with encoded message

### POST /decode
Decodes a message from an image.

**Request:**
- `image` (file): Encoded image file

**Response:**
```json
{
  "message": "Your hidden message here"
}
```

### GET /stats
Get statistics about operations.

**Response:**
```json
{
  "total_operations": 42,
  "encode_count": 25,
  "decode_count": 17,
  "total_characters": 5234
}
```

### GET /health
Check if the backend is running.

**Response:**
```json
{
  "status": "healthy"
}
```

## Database Schema

### operations table
```sql
CREATE TABLE operations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  operation_type TEXT,           -- 'encode' or 'decode'
  timestamp DATETIME,            -- When operation occurred
  message_length INTEGER,        -- Length of message
  image_name TEXT,              -- Original image filename
  status TEXT                   -- 'success' or 'failed'
)
```

## Limitations

- Maximum message size: 1000 characters
- Maximum image size: 10MB
- Supported formats: PNG, JPG, GIF, BMP
- Message capacity depends on image dimensions
- For a 1000x1000 image: ~375KB of data can be hidden

## Security Notes

- Messages are encoded in the image itself, not encrypted
- For sensitive data, encrypt the message before encoding
- The encoded image looks identical to the original
- Only someone who knows to look for hidden data will find it

## Troubleshooting

### Backend won't start
- Ensure Python 3.8+ is installed
- Check if port 5000 is available
- Verify all dependencies are installed: `pip install -r requirements.txt`

### CORS errors
- The backend has CORS enabled for localhost
- If accessing from a different domain, update CORS settings in `app.py`

### Image upload fails
- Check file size (max 10MB)
- Verify file format is supported
- Ensure image has sufficient pixels for message

### Decoding returns error
- Image may not contain encoded data
- Image may be corrupted
- Try with a different encoded image

## Performance Tips

- Use PNG format for best quality preservation
- Larger images can hide longer messages
- Encoding/decoding is fast (< 1 second for most images)

## Future Enhancements

- [ ] Message encryption before encoding
- [ ] Support for audio steganography
- [ ] Batch processing
- [ ] Advanced image formats (WebP, AVIF)
- [ ] User authentication
- [ ] Cloud storage integration
- [ ] Mobile app version

## License

This project is open source and available for educational purposes.

## Support

For issues or questions, please check the troubleshooting section or review the code comments.

---

**Built with ❤️ using Flask, Pillow, and Tailwind CSS**
