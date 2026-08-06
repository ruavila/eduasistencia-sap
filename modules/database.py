import streamlit as st
from supabase import create_client, Client
import hashlib

# Conexión con las llaves de Streamlit Secrets
try:
    url = "https://yzeqxltqpkgrrqcbagik.supabase.co"
    key = "sb_publishable_s4RmxZTJBxbRGMLNY3xQ2A_7OKqkUM7"
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
