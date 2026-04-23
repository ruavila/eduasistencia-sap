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

# Inicialización
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

# --- SESIÓN ---
if 'logueado' not in st.session_state: st.session_state.logueado = False
if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registro"])
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("❌ Datos incorrectos.")
    st.stop()

# --- MENÚ COMPLETO ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", [
    "📚 Mis Cursos", 
    "👤 Gestionar Estudiantes", 
    "📷 Escanear Asistencia", 
    "📊 Reportes", 
    "⚙️ Reinicio"
])
conn = get_connection()

# 1. MIS CURSOS
if menu == "📚 Mis Cursos":
    st.header("Gestión de Grupos y Materias")
    with st.form("f_cursos"):
        c1, c2 = st.columns(2)
        gr, mat = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Crear Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (gr, mat, st.session_state.user))
            conn.commit(); st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5,1])
        c1.info(f"📖 {r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

# 2. GESTIONAR ESTUDIANTES
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva de Alumnos")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Crea un curso primero.")
    else:
        opc = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        grado_sel, materia_sel = opc.split(" | ")
        file = st.file_uploader("Subir Excel (estudiante_id, nombre, whatsapp)", type=["xlsx"])
        
        if file:
            try:
                df_al = pd.read_excel(file, engine='openpyxl')
                df_al.columns = [str(c).strip().lower() for c in df_al.columns]
                st.write("Vista previa (5 primeros):")
                st.dataframe(df_al.head(5))

                if st.button("Generar PDF con TODOS los QRs (4x4 cm)"):
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_buf = io.BytesIO()
                        canv = canvas.Canvas(pdf_buf, pagesize=letter)
                        w, h = letter
                        x_in, y_in = 1.5*cm, h - 5*cm
                        
                        for idx, row in df_al.iterrows():
                            eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', ''))
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, grado_sel, materia_sel, st.session_state.user))
                            
                            qr_img = qrcode.make(eid)
                            img_b = io.BytesIO()
                            qr_img.save(img_b, format="PNG") # Corrección error BytesIO
                            img_b.seek(0)
                            
                            canv.drawInlineImage(img_b, x_in, y_in, width=4*cm, height=4*cm)
                            nombres = enom.split()
                            texto = f"{(nombres[1][0] if len(nombres)>1 else '')} {nombres[0]} | {grado_sel}"
                            canv.setFont("Helvetica-Bold", 7); canv.drawCentredString(x_in + 2*cm, y_in - 0.4*cm, texto)
                            
                            x_in += 5*cm
                            if x_in > w - 5*cm: x_in, y_in = 1.5*cm, y_in - 6*cm
                            if y_in < 2*cm: canv.showPage(); x_in, y_in = 1.5*cm, h - 5*cm
                        
                        conn.commit(); canv.save()
                        st.success(f"✅ {len(df_al)} estudiantes listos.")
                        st.download_button("📥 Descargar PDF", pdf_buf.getvalue(), f"QR_{grado_sel}.pdf")
            except Exception as e: st.error(f"Error: {e}")

# 3. ESCANEAR ASISTENCIA
elif menu == "📷 Escanear Asistencia":
    st.header("Toma de Asistencia QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        opc = st.selectbox("Curso actual:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        grado, materia = opc.split(" | ")
        
        if 'asistentes' not in st.session_state: st.session_state.asistentes = set()
        
        scan = st.text_input("Enfoque el QR y el código aparecerá aquí (o use escáner):")
        if scan:
            st.session_state.asistentes.add(scan)
            st.success(f"Capturado ID: {scan}")

        if st.button("Finalizar y Notificar Ausentes"):
            # Lógica de comparación y envío (simulado para WhatsApp Web)
            st.info("Procesando inasistencias y preparando mensajes...")
            st.session_state.asistentes = set()

# 4. REPORTES
elif menu == "📊 Reportes":
    st.header("Consolidado de Asistencia")
    st.info("Aquí aparecerá el formato Excel con '✓' y 'X' y el % de asistencia.")
    # (Lógica de exportación Excel con pandas.ExcelWriter)

# 5. REINICIO
elif menu == "⚙️ Reinicio":
    st.header("Zona de Peligro")
    if st.checkbox("Confirmar eliminación de TODA la información") and st.button("BORRAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.success("Datos borrados."); st.rerun()

if st.sidebar.button("Cerrar Sesión"): st.session_state.logueado = False; st.rerun()
