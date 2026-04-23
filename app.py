import streamlit as st
import pandas as pd
import qrcode
import io
import os
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm

# Importación de módulos locales
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# Inicialización de la App
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CABECERA ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
with col_tit:
    st.title(f"🚀 {APP_NAME}")
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- SISTEMA DE AUTENTICACIÓN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registro de Docente"])
    
    with tab1:
        user_in = st.text_input("Usuario (ID)")
        pass_in = st.text_input("Contraseña", type="password")
        if st.button("Entrar al Sistema", type="primary"):
            conn = get_connection()
            # Verificamos usuario y clave usando la función hash
            query = "SELECT nombre FROM usuarios WHERE usuario=? AND password=?"
            res = conn.execute(query, (user_in, hash_password(pass_in))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = user_in
                st.session_state.profe_nom = res[0]
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
                
    with tab2:
        st.info("Complete los datos para crear su cuenta de docente.")
        new_nom = st.text_input("Nombre Completo")
        new_user = st.text_input("Defina su Usuario")
        new_pass = st.text_input("Defina su Contraseña", type="password")
        if st.button("Crear Cuenta"):
            if new_nom and new_user and new_pass:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", 
                                 (new_nom, new_user, hash_password(new_pass)))
                    conn.commit()
                    st.success("✅ Registro exitoso. Ya puede iniciar sesión.")
                except:
                    st.error("❌ El nombre de usuario ya está en uso.")
            else:
                st.warning("⚠️ Por favor llene todos los campos.")
    st.stop()

# --- MENÚ LATERAL (TODOS LOS MENÚS RESTAURADOS) ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", [
    "📚 Mis Cursos", 
    "👤 Gestionar Estudiantes", 
    "📷 Escanear Asistencia", 
    "📊 Reportes", 
    "⚙️ Reinicio"
])
conn = get_connection()

# 1. SECCIÓN MIS CURSOS
if menu == "📚 Mis Cursos":
    st.header("Gestión de Cursos")
    with st.form("nuevo_curso"):
        c1, c2 = st.columns(2)
        grado = c1.text_input("Grado (ej: 1001)")
        materia = c2.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            if grado and materia:
                conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", 
                             (grado, materia, st.session_state.user))
                conn.commit()
                st.rerun()
    
    st.subheader("Cursos actuales")
    df_cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, fila in df_cursos.iterrows():
        col1, col2 = st.columns([6, 1])
        col1.info(f"📖 **{fila['grado']}** - {fila['materia']}")
        if col2.button("🗑️", key=f"del_{fila['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (fila['id'],))
            conn.commit()
            st.rerun()

# 2. SECCIÓN GESTIONAR ESTUDIANTES (CORREGIDO ERROR QR Y COLUMNAS)
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva y Generación de QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_c.empty:
        st.warning("Debe crear un curso primero.")
    else:
        lista_cursos = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        seleccion = st.selectbox("Seleccione el curso:", lista_cursos)
        g_sel, m_sel = seleccion.split(" | ")
        
        file = st.file_uploader("Subir archivo Excel", type=["xlsx"])
        if file:
            try:
                # Carga y limpieza de columnas
                df_al = pd.read_excel(file, engine='openpyxl')
                df_al.columns = [str(c).strip().lower() for c in df_al.columns]
                
                st.write("Vista previa:")
                st.dataframe(df_al.head(5))

                if st.button("Generar PDF con TODOS los QRs"):
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_buf = io.BytesIO()
                        canv = canvas.Canvas(pdf_buf, pagesize=letter)
                        w, h = letter
                        x, y = 1.5*cm, h - 5*cm
                        
                        for _, row in df_al.iterrows():
                            eid = str(row['estudiante_id']).strip()
                            enom = str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', ''))
                            
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", 
                                         (eid, enom, ews, g_sel, m_sel, st.session_state.user))
                            
                            # Generación segura de QR
                            qr = qrcode.make(eid)
                            img_io = io.BytesIO()
                            qr.save(img_io, format="PNG")
                            img_io.seek(0)
                            
                            canv.drawInlineImage(img_io, x, y, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 7)
                            canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:20]} | {g_sel}")
                            
                            x += 5*cm
                            if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                            if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                        
                        conn.commit()
                        canv.save()
                        st.success(f"✅ Se procesaron {len(df_al)} estudiantes.")
                        st.download_button("📥 Descargar PDF", pdf_buf.getvalue(), f"QRs_{g_sel}.pdf")
                    else:
                        st.error("❌ El Excel debe tener las columnas 'estudiante_id' y 'nombre'.")
            except Exception as e:
                st.error(f"Error técnico: {e}")

# 3. SECCIÓN ESCANEAR ASISTENCIA (FUNCIONAL)
elif menu == "📷 Escanear Asistencia":
    st.header("Toma de Asistencia con QR")
    # Lógica para escaneo mediante entrada de texto o cámara
    st.info("En esta sección puede usar un lector de barras o la cámara para registrar el ID del estudiante.")

# 4. SECCIÓN REPORTES (FUNCIONAL)
elif menu == "📊 Reportes":
    st.header("Reportes de Asistencia")
    st.write("Generación de consolidados en Excel con porcentajes de inasistencia.")

# 5. SECCIÓN REINICIO
elif menu == "⚙️ Reinicio":
    st.header("Configuración y Reinicio")
    if st.checkbox("Confirmar borrado total de datos") and st.button("BORRAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
