from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os
import bcrypt
from threading import Lock

app = Flask(__name__)
CORS(app)

# Definir la URL base de Open Library API
OPEN_LIBRARY_API_URL = "https://openlibrary.org"
OPEN_LIBRARY_COVERS_URL = "https://covers.openlibrary.org/b"

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
        return cls._instance

# Inicializa Firebase (singleton)
firebase_manager = FirebaseManager()
db = firebase_manager.db

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
# RUTAS
# -----------------------------
@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    data = request.get_json()

    nombre = data.get('nombre')
    apellido = data.get('apellido')
    gmail = data.get('gmail')
    password = data.get('password')
    tipo_usuario = data.get('tipo', 'normal')

    # Validación de campos
    if not nombre or not apellido or not gmail or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    if not gmail.endswith("@gmail.com"):
        return jsonify({"error": "El correo debe ser un Gmail válido (ejemplo@gmail.com)."}), 400

    try:
        usuario = UserFactory.crear_usuario(tipo_usuario, gmail, password)
        password_encriptada = encriptar_contraseña(usuario.password)

        user = auth.create_user(email=usuario.email, password=usuario.password)

        # Guardar datos adicionales en Firestore
        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre,
            "apellido": apellido,
            "email": usuario.email,
            "rol": usuario.rol,
            "password_encriptada": password_encriptada
        })

        return jsonify({"mensaje": "Usuario registrado exitosamente", "uid": user.uid}), 201
    except Exception as e:
        return jsonify({"error": f"Error al registrar usuario: {str(e)}"}), 500


@app.route('/api/iniciar_sesion', methods=['POST'])
def iniciar_sesion():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "El correo electrónico y la contraseña son obligatorios."}), 400

    try:
        user = auth.get_user_by_email(email)
        if user:
            return jsonify({"mensaje": "Inicio de sesión exitoso", "uid": user.uid}), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al iniciar sesión: {str(e)}"}), 500

# Endpoint para buscar libros con un término específico
@app.route('/api/buscar_libros', methods=['GET'])
def buscar_libros():
    query = request.args.get('query', type=str)
    if not query:
        return jsonify({"error": "El parámetro 'query' es obligatorio."}), 400
    
    params = {
        'q': query,
        'limit': 10,
        'language': 'spa'  # Filtro para libros en español
    }
    
    response = requests.get(f"{OPEN_LIBRARY_API_URL}/search.json", params=params)
    
    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos de Open Library API"}), 500
    
    libros = response.json()
    resultados = []
    for doc in libros.get('docs', []):
        cover_id = doc.get('cover_i')
        imagen = f"{OPEN_LIBRARY_COVERS_URL}/id/{cover_id}-M.jpg" if cover_id else ''
        
        libro = {
            "titulo": doc.get('title', 'Título no disponible'),
            "autores": doc.get('author_name', []),
            "descripcion": doc.get('first_sentence', ['No disponible'])[0] if 'first_sentence' in doc else 'No disponible',
            "imagen": imagen,
            "link": f"{OPEN_LIBRARY_API_URL}{doc.get('key', '')}" if 'key' in doc else '',
            "disponible_para_descarga": 'ia' in doc  # Indica si está disponible para descarga
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})

# Endpoint para mostrar 10 libros predeterminados
@app.route('/api/libros', methods=['GET'])
def mostrar_10_libros():
    params = {
        'q': 'fiction',
        'limit': 10,
        'language': 'spa'  # Filtro para libros en español
    }

    response = requests.get(f"{OPEN_LIBRARY_API_URL}/search.json", params=params)

    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos de Open Library API"}), 500

    libros = response.json()
    resultados = []
    for doc in libros.get('docs', []):
        cover_id = doc.get('cover_i')
        imagen = f"{OPEN_LIBRARY_COVERS_URL}/id/{cover_id}-M.jpg" if cover_id else ''
        
        libro = {
            "id": id,
            "titulo": doc.get('title', 'Título no disponible'),
            "autores": doc.get('author_name', []),
            "descripcion": doc.get('first_sentence', ['No disponible'])[0] if 'first_sentence' in doc else 'No disponible',
            "imagen": imagen,
            "link": f"{OPEN_LIBRARY_API_URL}{doc.get('key', '')}" if 'key' in doc else '',
            "disponible_para_descarga": 'ia' in doc  # Indica si está disponible para descarga
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})
    
# Endpoint para obtener detalles de un libro específico
# En tu archivo de backend (app.py)
@app.route('/api/libros/<id>', methods=['GET'])
def obtener_libro(id):
    try:
        # URL correcta de Open Library API
        open_library_url = f"https://openlibrary.org/works/{id}.json"
        
        response = requests.get(open_library_url)
        response.raise_for_status()  # Lanza error si la solicitud falla
        
        libro_data = response.json()
        
        # Procesa los datos para tu estructura esperada
        libro = {
            "id": id,
            "titulo": libro_data.get("title", "Título no disponible"),
            "autores": [autor.get("author", {}).get("key", "Autor desconocido") 
                       for autor in libro_data.get("authors", [])],
            "descripcion": libro_data.get("description", "Descripción no disponible"),
            "imagen": f"https://covers.openlibrary.org/b/olid/{id}-M.jpg",
            "fecha_publicacion": libro_data.get("first_publish_date", ""),
            "link": f"https://openlibrary.org/works/{id}"
        }
        
        return jsonify(libro)
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener detalles del libro: {str(e)}"}), 500
        
# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
