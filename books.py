from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os
import bcrypt
from threading import Lock
import base64
from cryptography.fernet import Fernet

app = Flask(__name__)
CORS(app)

# Configuración de Google Books API
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1"

# Simple encryption key (in production, use environment variables)
SECRET_KEY = b'your-secret-key-here-32-chars-long!'

def get_fernet():
    """Create a Fernet instance for encryption/decryption"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'static_salt_here',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)

def encrypt_data(data):
    """Encrypt data using Fernet"""
    try:
        json_string = json.dumps(data, ensure_ascii=False)
        fernet = get_fernet()
        encrypted = fernet.encrypt(json_string.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        print(f"Error encrypting data: {e}")
        return None

def decrypt_data(encrypted_data):
    """Decrypt data using Fernet"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_bytes)
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Error decrypting data: {e}")
        return None

def encrypt_response(data):
    """Encrypt response data"""
    encrypted = encrypt_data(data)
    if encrypted:
        return {"encrypted_data": encrypted}
    return data

def decrypt_request(request_data):
    """Decrypt request data"""
    if isinstance(request_data, dict) and "encrypted_data" in request_data:
        return decrypt_data(request_data["encrypted_data"])
    return request_data

# -----------------------------
# PATRÓN SINGLETON: FirebaseManager
# -----------------------------
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

# Inicializa Firebase (singleton)
firebase_manager = FirebaseManager()
db = firebase_manager.db
GOOGLE_BOOKS_API_KEY = firebase_manager.google_books_api_key

# -----------------------------
# PATRÓN FACTORY METHOD: UserFactory
# -----------------------------
class Usuario:
    def __init__(self, email, password):
        self.email = email
        self.password = password

class UsuarioAdmin(Usuario):
    def __init__(self, email, password):
        super().__init__(email, password)
        self.rol = "admin"

class UsuarioNormal(Usuario):
    def __init__(self, email, password):
        super().__init__(email, password)
        self.rol = "normal"

class UserFactory:
    @staticmethod
    def crear_usuario(tipo, email, password):
        if tipo == "admin":
            return UsuarioAdmin(email, password)
        return UsuarioNormal(email, password)

# -----------------------------
# Encriptación: bcrypt
# -----------------------------
def encriptar_contraseña(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# -----------------------------
# SIMULATED BOOK DATA (Temporary fix)
# -----------------------------
def get_simulated_books():
    """Return simulated book data instead of calling Google Books API"""
    return {
        "resultados": [
            {
                "id": "book1",
                "titulo": "El Señor de los Anillos",
                "autores": ["J.R.R. Tolkien"],
                "descripcion": "Una épica historia de fantasía sobre la lucha contra el mal.",
                "imagen": "https://via.placeholder.com/128x200/4A90E2/FFFFFF?text=Libro+1",
                "link": "https://example.com/book1",
                "precio": "Gratis",
                "disponible_para_descarga": True
            },
            {
                "id": "book2",
                "titulo": "Cien Años de Soledad",
                "autores": ["Gabriel García Márquez"],
                "descripcion": "Una obra maestra del realismo mágico latinoamericano.",
                "imagen": "https://via.placeholder.com/128x200/E74C3C/FFFFFF?text=Libro+2",
                "link": "https://example.com/book2",
                "precio": "Gratis",
                "disponible_para_descarga": True
            },
            {
                "id": "book3",
                "titulo": "Don Quijote de la Mancha",
                "autores": ["Miguel de Cervantes"],
                "descripcion": "La primera novela moderna y una de las mejores obras de la literatura universal.",
                "imagen": "https://via.placeholder.com/128x200/F39C12/FFFFFF?text=Libro+3",
                "link": "https://example.com/book3",
                "precio": "Gratis",
                "disponible_para_descarga": False
            },
            {
                "id": "book4",
                "titulo": "Rayuela",
                "autores": ["Julio Cortázar"],
                "descripcion": "Una novela experimental que revolucionó la literatura latinoamericana.",
                "imagen": "https://via.placeholder.com/128x200/9B59B6/FFFFFF?text=Libro+4",
                "link": "https://example.com/book4",
                "precio": "Gratis",
                "disponible_para_descarga": True
            },
            {
                "id": "book5",
                "titulo": "Pedro Páramo",
                "autores": ["Juan Rulfo"],
                "descripcion": "Una obra fundamental de la literatura mexicana del siglo XX.",
                "imagen": "https://via.placeholder.com/128x200/1ABC9C/FFFFFF?text=Libro+5",
                "link": "https://example.com/book5",
                "precio": "Gratis",
                "disponible_para_descarga": True
            }
        ]
    }

def search_simulated_books(query):
    """Search in simulated books"""
    all_books = get_simulated_books()["resultados"]
    query_lower = query.lower()
    
    filtered_books = [
        book for book in all_books
        if query_lower in book["titulo"].lower() or 
           any(query_lower in autor.lower() for autor in book["autores"])
    ]
    
    return {"resultados": filtered_books}

# -----------------------------
# RUTAS
# -----------------------------
@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    try:
        data = decrypt_request(request.get_json())
        
        nombre = data.get('nombre')
        apellido = data.get('apellido')
        gmail = data.get('gmail')
        password = data.get('password')
        tipo_usuario = data.get('tipo', 'normal')

        if not nombre or not apellido or not gmail or not password:
            return jsonify(encrypt_response({"error": "Todos los campos son obligatorios."})), 400

        if not gmail.endswith("@gmail.com"):
            return jsonify(encrypt_response({"error": "El correo debe ser un Gmail válido."})), 400

        usuario = UserFactory.crear_usuario(tipo_usuario, gmail, password)
        password_encriptada = encriptar_contraseña(usuario.password)

        user = auth.create_user(email=usuario.email, password=usuario.password)

        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre,
            "apellido": apellido,
            "email": usuario.email,
            "rol": usuario.rol,
            "password_encriptada": password_encriptada
        })

        return jsonify(encrypt_response({"mensaje": "Usuario registrado exitosamente", "uid": user.uid})), 201
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al registrar usuario: {str(e)}"})), 500

