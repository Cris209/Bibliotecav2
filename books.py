from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os
import bcrypt
from threading import Lock
from functools import wraps

# --- NUEVAS LIBRERÍAS DE SEGURIDAD ---
from cryptography.fernet import Fernet
import jwt

app = Flask(__name__)
CORS(app)

# -----------------------------
# CONFIGURACIÓN DE SEGURIDAD
# -----------------------------
# Carga la clave de encriptación desde la variable de entorno de Render
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY no está configurada. Asegúrate de añadirla en Render.")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# Carga la clave secreta para JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY no está configurada. Asegúrate de añadirla en Render.")

# Configuración de Google Books API
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1"

# -----------------------------
# PATRÓN SINGLETON: FirebaseManager
# -----------------------------
# (El código del Singleton se mantiene igual)
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
                cls._instance.google_books_api_key = service_account_info.get("GOOGLE_BOOKS_API_KEY") or os.getenv("GOOGLE_BOOKS_API_KEY")
        return cls._instance

firebase_manager = FirebaseManager()
db = firebase_manager.db
GOOGLE_BOOKS_API_KEY = firebase_manager.google_books_api_key

# -----------------------------
# PATRÓN FACTORY METHOD: UserFactory
# -----------------------------
# (El código de las clases Usuario y UserFactory se mantiene igual)
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
# Encriptación: bcrypt y Fernet
# -----------------------------
def encriptar_contraseña(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_contraseña(password_enviada, password_hash):
    return bcrypt.checkpw(password_enviada.encode('utf-8'), password_hash.encode('utf-8'))

def encriptar_payload(data):
    """Encripta un diccionario de datos a una cadena"""
    json_data = json.dumps(data)
    return cipher_suite.encrypt(json_data.encode('utf-8')).decode('utf-8')

# -----------------------------
# Decorador para JWT
# -----------------------------
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({"error": "Token de autenticación faltante o inválido"}), 401
        
        token = token.split(' ')[1]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            request.uid = payload['uid']
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# RUTAS MEJORADAS
# -----------------------------

@app.route('/api/registrarse', methods=['POST'])
def registrarse():
    # ... (código se mantiene casi igual, se añade JWT)
    data = request.get_json()
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    gmail = data.get('gmail')
    password = data.get('password')
    tipo_usuario = data.get('tipo', 'normal')

    if not nombre or not apellido or not gmail or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400
    if not gmail.endswith("@gmail.com"):
        return jsonify({"error": "El correo debe ser un Gmail válido (ejemplo@gmail.com)."}), 400

    try:
        usuario = UserFactory.crear_usuario(tipo_usuario, gmail, password)
        password_encriptada_bcrypt = encriptar_contraseña(usuario.password)
        
        user = auth.create_user(email=usuario.email, password=usuario.password)
        
        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre,
            "apellido": apellido,
            "email": usuario.email,
            "rol": usuario.rol,
            "password_hash": password_encriptada_bcrypt
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
        user_doc = db.collection("usuarios").where("email", "==", email).limit(1).get()
        if not user_doc:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        user_data = user_doc[0].to_dict()
        user_id = user_doc[0].id
        
        # VERIFICAR LA CONTRASEÑA ENCRIPTADA
        if not verificar_contraseña(password, user_data.get('password_hash')):
            return jsonify({"error": "Contraseña incorrecta"}), 401
            
        # Generar JWT
        payload = {'uid': user_id, 'rol': user_data['rol']}
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
        
        return jsonify({"mensaje": "Inicio de sesión exitoso", "token": token}), 200

    except Exception as e:
        return jsonify({"error": f"Error al iniciar sesión: {str(e)}"}), 500

@app.route('/api/usuario/<uid>', methods=['GET'])
@jwt_required
def obtener_usuario(uid):
    if request.uid != uid:
        return jsonify({"error": "Acceso no autorizado"}), 403
    try:
        user_doc = db.collection("usuarios").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            del user_data['password_hash'] # No enviar el hash de la contraseña
            
            # ENCRIPTAR LOS DATOS DEL USUARIO
            encrypted_data = encriptar_payload(user_data)
            
            return jsonify({"payload": encrypted_data}), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener datos del usuario: {str(e)}"}), 500

# Endpoint para buscar libros (no se encripta, es información pública)
@app.route('/api/buscar_libros', methods=['GET'])
def buscar_libros():
    # ... (código se mantiene igual)
    query = request.args.get('query', type=str)
    if not query:
        return jsonify({"error": "El parámetro 'query' es obligatorio."}), 400
    
    params = {
        'q': query,
        'maxResults': 10,
        'langRestrict': 'es',
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

# Endpoint para mostrar 10 libros predeterminados (no se encripta)
@app.route('/api/libros', methods=['GET'])
def mostrar_10_libros():
    # ... (código se mantiene igual)
    params = {
        'q': 'fiction',
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
    
# ... (El resto de los endpoints de libros se mantienen igual)
@app.route('/api/libros/<id>', methods=['GET'])
def obtener_libro(id):
    # ... (código se mantiene igual)
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
    # ... (código se mantiene igual)
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
            return jsonify({"disponible": False,"mensaje": "Este libro no está disponible para descarga"})
    except Exception as e:
        return jsonify({"error": f"Error al verificar disponibilidad: {str(e)}", "disponible": False}), 500

# -----------------------------
# ADMIN ENDPOINTS PROTEGIDOS CON JWT
# -----------------------------

@app.route('/api/admin/libros', methods=['POST'])
@jwt_required
def agregar_libro():
    # ... (código se mantiene casi igual, se añade la verificación de rol)
    try:
        user_doc = db.collection("usuarios").document(request.uid).get()
        if user_doc.exists and user_doc.to_dict().get('rol') != 'admin':
            return jsonify({"error": "Acceso no autorizado: Solo para administradores"}), 403
            
        data = request.get_json()
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
@jwt_required
def eliminar_libro(id):
    # ... (código se mantiene casi igual, se añade la verificación de rol)
    try:
        user_doc = db.collection("usuarios").document(request.uid).get()
        if user_doc.exists and user_doc.to_dict().get('rol') != 'admin':
            return jsonify({"error": "Acceso no autorizado: Solo para administradores"}), 403
            
        db.collection("libros_admin").document(id).delete()
        return jsonify({"mensaje": "Libro eliminado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar libro: {str(e)}"}), 500

@app.route('/api/admin/libros', methods=['GET'])
@jwt_required
def obtener_libros_admin():
    # ... (código se mantiene casi igual, se añade la verificación de rol)
    try:
        user_doc = db.collection("usuarios").document(request.uid).get()
        if user_doc.exists and user_doc.to_dict().get('rol') != 'admin':
            return jsonify({"error": "Acceso no autorizado: Solo para administradores"}), 403
            
        libros_ref = db.collection("libros_admin").stream()
        libros = []
        for libro in libros_ref:
            libros.append(libro.to_dict())
        return jsonify({"libros": libros}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener libros: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
