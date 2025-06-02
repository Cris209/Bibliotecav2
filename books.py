from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os

app = Flask(__name__)
CORS(app)

# Cargar credenciales de Firebase desde variable de entorno render
service_account_info = json.loads(os.getenv("SERVICE_ACCOUNT_KEY"))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Definir la URL base de Open Library API
OPEN_LIBRARY_API_URL = "https://openlibrary.org"
OPEN_LIBRARY_COVERS_URL = "https://covers.openlibrary.org/b"

# Endpoint para registrar un nuevo usuario
@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "El correo electrónico y la contraseña son obligatorios."}), 400

    try:
        user = auth.create_user(
            email=email,
            password=password
        )
        return jsonify({"mensaje": "Usuario registrado exitosamente", "uid": user.uid}), 201
    except Exception as e:
        return jsonify({"error": f"Error al registrar usuario: {str(e)}"}), 500

# Endpoint para iniciar sesión (autenticación)
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
            "titulo": doc.get('title', 'Título no disponible'),
            "autores": doc.get('author_name', []),
            "descripcion": doc.get('first_sentence', ['No disponible'])[0] if 'first_sentence' in doc else 'No disponible',
            "imagen": imagen,
            "link": f"{OPEN_LIBRARY_API_URL}{doc.get('key', '')}" if 'key' in doc else '',
            "disponible_para_descarga": 'ia' in doc  # Indica si está disponible para descarga
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})

# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