@app.route('/api/iniciar_sesion', methods=['POST'])
def iniciar_sesion():
    try:
        data = decrypt_request(request.get_json())
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify(encrypt_response({"error": "El correo electrónico y la contraseña son obligatorios."})), 400

        user = auth.get_user_by_email(email)
        if user:
            return jsonify(encrypt_response({"mensaje": "Inicio de sesión exitoso", "uid": user.uid})), 200
        else:
            return jsonify(encrypt_response({"error": "Usuario no encontrado"})), 404
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al iniciar sesión: {str(e)}"})), 500

@app.route('/api/usuario/<uid>', methods=['GET'])
def obtener_usuario(uid):
    try:
        user_doc = db.collection("usuarios").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return jsonify(encrypt_response(user_data)), 200
        else:
            return jsonify(encrypt_response({"error": "Usuario no encontrado"})), 404
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al obtener datos del usuario: {str(e)}"})), 500

# Endpoint para mostrar libros (usando datos simulados)
@app.route('/api/libros', methods=['GET'])
def mostrar_libros():
    try:
        # Use simulated data instead of Google Books API
        libros = get_simulated_books()
        return jsonify(encrypt_response(libros))
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al obtener libros: {str(e)}"})), 500

# Endpoint para buscar libros (usando datos simulados)
@app.route('/api/buscar_libros', methods=['GET'])
def buscar_libros():
    try:
        query = request.args.get('query', type=str)
        if not query:
            return jsonify(encrypt_response({"error": "El parámetro 'query' es obligatorio."})), 400
        
        # Use simulated search instead of Google Books API
        resultados = search_simulated_books(query)
        return jsonify(encrypt_response(resultados))
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al buscar libros: {str(e)}"})), 500

# Endpoint para obtener detalles de un libro específico
@app.route('/api/libros/<id>', methods=['GET'])
def obtener_libro(id):
    try:
        # Get book from simulated data
        all_books = get_simulated_books()["resultados"]
        libro = next((book for book in all_books if book["id"] == id), None)
        
        if not libro:
            return jsonify(encrypt_response({"error": "Libro no encontrado"})), 404
        
        # Add more details for the book
        libro_detallado = {
            **libro,
            "fecha_publicacion": "2023",
            "editorial": "Editorial Simulada",
            "paginas": 300,
            "categorias": ["Ficción", "Literatura"],
            "download_links": {
                "pdf": "https://example.com/download.pdf" if libro["disponible_para_descarga"] else "",
                "epub": "https://example.com/download.epub" if libro["disponible_para_descarga"] else ""
            }
        }
        
        return jsonify(encrypt_response(libro_detallado))
        
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al obtener detalles del libro: {str(e)}"})), 500

# Admin endpoints
@app.route('/api/admin/libros', methods=['POST'])
def agregar_libro():
    try:
        data = decrypt_request(request.get_json())
        
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
        return jsonify(encrypt_response({"mensaje": "Libro agregado exitosamente", "libro": response_data})), 201
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al agregar libro: {str(e)}"})), 500

@app.route('/api/admin/libros/<id>', methods=['DELETE'])
def eliminar_libro(id):
    try:
        db.collection("libros_admin").document(id).delete()
        return jsonify(encrypt_response({"mensaje": "Libro eliminado exitosamente"})), 200
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al eliminar libro: {str(e)}"})), 500

@app.route('/api/admin/libros', methods=['GET'])
def obtener_libros_admin():
    try:
        libros_ref = db.collection("libros_admin").stream()
        libros = []
        for libro in libros_ref:
            libros.append(libro.to_dict())
        
        return jsonify(encrypt_response({"libros": libros})), 200
    except Exception as e:
        return jsonify(encrypt_response({"error": f"Error al obtener libros: {str(e)}"})), 500

# Payment endpoint
@app.route('/api/payment', methods=['POST'])
def process_payment():
    try:
        data = decrypt_request(request.get_json())
        
        import uuid
        order_id = str(uuid.uuid4())
        
        order_data = {
            "order_id": order_id,
            "user_id": data.get('user_id'),
            "items": data.get('items', []),
            "total": data.get('total'),
            "payment_method": data.get('payment_method'),
            "status": "completed",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        
        db.collection("orders").document(order_id).set(order_data)
        
        return jsonify(encrypt_response({
            "success": True,
            "order_id": order_id,
            "message": "Payment processed successfully"
        })), 200
    except Exception as e:
        return jsonify(encrypt_response({
            "success": False,
            "error": f"Payment processing failed: {str(e)}"
        })), 500

# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 
