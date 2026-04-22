import sqlite3
import hashlib

DB_NAME = "asistencia_escolar.db"

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Usuarios (Profesores)
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, password TEXT)')
    # Cursos
    cursor.execute('CREATE TABLE IF NOT EXISTS cursos (id INTEGER PRIMARY KEY, grado TEXT, materia TEXT, profe_id TEXT)')
    # Estudiantes
    cursor.execute('CREATE TABLE IF NOT EXISTS estudiantes (id INTEGER PRIMARY KEY, documento TEXT, nombre TEXT, whatsapp TEXT, grado TEXT, materia TEXT, profe_id TEXT)')
    # Asistencia (Registro de cada sesión)
    cursor.execute('CREATE TABLE IF NOT EXISTS asistencia (id INTEGER PRIMARY KEY, estudiante_id TEXT, fecha TEXT, estado TEXT, materia TEXT, grado TEXT, profe_id TEXT)')
    conn.commit()
    conn.close()
