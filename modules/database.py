import sqlite3
import hashlib

def get_connection():
    # check_same_thread=False es vital para que Streamlit no de errores de conexión 
    return sqlite3.connect("asistencia.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    # Creamos todas las tablas que definiste originalmente 
    queries = [
        "CREATE TABLE IF NOT EXISTS profesores (username TEXT PRIMARY KEY, password_hash TEXT, nombre_completo TEXT)",
        "CREATE TABLE IF NOT EXISTS docentes_cursos (profesor TEXT, grado TEXT, materia TEXT, PRIMARY KEY (profesor, grado, materia))",
        "CREATE TABLE IF NOT EXISTS estudiantes (profesor TEXT, grado TEXT, materia TEXT, estudiante_id TEXT, nombre TEXT, PRIMARY KEY (profesor, grado, materia, estudiante_id))",
        "CREATE TABLE IF NOT EXISTS asistencias (profesor TEXT, grado TEXT, materia TEXT, estudiante_id TEXT, fecha TEXT, hora_registro TEXT, PRIMARY KEY (profesor, grado, materia, estudiante_id, fecha))"
    ]
    for q in queries:
        conn.execute(q)
    conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()