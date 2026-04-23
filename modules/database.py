import sqlite3
import hashlib

def get_connection():
    return sqlite3.connect('asistencia_escolar.db', check_same_thread=False)

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Usuarios/Docentes
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
                        profe_id TEXT NOT NULL)''')
    # Estudiantes
    cursor.execute('''CREATE TABLE IF NOT EXISTS estudiantes (
                        documento TEXT PRIMARY KEY,
                        nombre TEXT NOT NULL,
                        whatsapp TEXT,
                        grado TEXT NOT NULL,
                        materia TEXT NOT NULL,
                        profe_id TEXT NOT NULL)''')
    # Asistencia
    cursor.execute('''CREATE TABLE IF NOT EXISTS asistencia (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estudiante_id TEXT NOT NULL,
                        fecha TEXT NOT NULL,
                        hora TEXT NOT NULL,
                        grado TEXT NOT NULL,
                        materia TEXT NOT NULL,
                        profe_id TEXT NOT NULL)''')
    conn.commit()
    conn.close()
