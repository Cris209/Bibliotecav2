from flask import Flask, request, jsonify
import requests
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
import json
import os
from firebase_admin import auth

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configurar Flask
app = Flask(__name__)

# Tu API Key de Google Books
GOOGLE_BOOKS_API_KEY = os.getenv("AIzaSyCNaLXQirFNEXYFeAS8RTg8YbYe12Z2DNs")

# Función para obtener libros desde Google Books API
def fetch_books_from_google(query):
    # URL base de la API de Google Books
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}"

    # Realizar la solicitud GET a la API de Google Books
    response = requests.get(url)

    # Verificar si la solicitud fue exitosa (código de estado 200)
    if response.status_code == 200:
        return response.json()  # Devuelve los resultados en formato JSON
    else:
        return None  # Si no se pudo obtener los datos, devuelve None

# Ejemplo de uso dentro de una ruta para buscar libros
@app.route("/books/search", methods=["GET"])
def search_books():
    query = request.args.get("query", "")
    
    if not query:
        return jsonify({"error": "Se requiere una consulta de búsqueda"}), 400
    
    books_data = fetch_books_from_google(query)

    if books_data:
        # Extraer los libros y devolverlos
        books = [
            {
                "title": item["volumeInfo"].get("title"),
                "author": item["volumeInfo"].get("authors", []),
                "publisher": item["volumeInfo"].get("publisher"),
                "category": item["volumeInfo"].get("categories", []),
            }
            for item in books_data.get("items", [])
        ]
        return jsonify(books), 200
    else:
        return jsonify({"error": "No se pudo obtener datos de la API de Google Books"}), 500

# Función para verificar si el usuario está autenticado (solo usuarios logueados pueden descargar libros)
def check_authenticated_user(token):
    try:
        # Verificar el token de Firebase Auth
        decoded_token = auth.verify_id_token(token)
        return decoded_token  # Devuelve la información del usuario
    except Exception as e:
        return None  # Si el token no es válido o no está presente

# Función para obtener todos los libros desde Firestore
@app.route("/books", methods=["GET"])
def get_books():
    books_ref = db.collection("books").get()
    books = [book.to_dict() for book in books_ref]
    return jsonify(books), 200

# Endpoint para agregar un libro (solo admin)
@app.route("/books", methods=["POST"])
def add_book():
    token = request.headers.get("Authorization")
    
    # Verificar que el token esté presente y sea válido
    decoded_token = check_authenticated_user(token)
    if not decoded_token or not decoded_token.get('admin', False):
        return jsonify({"error": "No autorizado"}), 403

    data = request.json
    if not data or not all(key in data for key in ["title", "author", "category", "publisher", "popularity"]):
        return jsonify({"error": "Faltan datos"}), 400

    # Guardar en Firestore
    new_book_ref = db.collection("books").document()
    new_book_ref.set(data)

    return jsonify({"message": "Libro agregado correctamente"}), 201

# Endpoint para eliminar un libro (solo admin)
@app.route("/books/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    token = request.headers.get("Authorization")
    
    # Verificar que el token esté presente y sea válido
    decoded_token = check_authenticated_user(token)
    if not decoded_token or not decoded_token.get('admin', False):
        return jsonify({"error": "No autorizado"}), 403

    book_ref = db.collection("books").document(book_id)
    
    # Verificar si el libro existe
    if not book_ref.get().exists:
        return jsonify({"error": "Libro no encontrado"}), 404

    book_ref.delete()
    return jsonify({"message": "Libro eliminado correctamente"}), 200

# Endpoint para descargar un libro (solo usuarios autenticados)
@app.route("/books/download/<book_id>", methods=["GET"])
def download_book(book_id):
    token = request.headers.get("Authorization")
    
    # Verificar si el usuario está autenticado
    decoded_token = check_authenticated_user(token)
    if not decoded_token:
        return jsonify({"error": "Debe iniciar sesión para descargar el libro"}), 401

    book_ref = db.collection("books").document(book_id)
    
    # Verificar si el libro existe
    book = book_ref.get()
    if not book.exists:
        return jsonify({"error": "Libro no encontrado"}), 404

    book_data = book.to_dict()
    # Aquí podrías agregar la lógica de descarga de un archivo, por ejemplo un PDF.
    # Este ejemplo solo devuelve los datos del libro.
    return jsonify(book_data), 200

# Iniciar el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
