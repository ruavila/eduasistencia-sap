import sqlite3
import hashlib

def get_connection():
    # Establece conexión con la base de datos local
    return sqlite3.connect("data/asistencia.db", check_same_thread=False)

def hash_password(password):
    # Encriptación simple para seguridad de acceso
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
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
    
    # Tabla de Estudiantes (Asegurando documento como texto y sin error de ID)
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
    
    # Tabla de Asistencia (Incluyendo la columna TEMA desde el inicio)
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
    
    # Usuario por defecto si la tabla está vacía
    cursor.execute("SELECT * FROM usuarios")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?)", 
                       ("admin", hash_password("1234"), "Profesor Administrador"))
    
    conn.commit()
    conn.close()
