import sys
import os
import streamlit as st
import pandas as pd
from PIL import Image

# Asegurar que encuentre la carpeta 'modules'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from modules.database import init_db, get_connection
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login, registrar_usuario

# Configuración inicial
st.set_page_config(page_title=APP_NAME, layout="wide")

# Inicializar DB
try:
    init_db()
except Exception as e:
    st.error(f"Error de base de datos: {e}")

# --- Cabecera ---
col_escudo, col_titulo = st.columns([1, 4])
with col_escudo:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)

with col_titulo:
    st.markdown(f"<h1 style='color:#1E3A8A; margin-bottom:0;'>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:1.1em;'>{COLEGIO} | <b>Docente: {CREADOR}</b></p>", unsafe_allow_html=True)

st.divider()

# --- Lógica de Acceso ---
if 'usuario_logueado' not in st.session_state:
    st.session_state.usuario_logueado = None
    st.session_state.nombre_profe = None

if st.session_state.usuario_logueado is None:
    st.header("🔑 Acceso al Sistema")
    tab_login, tab_registro = st.tabs(["📧 Iniciar Sesión", "📝 Registrarse"])

    with tab_login:
        u_ing = st.text_input("Usuario", key="l_u")
        p_ing = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Entrar", type="primary"):
            datos = check_login(u_ing, p_ing)
            if datos:
                st.session_state.usuario_logueado = u_ing
                st.session_state.nombre_profe = datos[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")

    with tab_registro:
        st.subheader("Crear nueva cuenta docente")
        r_nom = st.text_input("Nombre Completo", key="r_n")
        r_usr = st.text_input("Nombre de Usuario", key="r_u")
        r_pas = st.text_input("Contraseña", type="password", key="r_p")
        r_con = st.text_input("Confirmar Contraseña", type="password", key="r_c")
        if st.button("Finalizar Registro"):
            if r_pas == r_con and r_usr and r_nom:
                if registrar_usuario(r_nom, r_usr, r_pas):
                    st.success("✅ Registrado con éxito. Ya puedes iniciar sesión.")
                else:
                    st.error("El usuario ya existe.")
            else:
                st.warning("Completa todos los campos correctamente.")
    st.stop()

# --- Panel Principal ---
st.sidebar.success(f"Sesión: {st.session_state.nombre_profe}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.usuario_logueado = None
    st.rerun()

menu = st.sidebar.selectbox("Menú", ["Mis Cursos", "Gestionar Estudiantes", "Escanear Asistencia", "Reportes"])

if menu == "Mis Cursos":
    st.header("📚 Gestión de Cursos")
    
    # Formulario para agregar
    with st.expander("➕ Registrar Nuevo Curso"):
        with st.form("form_curso"):
            g = st.text_input("Grado (ej: 601)")
            m = st.text_input("Materia")
            if st.form_submit_button("Guardar Curso"):
                if g and m:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO cursos (grado, materia, profesor_id) VALUES (?, ?, ?)", 
                                       (g, m, st.session_state.usuario_logueado))
                        conn.commit()
                        st.success("Curso guardado.")
                        st.rerun()
                    except:
                        st.error("Error: Curso ya registrado.")
    
    st.divider()
    
    # Lista dinámica con opción de eliminar
    st.subheader("📋 Lista de Cursos")
    conn = get_connection()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profesor_id=?", 
                       conn, params=(st.session_state.usuario_logueado,))
    
    if df_c.empty:
        st.info("No hay cursos registrados.")
    else:
        for idx, row in df_c.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**Grado:** {row['grado']}")
            c2.write(f"**Materia:** {row['materia']}")
            if c3.button("🗑️ Eliminar", key=f"del_{row['id']}"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cursos WHERE id=?", (row['id'],))
                conn.commit()
                st.rerun()
            st.markdown("---")

elif menu == "Gestionar Estudiantes":
    st.header("👤 Estudiantes")
    # Lógica similar para estudiantes...
    st.info("Usa esta sección para vincular alumnos a tus grados registrados.")

elif menu == "Escanear Asistencia":
    st.header("📷 Escáner QR")
    st.camera_input("Capturar QR")

elif menu == "Reportes":
    st.header("📊 Reportes")
    st.write("Visualiza la asistencia histórica aquí.")
