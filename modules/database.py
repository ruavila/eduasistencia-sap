import sqlite3
import hashlib

DB_NAME = "asistencia.db"

def hash_password(password):
    """Crea un hash seguro para la contraseña."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_connection():
    """Establece conexión con la base de datos SQLite."""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, usuario TEXT UNIQUE, password TEXT, rol TEXT)''')
    
    # Tabla de Cursos
    cursor.execute('''CREATE TABLE IF NOT EXISTS cursos 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, grado TEXT, materia TEXT, profesor_id TEXT)''')
    
    # Tabla de Estudiantes
    cursor.execute('''CREATE TABLE IF NOT EXISTS estudiantes 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, documento TEXT UNIQUE, nombre TEXT, grado TEXT, profesor_id TEXT)''')
    
    conn.commit()
    conn.close()
