from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import firebase_admin
from firebase_admin import firestore, credentials, auth
import json
import os

# Cargar credenciales de Firebase desde variable de entorno
service_account_info = json.loads(os.getenv("SERVICE_ACCOUNT_KEY"))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configurar Flask
app = Flask(__name__)
CORS(app)

# API Key de Google Books
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

# Función para obtener libros desde Google Books API
def fetch_books_from_google(query, max_results=10):
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={max_results}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("items", [])
    return []

@app.route("/books/search", methods=["GET"])
def search_books():
    query = request.args.get("query", "")
    if not query:
        return jsonify({"error": "Se requiere una consulta de búsqueda"}), 400
    
    books_data = fetch_books_from_google(query)
    books = [{
    "title": item["volumeInfo"].get("title"),
    "author": item["volumeInfo"].get("authors", []),  # Asegúrate de que authors sea una lista
    "publisher": item["volumeInfo"].get("publisher"),
    "category": item["volumeInfo"].get("categories", []),  # Asegúrate de que categories sea una lista
} for item in books_data]

    
    return jsonify(books), 200

# Función para verificar si el usuario está autenticado
def check_authenticated_user(token):
    try:
        token = token.replace("Bearer ", "") if token else None
        return auth.verify_id_token(token)
    except Exception:
        return None

@app.route('/books', methods=['GET'])
def get_all_books():
    try:
        books_ref = db.collection('books')
        books = [doc.to_dict() for doc in books_ref.stream()]
        
        if len(books) < 10:
            google_books = fetch_books_from_google("technology", max_results=10 - len(books))
            books.extend(google_books)
        
        return jsonify(books), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/books", methods=["POST"])
def add_book():
    token = request.headers.get("Authorization")
    decoded_token = check_authenticated_user(token)
    if not decoded_token or not decoded_token.get('admin', False):
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.json
    required_fields = ["title", "author", "category", "publisher", "popularity"]
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan datos"}), 400
    
    new_book_ref = db.collection("books").document()
    new_book_ref.set(data)
    return jsonify({"message": "Libro agregado correctamente"}), 201

@app.route("/books/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    token = request.headers.get("Authorization")
    decoded_token = check_authenticated_user(token)
    if not decoded_token or not decoded_token.get('admin', False):
        return jsonify({"error": "No autorizado"}), 403
    
    book_ref = db.collection("books").document(book_id)
    book = book_ref.get()
    if not book.exists:
        return jsonify({"error": "Libro no encontrado"}), 404
    
    book_ref.delete()
    return jsonify({"message": "Libro eliminado correctamente"}), 200

@app.route("/books/download/<book_id>", methods=["GET"])
def download_book(book_id):
    token = request.headers.get("Authorization")
    decoded_token = check_authenticated_user(token)
    if not decoded_token:
        return jsonify({"error": "Debe iniciar sesión para descargar el libro"}), 401
    
    book_ref = db.collection("books").document(book_id)
    book = book_ref.get()
    if not book.exists:
        return jsonify({"error": "Libro no encontrado"}), 404
    
    book_data = book.to_dict()
    return jsonify(book_data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
