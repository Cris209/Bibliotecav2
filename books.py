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

def register_with_firebase(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
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

@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    encrypted_data = request.get_json().get('encrypted_data')
    if not encrypted_data:
        return jsonify({"error": "Datos encriptados requeridos"}), 400

    data = decrypt_data(encrypted_data)
    if not data:
        return jsonify({"error": "Error al desencriptar datos"}), 400

    nombre = data.get('nombre')
    apellido = data.get('apellido')
    gmail = data.get('gmail')
    password = data.get('password')

    if not nombre or not apellido or not gmail or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    if not gmail.endswith("@gmail.com"):
        return jsonify({"error": "El correo debe ser un Gmail válido (ejemplo@gmail.com)."}), 400

    try:
        # Register user with Firebase
        register_response = register_with_firebase(gmail, password)
        
        # Store additional user data in Firestore
        user_data = {
            "nombre": nombre,
            "apellido": apellido,
            "email": gmail,
            "rol": "normal",  # Default role
            "fecha_registro": firestore.SERVER_TIMESTAMP
        }
        
        db.collection("usuarios").document(register_response.get("localId")).set(user_data)
        
        response_data = {
            "mensaje": "Usuario registrado exitosamente",
            "uid": register_response.get("localId"),
            "idToken": register_response.get("idToken"),
            "refreshToken": register_response.get("refreshToken"),
            "expiresIn": register_response.get("expiresIn")
        }
        encrypted_response = encrypt_data(response_data)
        return jsonify({"encrypted_data": encrypted_response}), 201

    except Exception as e:
        error_data = {"error": f"Error al registrar usuario: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 400

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

@app.route('/api/usuario/<uid>', methods=['GET'])
def obtener_usuario(uid):
    try:
        user_doc = db.collection("usuarios").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            encrypted_response = encrypt_data(user_data)
            return jsonify({"encrypted_data": encrypted_response}), 200
        else:
            error_data = {"error": "Usuario no encontrado"}
            encrypted_error = encrypt_data(error_data)
            return jsonify({"encrypted_data": encrypted_error}), 404
    except Exception as e:
        error_data = {"error": f"Error al obtener datos del usuario: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

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

# Endpoint para buscar libros con un término específico
@app.route('/api/buscar_libros', methods=['GET'])
def buscar_libros():
    query = request.args.get('query', type=str)
    if not query:
        error_data = {"error": "El parámetro 'query' es obligatorio."}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 400
    
    params = {
        'q': query,
        'maxResults': 10,
        'langRestrict': 'es',
        'filter': 'paid-ebooks',
        'key': GOOGLE_BOOKS_API_KEY
    }
    
    response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes", params=params)
    
    if response.status_code != 200:
        error_data = {"error": "Error al obtener datos de Google Books API"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500
    
    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        volume_info = item.get('volumeInfo', {})
        imagen = volume_info.get('imageLinks', {}).get('thumbnail', '').replace('http://', 'https://') if 'imageLinks' in volume_info else ''
        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"

        
        libro = {
            "id": item.get('id', ''),
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'No disponible'),
            "imagen": imagen,
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": 'pdf' in item.get('accessInfo', {}).get('epub', {}).get('downloadLink', '') or 
                                      'pdf' in item.get('accessInfo', {}).get('pdf', {}).get('downloadLink', '')
        }
        resultados.append(libro)

    response_data = {"resultados": resultados}
    encrypted_response = encrypt_data(response_data)
    return jsonify({"encrypted_data": encrypted_response})

# Endpoint para mostrar 10 libros predeterminados
@app.route('/api/libros', methods=['GET'])
def mostrar_10_libros():
    params = {
        'q': 'fiction',
        'maxResults': 10,
        'langRestrict': 'es', 
        'filter': 'paid-ebooks',
        'key': GOOGLE_BOOKS_API_KEY
    }

    response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes", params=params)

    if response.status_code != 200:
        error_data = {"error": "Error al obtener datos de Google Books API"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        volume_info = item.get('volumeInfo', {})
        imagen = volume_info.get('imageLinks', {}).get('thumbnail', '').replace('http://', 'https://') if 'imageLinks' in volume_info else ''
        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"
        
        libro = {
            "id": item.get('id', ''),
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'No disponible'),
            "imagen": imagen,
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": 'pdf' in item.get('accessInfo', {}).get('epub', {}).get('downloadLink', '') or 
                                      'pdf' in item.get('accessInfo', {}).get('pdf', {}).get('downloadLink', '')
        }
        resultados.append(libro)

    response_data = {"resultados": resultados}
    encrypted_response = encrypt_data(response_data)
    return jsonify({"encrypted_data": encrypted_response})
    
# Endpoint para obtener detalles de un libro específico
@app.route('/api/libros/<id>', methods=['GET'])
def obtener_libro(id):
    try:
        response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes/{id}?key={GOOGLE_BOOKS_API_KEY}")
        response.raise_for_status()
        
        item = response.json()
        volume_info = item.get('volumeInfo', {})
        access_info = item.get('accessInfo', {})

        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"
        
        # Procesar información de la imagen
        image_links = volume_info.get('imageLinks', {})
        imagen = image_links.get('thumbnail', '').replace('http://', 'https://')
        if not imagen and 'smallThumbnail' in image_links:
            imagen = image_links['smallThumbnail'].replace('http://', 'https://')
        
        libro = {
            "id": id,
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'Descripción no disponible'),
            "imagen": imagen,
            "fecha_publicacion": volume_info.get('publishedDate', ''),
            "editorial": volume_info.get('publisher', ''),
            "paginas": volume_info.get('pageCount', 0),
            "categorias": volume_info.get('categories', []),
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": access_info.get('pdf', {}).get('isAvailable', False) or 
                                        access_info.get('epub', {}).get('isAvailable', False),
            "download_links": {
                "pdf": access_info.get('pdf', {}).get('downloadLink', ''),
                "epub": access_info.get('epub', {}).get('downloadLink', '')
            }
        }
        
        encrypted_response = encrypt_data(libro)
        return jsonify({"encrypted_data": encrypted_response})
        
    except Exception as e:
        error_data = {"error": f"Error al obtener detalles del libro: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

@app.route('/api/libros/<id>/disponibilidad', methods=['GET'])
def verificar_disponibilidad_descarga(id):
    try:
        response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes/{id}?key={GOOGLE_BOOKS_API_KEY}")
        response.raise_for_status()
        
        item = response.json()
        access_info = item.get('accessInfo', {})
        
        pdf_available = access_info.get('pdf', {}).get('isAvailable', False)
        epub_available = access_info.get('epub', {}).get('isAvailable', False)
        
        disponible = pdf_available or epub_available
        
        if disponible:
            response_data = {
                "disponible": True,
                "formato": "PDF" if pdf_available else "EPUB",
                "download_link": access_info.get('pdf', {}).get('downloadLink', '') if pdf_available else 
                               access_info.get('epub', {}).get('downloadLink', ''),
                "mensaje": "Disponible para descarga"
            }
        else:
            response_data = {
                "disponible": False,
                "mensaje": "Este libro no está disponible para descarga"
            }
        
        encrypted_response = encrypt_data(response_data)
        return jsonify({"encrypted_data": encrypted_response})
        
    except Exception as e:
        error_data = {
            "error": f"Error al verificar disponibilidad: {str(e)}",
            "disponible": False
        }
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

# -----------------------------
# ADMIN ENDPOINTS
# -----------------------------

@app.route('/api/admin/libros', methods=['POST'])
def agregar_libro():
    # Decrypt incoming data
    encrypted_data = request.get_json().get('encrypted_data')
    if not encrypted_data:
        return jsonify({"error": "Datos encriptados requeridos"}), 400
    
    data = decrypt_data(encrypted_data)
    if not data:
        return jsonify({"error": "Error al desencriptar datos"}), 400
    
    # Verificar si el usuario es admin (esto debería implementarse con autenticación real)
    # Por ahora, asumimos que es admin si se llama desde el frontend admin
    
    try:
        libro_data = {
            "id": data.get('id'),
            "titulo": data.get('titulo'),
            "autores": data.get('autores', []),
            "descripcion": data.get('descripcion'),
            "imagen": data.get('imagen'),
            "precio": data.get('precio'),
             "pdf_url": data.get('pdf_url', ''),
            "fecha_agregado": firestore.SERVER_TIMESTAMP
        }
        
        # Guardar en Firestore
        db.collection("libros_admin").document(libro_data['id']).set(libro_data)

        response_data = {
            "id": data.get('id'),
            "titulo": data.get('titulo'),
            "autores": data.get('autores', []),
            "descripcion": data.get('descripcion'),
            "imagen": data.get('imagen'),
            "precio": data.get('precio'),
             "pdf_url": data.get('pdf_url', '')
        }
        encrypted_response = encrypt_data({"mensaje": "Libro agregado exitosamente", "libro": response_data})
        return jsonify({"encrypted_data": encrypted_response}), 201
    except Exception as e:
        error_data = {"error": f"Error al agregar libro: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

@app.route('/api/admin/libros/<id>', methods=['DELETE'])
def eliminar_libro(id):
    try:
        # Eliminar de Firestore
        db.collection("libros_admin").document(id).delete()
        
        response_data = {"mensaje": "Libro eliminado exitosamente"}
        encrypted_response = encrypt_data(response_data)
        return jsonify({"encrypted_data": encrypted_response}), 200
    except Exception as e:
        error_data = {"error": f"Error al eliminar libro: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

@app.route('/api/admin/libros', methods=['GET'])
def obtener_libros_admin():
    try:
        libros_ref = db.collection("libros_admin").stream()
        libros = []
        for libro in libros_ref:
            libros.append(libro.to_dict())
        
        response_data = {"libros": libros}
        encrypted_response = encrypt_data(response_data)
        return jsonify({"encrypted_data": encrypted_response}), 200
    except Exception as e:
        error_data = {"error": f"Error al obtener libros: {str(e)}"}
        encrypted_error = encrypt_data(error_data)
        return jsonify({"encrypted_data": encrypted_error}), 500

# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 
