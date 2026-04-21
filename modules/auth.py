# modules/auth.py
import streamlit as st
from modules.database import get_connection, hash_password

def check_login(username, password):
    conn = get_connection()
    password_hash = hash_password(password)
    res = conn.execute(
        "SELECT nombre_completo FROM profesores WHERE username=? AND password_hash=?", 
        (username, password_hash)
    ).fetchone()
    return res