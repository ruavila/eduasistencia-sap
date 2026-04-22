import sys
import os
import streamlit as st
import pandas as pd
from PIL import Image
import datetime

# Asegurar que Python encuentre la carpeta 'modules'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Importación de módulos propios
from modules.database import init_db, get_connection
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login, registrar_usuario

# ====================== CONFIGURACIÓN INICIAL ======================
st.set_page_config(page_title=APP_NAME, layout="wide")

# Inicializar base de datos al arrancar
try:
    init_db()
except Exception as e:
    st.error(f"Error de base de datos: {e}")

# ====================== CABECERA (UI) ======================
col_escudo, col_titulo = st.columns([1, 4])
with col_escudo:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)

with col_titulo:
    st.markdown(f"<h1 style='color:#1E3A8A; margin-bottom:0;'>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:1.2em;'>{COLEGIO} | <b>Docente: {CREADOR}</b></p>", unsafe_allow_html=True)

st.divider()

# ====================== LÓGICA DE ACCESO (LOGIN/REGISTRO) ======================
if 'usuario_logueado' not in st.session_state:
    st.session_state.usuario_logueado = None
    st.session_state.nombre_profe = None

if st.session_state.usuario_logueado is None:
    st.header("🔑 Acceso al Sistema")
    tab_login, tab_registro = st.tabs(["📧 Iniciar Sesión", "📝 Registrarse"])

    with tab_login:
        u_ingreso = st.text_input("Usuario", key="l_u")
        p_ingreso = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Entrar", type="primary"):
            datos = check_login(u_ingreso, p_ingreso)
            if datos:
                st.session_state.usuario_logueado = u_ingreso
                st.session_state.nombre_profe = datos[0]
                st.rerun()
            else:
                st.error("Usuario o clave incorrectos.")

    with tab_registro:
        st.subheader("Crear nueva cuenta docente")
        reg_nom = st.text_input("Nombre Completo", key="r_n")
        reg_usr = st.text_input("Nombre de Usuario (ID)", key="r_u")
        reg_pas = st.text_input("Contraseña", type="password", key="r_p")
        reg_con = st.text_input("Confirmar Contraseña", type="password", key="r_c")
        
        if st.button("Finalizar Registro", key="r_btn"):
            if reg_pas == reg_con and reg_usr and reg_nom:
                if registrar_usuario(reg_nom, reg_usr, reg_pas):
                    st.success("✅ ¡Registrado! Ahora puedes iniciar sesión en la otra pestaña.")
                else:
                    st.error("❌ El usuario ya existe.")
            else:
                st.warning("⚠️ Verifica los campos y que las claves coincidan.")
    st.stop()

# ====================== PANEL PRINCIPAL (POST-LOGIN) ======================
st.sidebar.success(f"Sesión activa: {st.session_state.nombre_profe}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.usuario_logueado = None
    st.rerun()

menu = st.sidebar.selectbox("Menú de Navegación", 
    ["Mis Cursos", "Gestionar Estudiantes", "Escanear Asistencia", "Reportes"])

# Conexión global para las secciones
conn = get_connection()

if menu == "Mis Cursos":
    st.header("📚 Mis Cursos y Grupos")
    with st.expander("➕ Configurar Nuevo Grado"):
        nuevo_g = st.text_input("Grado (ej: 601)")
        nueva_m = st.text_input("Materia")
        if st.button("Registrar Curso"):
            # Usamos la tabla estudiantes con un marcador especial o podrías crear una tabla 'cursos'
            st.info(f"Curso {nuevo_g} - {nueva_m} configurado para el sistema.")

elif menu == "Gestionar Estudiantes":
    st.header("👤 Gestión de Estudiantes")
    
    with st.form("form_estudiante"):
        c1, c2 = st.columns(2)
        with c1:
            nom_e = st.text_input("Nombre Completo")
            doc_e = st.text_input("Documento/ID")
        with c2:
            gra_e = st.text_input("Grado")
        
        if st.form_submit_button("Guardar Estudiante"):
            if nom_e and doc_e:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO estudiantes (nombre, documento, grado, profesor_id) VALUES (?, ?, ?, ?)",
                        (nom_e, doc_e, gra_e, st.session_state.usuario_logueado)
                    )
                    conn.commit()
                    st.success(f"✅ Estudiante {nom_e} guardado.")
                except:
                    st.error("Error: El documento ya está registrado.")
    
    st.divider()
    st.subheader("📋 Estudiantes Registrados")
    df_est = pd.read_sql("SELECT nombre, documento, grado FROM estudiantes WHERE profesor_id=?", 
                         conn, params=(st.session_state.usuario_logueado,))
    st.dataframe(df_est, use_container_width=True)

elif menu == "Escanear Asistencia":
    st.header("📷 Control de Asistencia QR")
    st.write("Usa la cámara para registrar la entrada de los estudiantes.")
    
    foto = st.camera_input("Escanear Código QR")
    if foto:
        st.info("Buscando código QR en la imagen...")
        # Aquí se integraría pyzbar en el futuro para procesar 'foto'

elif menu == "Reportes":
    st.header("📊 Reportes y Exportación")
    st.write("Selecciona el grado para generar el reporte de asistencia.")
    grado_rep = st.selectbox("Seleccionar Grado", ["601", "602", "701"])
    if st.button("Generar Excel"):
        st.download_button(label="Descargar Reporte", data="Datos de prueba", file_name="asistencia.csv")
