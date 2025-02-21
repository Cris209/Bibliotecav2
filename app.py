from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# Inicializar Firebase
firebase_config = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configurar Flask
app = Flask(__name__)
CORS(app)

# Token de administrador (almacenado en variable de entorno para seguridad)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "default_admin_token")

# 📚 Obtener todos los libros
@app.route("/books", methods=["GET"])
def get_books():
    books_ref = db.collection("books").get()
    books = [book.to_dict() for book in books_ref]
    return jsonify(books), 200

# 🔍 Buscar libros por autor, categoría, editorial o título
@app.route("/books/search", methods=["GET"])
def search_books():
    author = request.args.get("author", "").lower()
    category = request.args.get("category", "").lower()
    publisher = request.args.get("publisher", "").lower()
    title = request.args.get("title", "").lower()

    books_ref = db.collection("books").get()
    books = [book.to_dict() for book in books_ref]

    # Filtrar en Python
    filtered_books = [
        book for book in books if (
            (not author or author in book.get("author", "").lower()) and
            (not category or category in book.get("category", "").lower()) and
            (not publisher or publisher in book.get("publisher", "").lower()) and
            (not title or title in book.get("title", "").lower())
        )
    ]

    return jsonify(filtered_books), 200

# 🌟 Obtener los libros más populares
@app.route("/books/popular", methods=["GET"])
def get_popular_books():
    popular_books = db.collection("books").order_by("popularity", direction=firestore.Query.DESCENDING).limit(5).get()
    books = [book.to_dict() for book in popular_books]
    return jsonify(books), 200

# 🆕 Agregar un nuevo libro (Solo admin)
@app.route("/books", methods=["POST"])
def add_book():
    # Verificar si el usuario es administrador
    token = request.headers.get("Authorization")
    if not token or token != f"Bearer {ADMIN_TOKEN}":
        return jsonify({"error": "No autorizado"}), 403

    data = request.json
    if not data or not all(key in data for key in ["title", "author", "category", "publisher", "popularity"]):
        return jsonify({"error": "Faltan datos"}), 400

    # Guardar en Firestore
    new_book_ref = db.collection("books").document()
    new_book_ref.set(data)

    return jsonify({"message": "Libro agregado correctamente"}), 201

# 🗑 Eliminar un libro (Solo admin)
@app.route("/books/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    # Verificar si el usuario es administrador
    token = request.headers.get("Authorization")
    if not token or token != f"Bearer {ADMIN_TOKEN}":
        return jsonify({"error": "No autorizado"}), 403

    book_ref = db.collection("books").document(book_id)
    
    # Verificar si el libro existe
    if not book_ref.get().exists:
        return jsonify({"error": "Libro no encontrado"}), 404

    book_ref.delete()
    return jsonify({"message": "Libro eliminado correctamente"}), 200

# Iniciar el servidor
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
