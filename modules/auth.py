import sqlite3
from modules.database import get_connection

def check_login(usuario, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Buscamos nombre del docente
        cursor.execute("SELECT nombre FROM usuarios WHERE usuario = ? AND password = ?", (usuario, password))
        resultado = cursor.fetchone()
        conn.close()
        return resultado
    except Exception as e:
        print(f"Error en login: {e}")
        return None

def registrar_usuario(nombre, usuario, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si ya existe
        cursor.execute("SELECT usuario FROM usuarios WHERE usuario = ?", (usuario,))
        if cursor.fetchone():
            conn.close()
            return False
        
        # Insertar (Nota: sin hash_password para que coincida con tu database.py)
        cursor.execute(
            "INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'Docente')",
            (nombre, usuario, password)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error en registro: {e}")
        return False