from cryptography.fernet import Fernet
import base64
import json
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Secret key for encryption (in production, this should be stored securely)
SECRET_KEY = b'your-secret-key-here-32-chars-long!'

def get_fernet():
    """Create a Fernet instance for encryption/decryption"""
    # Generate a key from the secret
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'static_salt_here',  # In production, use a random salt
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)

def encrypt_data(data):
    """
    Encrypt data using Fernet (AES-128)
    @param data: Data to encrypt (dict, list, or primitive)
    @returns: Encrypted data as base64 string
    """
    try:
        # Convert data to JSON string
        json_string = json.dumps(data, ensure_ascii=False)
        
        # Encrypt the JSON string
        fernet = get_fernet()
        encrypted = fernet.encrypt(json_string.encode('utf-8'))
        
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        print(f"Error encrypting data: {e}")
        raise Exception("Failed to encrypt data")

def decrypt_data(encrypted_data):
    """
    Decrypt data using Fernet (AES-128)
    @param encrypted_data: Encrypted data as base64 string
    @returns: Decrypted data
    """
    try:
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        
        # Decrypt the data
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_bytes)
        
        # Parse JSON back to original format
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Error decrypting data: {e}")
        raise Exception("Failed to decrypt data")

def encrypt_response(data):
    """
    Encrypt response data before sending to frontend
    @param data: Response data to encrypt
    @returns: Object with encrypted data
    """
    return {
        "encrypted_data": encrypt_data(data)
    }

def decrypt_request(request_data):
    """
    Decrypt request data from frontend
    @param request_data: Request data from frontend
    @returns: Decrypted request data
    """
    if isinstance(request_data, dict) and "encrypted_data" in request_data:
        return decrypt_data(request_data["encrypted_data"])
    return request_data 
