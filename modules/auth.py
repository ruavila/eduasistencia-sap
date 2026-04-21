# modules/auth.py
import streamlit as st
from modules.database import get_connection
from modules.utils import hash_password

def login():
    st.header("🔑 Acceso al Sistema")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])

    with tab1:
        username = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar", type="primary"):
            if username and password:
                password_hash = hash_password(password)
                conn = get_connection()
                res = conn.execute("SELECT nombre_completo FROM profesores WHERE username=? AND password_hash=?", 
                                  (username, password_hash)).fetchone()
                if res:
                    st.session_state.profesor_actual = username
                    st.session_state.nombre_docente = res[0]
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

    with tab2:
        nuevo_user = st.text_input("Usuario", key="reg_user")
        nuevo_nombre = st.text_input("Nombre completo", key="reg_nombre")
        nueva_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("Registrarse", type="primary"):
            if nuevo_user and nuevo_nombre and nueva_pass:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO profesores VALUES (?, ?, ?)", 
                                (nuevo_user.strip(), hash_password(nueva_pass), nuevo_nombre.strip()))
                    conn.commit()
                    st.success("Registro exitoso. Ahora inicia sesión.")
                except:
                    st.error("Ese usuario ya existe")