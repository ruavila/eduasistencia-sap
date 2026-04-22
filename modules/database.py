import sqlite3
import os

DB_NAME = "asistencia.db"

def get_connection():
    """Establece conexión con la base de datos SQLite."""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabla de Usuarios (Docentes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')

    # 2. Tabla de Cursos (Nueva funcionalidad)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grado TEXT NOT NULL,
            materia TEXT NOT NULL,
            profesor_id TEXT NOT NULL,
            UNIQUE(grado, materia, profesor_id)
        )
    ''')

    # 3. Tabla de Estudiantes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudiantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            grado TEXT NOT NULL,
            profesor_id TEXT NOT NULL
        )
    ''')

    # 4. Tabla de Asistencia
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            materia TEXT NOT NULL,
            profesor_id TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
