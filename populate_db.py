import firebase_admin
from firebase_admin import credentials, firestore

# Inicializar Firebase con el archivo de credenciales
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
books_ref = db.collection('books')

# Lista de libros de ejemplo
books = [
    {"title": "Cien años de soledad", "author": "Gabriel García Márquez", "category": "Novela", "editorial": "Sudamericana", "downloads": 500, "file_url": "https://ejemplo.com/cien.pdf"},
    {"title": "El principito", "author": "Antoine de Saint-Exupéry", "category": "Fantasía", "editorial": "Reynal & Hitchcock", "downloads": 600, "file_url": "https://ejemplo.com/principito.pdf"},
    {"title": "Don Quijote de la Mancha", "author": "Miguel de Cervantes", "category": "Clásico", "editorial": "Francisco de Robles", "downloads": 700, "file_url": "https://ejemplo.com/quijote.pdf"},
    {"title": "1984", "author": "George Orwell", "category": "Distopía", "editorial": "Secker & Warburg", "downloads": 800, "file_url": "https://ejemplo.com/1984.pdf"},
    {"title": "Fahrenheit 451", "author": "Ray Bradbury", "category": "Ciencia Ficción", "editorial": "Ballantine Books", "downloads": 550, "file_url": "https://ejemplo.com/fahrenheit.pdf"},
    {"title": "Crónica de una muerte anunciada", "author": "Gabriel García Márquez", "category": "Novela", "editorial": "Sudamericana", "downloads": 400, "file_url": "https://ejemplo.com/cronica.pdf"},
    {"title": "Los juegos del hambre", "author": "Suzanne Collins", "category": "Juvenil", "editorial": "Scholastic Press", "downloads": 950, "file_url": "https://ejemplo.com/hunger.pdf"},
    {"title": "El código Da Vinci", "author": "Dan Brown", "category": "Misterio", "editorial": "Doubleday", "downloads": 850, "file_url": "https://ejemplo.com/davinci.pdf"},
    {"title": "La sombra del viento", "author": "Carlos Ruiz Zafón", "category": "Novela", "editorial": "Planeta", "downloads": 900, "file_url": "https://ejemplo.com/sombra.pdf"},
    {"title": "Harry Potter y la piedra filosofal", "author": "J.K. Rowling", "category": "Fantasía", "editorial": "Bloomsbury", "downloads": 1200, "file_url": "https://ejemplo.com/harry.pdf"},
    {"title": "El Hobbit", "author": "J.R.R. Tolkien", "category": "Fantasía", "editorial": "George Allen & Unwin", "downloads": 1100, "file_url": "https://ejemplo.com/hobbit.pdf"},
    {"title": "Dune", "author": "Frank Herbert", "category": "Ciencia Ficción", "editorial": "Chilton Books", "downloads": 1050, "file_url": "https://ejemplo.com/dune.pdf"},
    {"title": "It", "author": "Stephen King", "category": "Terror", "editorial": "Viking", "downloads": 880, "file_url": "https://ejemplo.com/it.pdf"},
    {"title": "Orgullo y prejuicio", "author": "Jane Austen", "category": "Romance", "editorial": "T. Egerton", "downloads": 720, "file_url": "https://ejemplo.com/orgullo.pdf"},
    {"title": "Drácula", "author": "Bram Stoker", "category": "Terror", "editorial": "Archibald Constable and Company", "downloads": 730, "file_url": "https://ejemplo.com/dracula.pdf"},
    {"title": "Frankenstein", "author": "Mary Shelley", "category": "Terror", "editorial": "Lackington, Hughes, Harding, Mavor & Jones", "downloads": 690, "file_url": "https://ejemplo.com/frankenstein.pdf"},
    {"title": "Sherlock Holmes: Estudio en escarlata", "author": "Arthur Conan Doyle", "category": "Misterio", "editorial": "Ward, Lock & Co", "downloads": 750, "file_url": "https://ejemplo.com/sherlock.pdf"},
    {"title": "El nombre del viento", "author": "Patrick Rothfuss", "category": "Fantasía", "editorial": "DAW Books", "downloads": 950, "file_url": "https://ejemplo.com/viento.pdf"},
    {"title": "La carretera", "author": "Cormac McCarthy", "category": "Distopía", "editorial": "Alfred A. Knopf", "downloads": 680, "file_url": "https://ejemplo.com/carretera.pdf"},
    {"title": "Las ventajas de ser invisible", "author": "Stephen Chbosky", "category": "Juvenil", "editorial": "MTV Books", "downloads": 900, "file_url": "https://ejemplo.com/ventajas.pdf"}
]

# Agregar libros a Firestore
for book in books:
    books_ref.add(book)

print("📚 20 libros añadidos con éxito a Firebase Firestore.")
