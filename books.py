import os
import json
import base64
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from threading import Lock

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Firebase Web API Key (for login)
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1"

# Encryption settings
SECRET_KEY = os.getenv("ENCRYPTION_KEY", "default-secret-key")
SALT = os.getenv("ENCRYPTION_SALT", "default-salt").encode()

def generate_key():
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))

cipher_suite = Fernet(generate_key())

def encrypt_data(data):
    try:
        json_data = json.dumps(data, ensure_ascii=False)
        encrypted_data = cipher_suite.encrypt(json_data.encode('utf-8'))
        return base64.b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

def decrypt_data(encrypted_data):
    try:
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted_data = cipher_suite.decrypt(encrypted_bytes)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

# Firebase Singleton
class FirebaseManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                service_account_info = json.loads(os.getenv("SERVICE_ACCOUNT_KEY"))
                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(cred)
                cls._instance = super().__new__(cls)
                cls._instance.db = firestore.client()
                cls._instance.google_books_api_key = service_account_info.get("GOOGLE_BOOKS_API_KEY") or os.getenv("GOOGLE_BOOKS_API_KEY")
        return cls._instance

firebase_manager = FirebaseManager()
db = firebase_manager.db
GOOGLE_BOOKS_API_KEY = firebase_manager.google_books_api_key

# Firebase Authentication with REST API
def login_with_firebase(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(response.json().get("error", {}).get("message", "Error desconocido"))

def verificar_token(token):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise Exception(f"Token inválido: {str(e)}")

@app.route('/api/iniciar_sesion', methods=['POST'])
def iniciar_sesion():
    encrypted_data = request.get_json().get('encrypted_data')
    if not encrypted_data:
        return jsonify({"error": "Datos encriptados requeridos"}), 400

    data = decrypt_data(encrypted_data)
    if not data:
        return jsonify({"error": "Error al desencriptar datos"}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "El correo electrónico y la contraseña son obligatorios."}), 400

    try:
        login_response = login_with_firebase(email, password)
        response_data = {
            "mensaje": "Inicio de sesión exitoso",
            "uid": login_response.get("localId"),
            "idToken": login_response.get("idToken"),
            "refreshToken": login_response.get("refreshToken"),
            "expiresIn": login_response.get("expiresIn")
        }
        encrypted_response = encrypt_data(response_data)
        return jsonify({"encrypted_data": encrypted_response}), 200

    except Exception as e:
        error_data = {"error": f"Error al iniciar sesión: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 401

@app.route('/api/ruta_protegida', methods=['GET'])
def ruta_protegida():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"error": "Token requerido"}), 401

    token = auth_header.replace("Bearer ", "")

    try:
        user_info = verificar_token(token)
        return jsonify({"mensaje": f"Acceso permitido para UID: {user_info['uid']}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
