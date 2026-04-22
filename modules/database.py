import sqlite3
import os

# Nombre del archivo de la base de datos
DB_NAME = "asistencia.db"

def get_connection():
    """Establece conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabla de Usuarios (Docentes)
    # El campo 'usuario' es UNIQUE para evitar duplicados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')

    # 2. Tabla de Estudiantes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudiantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            grado TEXT NOT NULL,
            profesor_id TEXT,
            FOREIGN KEY (profesor_id) REFERENCES usuarios (usuario)
        )
    ''')

    # 3. Tabla de Registro de Asistencia
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            materia TEXT NOT NULL,
            profesor_id TEXT NOT NULL,
            FOREIGN KEY (estudiante_id) REFERENCES estudiantes (documento)
        )
    ''')

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

# Al importar este módulo, intentará crear el archivo si no existe
if __name__ == "__main__":
    init_db()