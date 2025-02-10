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

app = Flask(__name__)
CORS(app)  # Permite que el frontend pueda hacer peticiones

# Ruta para obtener todos los libros
@app.route("/books", methods=["GET"])
def get_books():
    books_ref = db.collection("books").get()
    books = [book.to_dict() for book in books_ref]
    return jsonify(books), 200

# Ruta para buscar libros por autor, categoría, editorial o título
@app.route("/books/search", methods=["GET"])
def search_books():
    author = request.args.get("author")  # Ahora estamos buscando el parámetro 'author' directamente
    category = request.args.get("category")
    publisher = request.args.get("publisher")
    title = request.args.get("title")

    # Verificamos si al menos uno de los parámetros de búsqueda está presente
    if not any([author, category, publisher, title]):
        return jsonify({"error": "Faltan parámetros"}), 400

    # Creamos la referencia para la búsqueda
    books_ref = db.collection("books")

    if author:
        books_ref = books_ref.where("author", "==", author)
    if category:
        books_ref = books_ref.where("category", "==", category)
    if publisher:
        books_ref = books_ref.where("publisher", "==", publisher)
    if title:
        books_ref = books_ref.where("title", "==", title)

    books = [book.to_dict() for book in books_ref.get()]
    return jsonify(books), 200

# Ruta para obtener los libros más populares
@app.route("/books/popular", methods=["GET"])
def get_popular_books():
    popular_books = db.collection("books").order_by("popularity", direction=firestore.Query.DESCENDING).limit(5).get()
    books = [book.to_dict() for book in popular_books]
    return jsonify(books), 200

# Ruta para iniciar sesión (aquí puedes agregar la lógica de autenticación que necesites)
@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # Aquí iría la lógica de validación de usuario
    if username == "test" and password == "password":
        return jsonify({"message": "Inicio de sesión exitoso"}), 200
    return jsonify({"error": "Credenciales incorrectas"}), 401

# Ruta para obtener las categorías
@app.route("/categories", methods=["GET"])
def get_categories():
    categories_ref = db.collection("categories").get()
    categories = [category.to_dict() for category in categories_ref]
    return jsonify(categories), 200

# Ruta para obtener detalles de un libro específico
@app.route("/books/<book_id>", methods=["GET"])
def get_book_details(book_id):
    book_ref = db.collection("books").document(book_id).get()
    if book_ref.exists:
        return jsonify(book_ref.to_dict()), 200
    return jsonify({"error": "Libro no encontrado"}), 404

# Ruta para descargar un libro (esto puede ser una URL de descarga o un archivo que subas)
@app.route("/books/<book_id>/download", methods=["GET"])
def download_book(book_id):
    book_ref = db.collection("books").document(book_id).get()
    if book_ref.exists:
        book = book_ref.to_dict()
        # Suponiendo que cada libro tiene un enlace de descarga en el campo 'download_link'
        return jsonify({"download_link": book.get("download_link")}), 200
    return jsonify({"error": "Libro no encontrado"}), 404

# Iniciar el servidor en la nube
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
