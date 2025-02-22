from flask import Flask, jsonify, request
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os

app = Flask(__name__)

# Cargar credenciales de Firebase desde variable de entorno render
service_account_info = json.loads(os.getenv("SERVICE_ACCOUNT_KEY"))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Obtener referencia a Firestore
db = firestore.client()

# Definir la URL base de Google Books API
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"

# Endpoint para registrar un nuevo usuario
@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "El correo electrónico y la contraseña son obligatorios."}), 400

    try:
        # Crear usuario con correo electrónico y contraseña
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
        # Verificar si el usuario existe y la contraseña es correcta
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
        'maxResults': 10,
        'langRestrict': 'es'
    }
    
    response = requests.get(GOOGLE_BOOKS_API_URL, params=params)
    
    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos de Google Books API"}), 500
    
    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        libro = {
            "titulo": item['volumeInfo'].get('title'),
            "autores": item['volumeInfo'].get('authors', []),
            "descripcion": item['volumeInfo'].get('description', 'No disponible'),
            "imagen": item['volumeInfo'].get('imageLinks', {}).get('thumbnail', ''),
            "link": item['volumeInfo'].get('infoLink', '')
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})

# Endpoint para mostrar 10 libros predeterminados
@app.route('/api/mostrar_10_libros', methods=['GET'])
def mostrar_10_libros():
    params = {
        'q': 'fiction',
        'maxResults': 10,
        'langRestrict': 'es'
    }

    response = requests.get(GOOGLE_BOOKS_API_URL, params=params)

    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos de Google Books API"}), 500

    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        libro = {
            "titulo": item['volumeInfo'].get('title'),
            "autores": item['volumeInfo'].get('authors', []),
            "descripcion": item['volumeInfo'].get('description', 'No disponible'),
            "imagen": item['volumeInfo'].get('imageLinks', {}).get('thumbnail', ''),
            "link": item['volumeInfo'].get('infoLink', '')
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})

# Endpoint para agregar un libro a Firebase
@app.route('/api/agregar_libro', methods=['POST'])
def agregar_libro():
    # Obtener los datos del libro desde el cuerpo de la solicitud
    datos_libro = request.get_json()

    # Validar que todos los campos necesarios estén presentes
    if not datos_libro.get('titulo') or not datos_libro.get('autores') or not datos_libro.get('descripcion') or not datos_libro.get('imagen') or not datos_libro.get('link'):
        return jsonify({"error": "Faltan datos necesarios para agregar el libro"}), 400

    # Crear un diccionario para el libro
    libro = {
        "titulo": datos_libro.get('titulo'),
        "autores": datos_libro.get('autores'),
        "descripcion": datos_libro.get('descripcion'),
        "imagen": datos_libro.get('imagen'),
        "link": datos_libro.get('link')
    }

    # Agregar el libro a Firestore en la colección "libros"
    try:
        db.collection('libros').add(libro)
        return jsonify({"mensaje": "Libro agregado exitosamente"}), 201
    except Exception as e:
        return jsonify({"error": f"Error al agregar el libro: {str(e)}"}), 500
    
# Endpoint para eliminar un libro de Firebase
@app.route('/api/eliminar_libro/<libro_id>', methods=['DELETE'])
def eliminar_libro(libro_id):
    # Buscar el libro por ID en Firestore
    libro_ref = db.collection('libros').document(libro_id)

    # Verificar si el libro existe
    libro = libro_ref.get()

    if not libro.exists:
        return jsonify({"error": "Libro no encontrado"}), 404

    try:
        # Eliminar el libro de Firestore
        libro_ref.delete()
        return jsonify({"mensaje": "Libro eliminado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar el libro: {str(e)}"}), 500
    
# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

