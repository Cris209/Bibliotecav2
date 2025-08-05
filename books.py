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

# Configuración de Google Books API
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1"

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
                # Obtener Google Books API Key desde la misma configuración
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

@app.route('/api/usuario/<uid>', methods=['GET'])
def obtener_usuario(uid):
    try:
        user_doc = db.collection("usuarios").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return jsonify(user_data), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener datos del usuario: {str(e)}"}), 500

# Endpoint para buscar libros con un término específico
@app.route('/api/buscar_libros', methods=['GET'])
def buscar_libros():
    query = request.args.get('query', type=str)
    if not query:
        return jsonify({"error": "El parámetro 'query' es obligatorio."}), 400
    
    params = {
        'q': query,
        'maxResults': 10,
        'langRestrict': 'es',
        'filter': 'paid-ebooks',
        'key': GOOGLE_BOOKS_API_KEY
    }
    
    response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes", params=params)
    
    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos de Google Books API"}), 500
    
    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        volume_info = item.get('volumeInfo', {})
        imagen = volume_info.get('imageLinks', {}).get('thumbnail', '').replace('http://', 'https://') if 'imageLinks' in volume_info else ''
        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"

        
        libro = {
            "id": item.get('id', ''),
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'No disponible'),
            "imagen": imagen,
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": 'pdf' in item.get('accessInfo', {}).get('epub', {}).get('downloadLink', '') or 
                                      'pdf' in item.get('accessInfo', {}).get('pdf', {}).get('downloadLink', '')
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})

# Endpoint para mostrar 10 libros predeterminados
@app.route('/api/libros', methods=['GET'])
def mostrar_10_libros():
    params = {
        'q': 'fiction',
        'maxResults': 10,
        'langRestrict': 'es', 
        'filter': 'paid-ebooks',
        'key': GOOGLE_BOOKS_API_KEY
    }

    response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes", params=params)

   if response.status_code != 200:
    return jsonify({
        "error": "Error al obtener datos de Google Books API",
        "detalle": response.text,
        "status_code": response.status_code
    }), 500

    libros = response.json()
    resultados = []
    for item in libros.get('items', []):
        volume_info = item.get('volumeInfo', {})
        imagen = volume_info.get('imageLinks', {}).get('thumbnail', '').replace('http://', 'https://') if 'imageLinks' in volume_info else ''
        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"
        
        libro = {
            "id": item.get('id', ''),
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'No disponible'),
            "imagen": imagen,
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": 'pdf' in item.get('accessInfo', {}).get('epub', {}).get('downloadLink', '') or 
                                      'pdf' in item.get('accessInfo', {}).get('pdf', {}).get('downloadLink', '')
        }
        resultados.append(libro)

    return jsonify({"resultados": resultados})
    
# Endpoint para obtener detalles de un libro específico
@app.route('/api/libros/<id>', methods=['GET'])
def obtener_libro(id):
    try:
        response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes/{id}?key={GOOGLE_BOOKS_API_KEY}")
        response.raise_for_status()
        
        item = response.json()
        volume_info = item.get('volumeInfo', {})
        access_info = item.get('accessInfo', {})

        sale_info = item.get('saleInfo', {})
        retail_price = sale_info.get('retailPrice')
        saleability = sale_info.get('saleability', 'NOT_FOR_SALE')

        if saleability == 'FOR_SALE' and retail_price:
            amount = retail_price.get('amount', 'No disponible')
            currency = retail_price.get('currencyCode', '')
            precio = f"{amount} {currency}"
        elif saleability == 'FREE':
            precio = "Gratis"
        else:
            precio = "No disponible"
        
        # Procesar información de la imagen
        image_links = volume_info.get('imageLinks', {})
        imagen = image_links.get('thumbnail', '').replace('http://', 'https://')
        if not imagen and 'smallThumbnail' in image_links:
            imagen = image_links['smallThumbnail'].replace('http://', 'https://')
        
        libro = {
            "id": id,
            "titulo": volume_info.get('title', 'Título no disponible'),
            "autores": volume_info.get('authors', []),
            "descripcion": volume_info.get('description', 'Descripción no disponible'),
            "imagen": imagen,
            "fecha_publicacion": volume_info.get('publishedDate', ''),
            "editorial": volume_info.get('publisher', ''),
            "paginas": volume_info.get('pageCount', 0),
            "categorias": volume_info.get('categories', []),
            "link": volume_info.get('infoLink', ''),
            "precio": precio,
            "disponible_para_descarga": access_info.get('pdf', {}).get('isAvailable', False) or 
                                        access_info.get('epub', {}).get('isAvailable', False),
            "download_links": {
                "pdf": access_info.get('pdf', {}).get('downloadLink', ''),
                "epub": access_info.get('epub', {}).get('downloadLink', '')
            }
        }
        
        return jsonify(libro)
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener detalles del libro: {str(e)}"}), 500

@app.route('/api/libros/<id>/disponibilidad', methods=['GET'])
def verificar_disponibilidad_descarga(id):
    try:
        response = requests.get(f"{GOOGLE_BOOKS_API_URL}/volumes/{id}?key={GOOGLE_BOOKS_API_KEY}")
        response.raise_for_status()
        
        item = response.json()
        access_info = item.get('accessInfo', {})
        
        pdf_available = access_info.get('pdf', {}).get('isAvailable', False)
        epub_available = access_info.get('epub', {}).get('isAvailable', False)
        
        disponible = pdf_available or epub_available
        
        if disponible:
            return jsonify({
                "disponible": True,
                "formato": "PDF" if pdf_available else "EPUB",
                "download_link": access_info.get('pdf', {}).get('downloadLink', '') if pdf_available else 
                               access_info.get('epub', {}).get('downloadLink', ''),
                "mensaje": "Disponible para descarga"
            })
        else:
            return jsonify({
                "disponible": False,
                "mensaje": "Este libro no está disponible para descarga"
            })
        
    except Exception as e:
        return jsonify({
            "error": f"Error al verificar disponibilidad: {str(e)}",
            "disponible": False
        }), 500

# -----------------------------
# ADMIN ENDPOINTS
# -----------------------------

@app.route('/api/admin/libros', methods=['POST'])
def agregar_libro():
    data = request.get_json()
    
    # Verificar si el usuario es admin (esto debería implementarse con autenticación real)
    # Por ahora, asumimos que es admin si se llama desde el frontend admin
    
    try:
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
        
        # Guardar en Firestore
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
        return jsonify({"mensaje": "Libro agregado exitosamente", "libro": response_data}), 201
    except Exception as e:
        return jsonify({"error": f"Error al agregar libro: {str(e)}"}), 500

@app.route('/api/admin/libros/<id>', methods=['DELETE'])
def eliminar_libro(id):
    try:
        # Eliminar de Firestore
        db.collection("libros_admin").document(id).delete()
        
        return jsonify({"mensaje": "Libro eliminado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar libro: {str(e)}"}), 500

@app.route('/api/admin/libros', methods=['GET'])
def obtener_libros_admin():
    try:
        libros_ref = db.collection("libros_admin").stream()
        libros = []
        for libro in libros_ref:
            libros.append(libro.to_dict())
        
        return jsonify({"libros": libros}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener libros: {str(e)}"}), 500

# Ejecutar la app en el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
