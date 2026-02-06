"""
Configuration file for Image Steganography Project
"""

import os

# Flask Configuration
FLASK_ENV = 'development'
DEBUG = True
HOST = 'localhost'
PORT = 5000

# File Upload Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Database Configuration
DATABASE_NAME = 'steganography.db'

# Steganography Configuration
MAX_MESSAGE_LENGTH = 1000  # characters
MIN_IMAGE_SIZE = 100  # pixels (width or height)

# CORS Configuration
CORS_ORIGINS = ['http://localhost:8000', 'http://localhost:3000', 'http://127.0.0.1:8000']

# Create necessary directories
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
