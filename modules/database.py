import sqlite3
import hashlib
import os

def get_connection():
    """Establece conexión asegurando que la carpeta 'data' exista."""
    if not os.path.exists("data"):
        os.makedirs("data")
    return sqlite3.connect("data/asistencia.db", check_same_thread=False)

def hash_password(password):
    """Encripta las contraseñas para seguridad del docente."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Inicializa todas las tablas del sistema EduAsistencia Pro."""
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
    
    # Tabla de Asistencia (Estructura completa para evitar errores en reportes)
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

def maintenance_mode():
    """Función para actualizar bases de datos antiguas sin perder datos."""
    conn = get_connection()
    cursor = conn.cursor()
    # Intenta añadir columnas nuevas si el docente actualiza desde una versión vieja
    columnas_nuevas = [("asistencia", "tema"), ("asistencia", "profe_id")]
    for tabla, columna in columnas_nuevas:
        try:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} TEXT")
        except:
            pass 
    conn.commit()
    conn.close()
