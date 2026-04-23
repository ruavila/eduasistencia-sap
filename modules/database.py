import sqlite3
import hashlib

def get_connection():
    """Establece la conexión con la base de datos SQLite."""
    conn = sqlite3.connect('asistencia_escolar.db', check_same_thread=False)
    return conn

def hash_password(password):
    """Encripta la contraseña para mayor seguridad."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    """Inicializa la base de datos y crea las tablas necesarias."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Usuarios (Docentes)
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT NOT NULL,
                        usuario TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    
    # Cursos
    cursor.execute('''CREATE TABLE IF NOT EXISTS cursos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        grado TEXT NOT NULL,
                        materia TEXT NOT NULL,
                        profe_id TEXT NOT NULL,
                        FOREIGN KEY (profe_id) REFERENCES usuarios(usuario))''')
    
    # Estudiantes (Incluye WhatsApp)
    cursor.execute('''CREATE TABLE IF NOT EXISTS estudiantes (
                        documento TEXT PRIMARY KEY,
                        nombre TEXT NOT NULL,
                        whatsapp TEXT,
                        grado TEXT NOT NULL,
                        materia TEXT NOT NULL,
                        profe_id TEXT NOT NULL,
                        FOREIGN KEY (profe_id) REFERENCES usuarios(usuario))''')
    
    # Asistencia
    cursor.execute('''CREATE TABLE IF NOT EXISTS asistencia (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estudiante_id TEXT NOT NULL,
                        fecha TEXT NOT NULL,
                        hora TEXT NOT NULL,
                        grado TEXT NOT NULL,
                        materia TEXT NOT NULL,
                        profe_id TEXT NOT NULL,
                        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(documento),
                        FOREIGN KEY (profe_id) REFERENCES usuarios(usuario))''')
    
    conn.commit()
    conn.close()
