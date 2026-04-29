import streamlit as st
from supabase import create_client, Client
import hashlib

# Conexión con las llaves de Streamlit Secrets
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Error en credenciales. Verifica los Secrets.")
    st.stop()

def get_connection():
    return supabase

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    pass
