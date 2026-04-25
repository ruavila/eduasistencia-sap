import sqlite3
import hashlib
import os

def get_connection():
    """Establece la conexión con la base de datos asegurando que la carpeta exista."""
    if not os.path.exists("data"):
        os.makedirs("data")
    return sqlite3.connect("data/asistencia.db", check_same_thread=False)

def hash_password(password):
    """Encripta las contraseñas para seguridad de los docentes."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. TABLA DE DOCENTES (USUARIOS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            password TEXT,
            nombre TEXT
        )
    """)
    
    # 2. TABLA DE CURSOS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grado TEXT,
            materia TEXT,
            profe_id TEXT
        )
    """)
    
    # 3. TABLA DE ESTUDIANTES
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
    
    # 4. TABLA DE ASISTENCIA (Estructura completa para reportes)
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

# --- Bloque de mantenimiento opcional (para corregir errores de versiones previas) ---
def check_db_maintenance():
    """Asegura que si la base de datos es antigua, se añadan las columnas faltantes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Intenta añadir 'tema' si el usuario viene de una versión vieja
        cursor.execute("ALTER TABLE asistencia ADD COLUMN tema TEXT")
    except:
        pass # Si ya existe, no hace nada
    conn.commit()
    conn.close()
