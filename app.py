import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode

# Importamos tus propios módulos
from modules.database import init_db, get_connection
from modules.utils import generar_qr, abreviar_nombre
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login

# ====================== CONFIGURACIÓN INICIAL ======================
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()
conn = get_connection()

# ====================== CABECERA (UI) ======================
col_escudo, col_titulo = st.columns([1, 4])
with col_escudo:
    try:
        escudo = Image.open(ESCUDO_PATH)
        st.image(escudo, width=130)
    except:
        st.warning("No se encontró el escudo en assets/")

with col_titulo:
    st.markdown(f"""
        <h1 style='margin-bottom:0; color:#1E3A8A;'>{APP_NAME}</h1>
        <h3 style='margin-top:5px; color:#334155;'>{APP_SUBTITLE}</h3>
        <p style='color:#64748B; font-size:1.05em;'>{COLEGIO} • Creado por {CREADOR}</p>
    """, unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ====================== LÓGICA DE SESIÓN ======================
if 'profesor_actual' not in st.session_state:
    st.session_state.profesor_actual = None
    st.session_state.nombre_docente = None

if st.session_state.profesor_actual is None:
    st.header("🔑 Acceso al Sistema")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])

    with tab1:
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", type="primary"):
            res = check_login(user, pw) # Usamos nuestra función de auth.py
            if res:
                st.session_state.profesor_actual = user
                st.session_state.nombre_docente = res[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop() # Detiene la ejecución si no está logueado

# ====================== PANEL PRINCIPAL ======================
profesor = st.session_state.profesor_actual
st.sidebar.success(f"✅ Docente: {st.session_state.nombre_docente}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.profesor_actual = None
    st.rerun()

menu = st.sidebar.selectbox("Menú:", [
    "1. Mis Cursos",
    "2. Gestionar Estudiantes",
    "3. Escanear Asistencia",
    "4. Reportes"
])

# Ejemplo rápido de cómo usar la DB modularizada en el menú
if menu == "1. Mis Cursos":
    st.header("📚 Mis Cursos")
    # Puedes seguir usando 'conn' directamente aquí o crear funciones en database.py
    df_cursos = pd.read_sql("SELECT grado, materia FROM docentes_cursos WHERE profesor=?", 
                            conn, params=(profesor,))
    st.dataframe(df_cursos, use_container_width=True)

# ... El resto de tus secciones siguen la misma lógica ...