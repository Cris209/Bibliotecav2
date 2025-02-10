from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

# Inicializar Firebase
cred = credentials.Certificate("serviceAccountKey.json")
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
    field = request.args.get("field")  # Puede ser 'author', 'category', 'publisher' o 'title'
    value = request.args.get("value")

    if not field or not value:
        return jsonify({"error": "Faltan parámetros"}), 400

    books_ref = db.collection("books").where(field, "==", value).get()
    books = [book.to_dict() for book in books_ref]
    return jsonify(books), 200

# Ruta para obtener los libros más populares
@app.route("/books/popular", methods=["GET"])
def get_popular_books():
    popular_books = db.collection("books").order_by("popularity", direction=firestore.Query.DESCENDING).limit(5).get()
    books = [book.to_dict() for book in popular_books]
    return jsonify(books), 200

# Iniciar el servidor en la nube
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

