import sys
import os
import streamlit as st
import pandas as pd
from PIL import Image
import qrcode
import io

# Librerías para la generación del PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm

# Asegurar que encuentre la carpeta 'modules'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from modules.database import init_db, get_connection
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login, registrar_usuario

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CABECERA ---
col_esc, col_tit = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=100)
with col_tit:
    st.title(APP_NAME)
    st.write(f"**{COLEGIO}** | Docente: {CREADOR}")

st.divider()

# --- GESTIÓN DE SESIÓN ---
if 'usuario_logueado' not in st.session_state:
    st.session_state.usuario_logueado = None
    st.session_state.nombre_profe = None

if st.session_state.usuario_logueado is None:
    tab_l, tab_r = st.tabs(["📧 Iniciar Sesión", "📝 Registrarse"])
    with tab_l:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Clave", type="password", key="login_p")
        if st.button("Entrar", type="primary"):
            datos = check_login(u, p)
            if datos:
                st.session_state.usuario_logueado = u
                st.session_state.nombre_profe = datos[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
    with tab_r:
        r_n = st.text_input("Nombre Completo", key="reg_n")
        r_u = st.text_input("Usuario (ID)", key="reg_u")
        r_p = st.text_input("Contraseña", type="password", key="reg_p")
        r_c = st.text_input("Confirmar Contraseña", type="password", key="reg_c")
        if st.button("Finalizar Registro"):
            if r_p == r_c and r_u and r_n:
                if registrar_usuario(r_n, r_u, r_p):
                    st.success("¡Registrado con éxito! Ya puedes iniciar sesión.")
                else:
                    st.error("El usuario ya existe.")
            else:
                st.warning("Verifica los campos y que las claves coincidan.")
    st.stop()

# --- MENÚ LATERAL ---
st.sidebar.success(f"Sesión activa: {st.session_state.nombre_profe}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.usuario_logueado = None
    st.session_state.nombre_profe = None
    st.rerun()

menu = st.sidebar.selectbox("Menú de Navegación", ["Mis Cursos", "Gestionar Estudiantes", "Escanear Asistencia", "Reportes"])
conn = get_connection()

# --- SECCIÓN: MIS CURSOS ---
if menu == "Mis Cursos":
    st.header("📚 Gestión de Cursos")
    with st.expander("➕ Registrar Nuevo Curso"):
        with st.form("f_curso"):
            g = st.text_input("Grado (ej: 601)")
            m = st.text_input("Materia")
            if st.form_submit_button("Guardar Curso"):
                if g and m:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO cursos (grado, materia, profesor_id) VALUES (?, ?, ?)", 
                                       (g, m, st.session_state.usuario_logueado))
                        conn.commit()
                        st.success(f"Curso {g} guardado.")
                        st.rerun()
                    except:
                        st.error("Este curso ya está registrado.")

    st.subheader("📋 Lista de Cursos Actuales")
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profesor_id=?", 
                       conn, params=(st.session_state.usuario_logueado,))
    
    if df_c.empty:
        st.info("No tienes cursos registrados.")
    else:
        for idx, row in df_c.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**Grado:** {row['grado']}")
            c2.write(f"**Materia:** {row['materia']}")
            if c3.button("🗑️ Eliminar", key=f"del_{row['id']}"):
                conn.cursor().execute("DELETE FROM cursos WHERE id=?", (row['id'],))
                conn.commit()
                st.rerun()
            st.divider()

# --- SECCIÓN: GESTIONAR ESTUDIANTES ---
elif menu == "Gestionar Estudiantes":
    st.header("👤 Carga de Estudiantes y PDF de QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profesor_id=?", 
                       conn, params=(st.session_state.usuario_logueado,))
    
    if df_c.empty:
        st.warning("Primero registra un curso en la sección 'Mis Cursos'.")
    else:
        opciones = {f"{r['grado']} - {r['materia']}": r['grado'] for i, r in df_c.iterrows()}
        seleccion = st.selectbox("Seleccione el curso destino:", opciones.keys())
        grado_sel = opciones[seleccion]
        materia_sel = seleccion.split(" - ")[1]

        file = st.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "csv"])
        if file:
            try:
                if file.name.endswith('.csv'):
                    df_al = pd.read_csv(file)
                else:
                    df_al = pd.read_excel(file, engine='openpyxl')
                
                st.write("Vista previa de la lista:")
                st.dataframe(df_al.head())

                if st.button("Generar PDF con Carnets QR"):
                    pdf_buf = io.BytesIO()
                    canv = canvas.Canvas(pdf_buf, pagesize=letter)
                    w, h = letter
                    
                    # Configuración de cuadrícula (4x4 cm)
                    mx, my, sz, gap = 1.5*cm, 2*cm, 4*cm, 1.2*cm
                    curr_x, curr_y = mx, h - my - sz

                    for _, row in df_al.iterrows():
                        nom = str(row['nombre']).upper()
                        doc = str(row['documento'])
                        
                        # Formato de texto: Iniciales - Nombre Completo
                        ini = "".join([p[0] for p in nom.split() if p])
                        txt_final = f"{ini} - {nom}"

                        # Guardar estudiante en DB (ignorar si ya existe)
                        try:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO estudiantes (nombre, documento, grado, profesor_id) VALUES (?, ?, ?, ?)",
                                           (nom, doc, grado_sel, st.session_state.usuario_logueado))
                            conn.commit()
                        except:
                            pass

                        # Generar Imagen QR
                        qr_img = qrcode.make(doc)
                        img_b = io.BytesIO()
                        qr_img.save(img_b, format="PNG")
                        img_b.seek(0)

                        # Dibujar en PDF
                        canv.drawInlineImage(img_b, curr_x, curr_y, width=sz, height=sz)
                        canv.setFont("Helvetica-Bold", 6)
                        canv.drawCentredString(curr_x + (sz/2), curr_y - 0.3*cm, txt_final)
                        canv.setFont("Helvetica", 5)
                        canv.drawCentredString(curr_x + (sz/2), curr_y - 0.6*cm, f"{grado_sel} | {materia_sel}")

                        # Lógica de saltos de línea/página
                        curr_x += sz + gap
                        if curr_x + sz > w - mx:
                            curr_x = mx
                            curr_y -= sz + 1.5*cm
                        if curr_y < my:
                            canv.showPage()
                            curr_x, curr_y = mx, h - my - sz

                    canv.save()
                    st.success("✅ PDF generado correctamente.")
                    st.download_button("📥 Descargar PDF de QRs", pdf_buf.getvalue(), f"QRs_{grado_sel}.pdf", "application/pdf")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

# --- SECCIONES RESTANTES ---
elif menu == "Escanear Asistencia":
    st.header("📷 Escáner de Asistencia QR")
    st.camera_input("Capturar código QR del estudiante")

elif menu == "Reportes":
    st.header("📊 Reportes y Estadísticas")
    st.info("Módulo de reportes en desarrollo.")
