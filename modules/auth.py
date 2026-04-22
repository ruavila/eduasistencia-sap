from modules.database import get_connection, hash_password

def check_login(usuario, password):
    conn = get_connection()
    cursor = conn.cursor()
    h_pass = hash_password(password)
    cursor.execute("SELECT nombre FROM usuarios WHERE usuario = ? AND password = ?", (usuario, h_pass))
    result = cursor.fetchone()
    conn.close()
    return result

def registrar_usuario(nombre, usuario, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        h_pass = hash_password(password)
        cursor.execute("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, ?)", 
                       (nombre, usuario, h_pass, 'docente'))
        conn.commit()
        conn.close()
        return True
    except:
        return False
