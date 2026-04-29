import streamlit as st
from supabase import create_client, Client
import hashlib

# --- CONEXIÓN CON SUPABASE ---
# st.secrets busca automáticamente las llaves que pegaste en el panel de Streamlit Cloud
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    # Creamos el cliente de conexión a la nube
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Error al leer las credenciales de Supabase. Verifica los Secrets en Streamlit Cloud.")
    st.stop()

def get_connection():
    """
    Retorna el cliente de Supabase. 
    A diferencia de SQLite, aquí no retornamos una conexión de archivo,
    sino el objeto cliente para interactuar con la API de Supabase.
    """
    return supabase

def hash_password(password):
    """
    Encripta las contraseñas usando SHA-256 para que no sean 
    visibles en texto plano en la base de datos.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """
    En la arquitectura de Supabase, las tablas se crean desde el panel web 
    (SQL Editor) para mayor eficiencia y seguridad. 
    Esta función queda vacía para mantener compatibilidad con el resto del código.
    """
    pass

# Exponemos el cliente directamente para facilitar su uso en app.py
db = supabase
    conn.close()
