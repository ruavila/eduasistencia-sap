import sys
import os
import streamlit as st
import pandas as pd
from PIL import Image

# Asegurar que encuentre la carpeta modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from modules.database import init_db, get_connection
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login, registrar_usuario

# Configuración de página
st.set_page_config(page_title=APP_NAME, layout="wide")

# Inicializar Base de Datos
try:
    init_db()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")

# --- CABECERA ---
col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
with col2:
    st.title(APP_NAME)
    st.write(f"**{COLEGIO}** | Docente: {CREADOR}")

st.divider()

# --- LÓGICA DE ACCESO ---
if 'usuario_logueado' not in st.session_state:
    st.session_state.usuario_logueado = None

if st.session_state.usuario_logueado is None:
    st.header("🔑 Acceso al Sistema")
    tab_login, tab_registro = st.tabs(["📧 Iniciar Sesión", "📝 Registrarse"])

    with tab_login:
        u_ingreso = st.text_input("Usuario", key="login_u")
        p_ingreso = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar", type="primary"):
            datos_docente = check_login(u_ingreso, p_ingreso)
            if datos_docente:
                st.session_state.usuario_logueado = u_ingreso
                st.session_state.nombre_profe = datos_docente[0]
                st.rerun()
            else:
                st.error("Usuario o clave incorrectos.")

    with tab_registro:
        st.subheader("Crear nueva cuenta docente")
        reg_nom = st.text_input("Nombre Completo", key="reg_n")
        reg_usr = st.text_input("Nombre de Usuario (ID)", key="reg_u")
        reg_pas = st.text_input("Contraseña", type="password", key="reg_p")
        reg_con = st.text_input("Confirmar Contraseña", type="password", key="reg_c")
        
        if st.button("Finalizar Registro", key="reg_btn"):
            if reg_pas == reg_con and reg_usr and reg_nom:
                if registrar_usuario(reg_nom, reg_usr, reg_pas):
                    st.success("✅ ¡Registrado! Ahora puedes iniciar sesión.")
                else:
                    st.error("❌ El usuario ya existe.")
            else:
                st.warning("⚠️ Revisa que los campos no estén vacíos y las claves coincidan.")
    st.stop()

# --- PANEL TRAS EL LOGIN ---
st.sidebar.success(f"Bienvenido: {st.session_state.nombre_profe}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.usuario_logueado = None
    st.rerun()

menu = st.sidebar.selectbox("Menú", ["Mis Cursos", "Escanear QR", "Reportes"])
st.write(f"Has seleccionado: {menu}")