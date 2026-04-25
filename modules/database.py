import sqlite3
import hashlib
import os

def get_connection():
    """Establece la conexión con la base de datos local."""
    if not os.path.exists("data"):
        os.makedirs("data")
    return sqlite3.connect("data/asistencia.db", check_same_thread=False)

def hash_password(password):
    """Encripta las contraseñas para seguridad de los docentes."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Crea la estructura de tablas completa si no existe."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios (Docentes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            password TEXT,
            nombre TEXT
        )
    """)
    
    # Tabla de Cursos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grado TEXT,
            materia TEXT,
            profe_id TEXT
        )
    """)
    
    # Tabla de Estudiantes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estudiantes (
            documento TEXT PRIMARY KEY,
            nombre TEXT,
            whatsapp TEXT,
            grado TEXT,
            materia TEXT,
            profe_id TEXT
        )
    """)
    
    # Tabla de Asistencia
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id TEXT,
            fecha TEXT,
            hora TEXT,
            grado TEXT,
            materia TEXT,
            tema TEXT,
            profe_id TEXT
        )
    """)
    
    conn.commit()
    conn.close()
