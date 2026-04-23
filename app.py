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

# Módulos locales
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# 1. Configuración e Inicialización
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

# --- 2. SISTEMA DE ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    with tab1:
        u = st.text_input("Usuario", key="l_user")
        p = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Ingresar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("❌ Credenciales incorrectas.")
    with tab2:
        n = st.text_input("Nombre Completo")
        us = st.text_input("ID Usuario")
        cl = st.text_input("Contraseña", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (n, us, hash_password(cl)))
                conn.commit(); st.success("✅ Registro exitoso.")
            except: st.error("❌ El usuario ya existe.")
    st.stop()

# --- 3. NAVEGACIÓN ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])
conn = get_connection()

# SECCIÓN: MIS CURSOS
if menu == "📚 Mis Cursos":
    st.header("Gestión de Cursos")
    with st.form("nc"):
        c1, c2 = st.columns(2)
        g, m = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        col1, col2 = st.columns([6,1])
        col1.info(f"📖 {r['grado']} - {r['materia']}")
        if col2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

# SECCIÓN: GESTIONAR ESTUDIANTES (LOGRO: PDF Y QR VISIBLES)
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva y QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso:", op)
        g_s, m_s = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file:
            try:
                df = pd.read_excel(file, engine='openpyxl')
                df.columns = [str(c).strip().lower() for c in df.columns] # Normalización
                st.dataframe(df.head(5))
                if st.button("Generar PDF con QRs"):
                    if 'estudiante_id' in df.columns and 'nombre' in df.columns: # Clave corregida
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x_p, y_p = 1.5*cm, h - 5*cm
                        for _, row in df.iterrows():
                            eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, grado, materia, profe_id) VALUES (?,?,?,?,?)", (eid, enom, g_s, m_s, st.session_state.user))
                            # Lógica QR corregida
                            qr = qrcode.QRCode(version=1, box_size=10, border=1)
                            qr.add_data(eid); qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                            tmp_img = io.BytesIO(); img_qr.save(tmp_img, format='PNG'); tmp_img.seek(0)
                            canv.drawInlineImage(Image.open(tmp_img), x_p, y_p, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 8); canv.drawCentredString(x_p + 2*cm, y_p - 0.5*cm, f"{enom[:15]} | {g_s}")
                            x_p += 5.2*cm
                            if x_p > w - 5*cm: x_p, y_p = 1.5*cm, y_p - 6*cm
                            if y_p < 2*cm: canv.showPage(); x_p, y_p = 1.5*cm, h - 5*cm
                        conn.commit(); canv.save()
                        st.success("✅ PDF Generado."); st.download_button("📥 Descargar", pdf_io.getvalue(), f"QRs_{g_s}.pdf")
                    else: st.error("❌ Error en columnas.")
            except Exception as e: st.error(f"Error: {e}")

# SECCIÓN: ESCANEAR ASISTENCIA (NUEVO)
elif menu == "📷 Escanear Asistencia":
    st.header("📷 Control de Asistencia QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("⚠️ Debe crear un curso primero.")
    else:
        opciones_c = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        curso_asistencia = st.selectbox("Curso actual:", opciones_c)
        g_asist, m_asist = curso_asistencia.split(" | ")
        id_escaneado = st.text_input("👉 Escanee el QR o ingrese ID:", key="input_qr")
        if id_escaneado:
            res_e = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_escaneado.strip(), g_asist, st.session_state.user)).fetchone()
            if res_e:
                nom_e, f_hoy = res_e[0], datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_escaneado.strip(), f_hoy, g_asist)).fetchone()
                if ya: st.warning(f"⚠️ {nom_e} ya registró asistencia hoy.")
                else:
                    h_act = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_escaneado.strip(), f_hoy, h_act, g_asist, m_asist, st.session_state.user))
                    conn.commit(); st.balloons(); st.success(f"✅ Registrado: {nom_e} ({h_act})")
            else: st.error("❌ Estudiante no encontrado en este curso.")
        st.divider(); st.subheader("Últimos registros de hoy")
        f_act = datetime.now().strftime("%Y-%m-%d")
        df_hoy = pd.read_sql("SELECT a.hora, e.nombre FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.fecha = ? AND a.grado = ? AND a.profe_id = ? ORDER BY a.hora DESC LIMIT 5", conn, params=(f_act, g_asist, st.session_state.user))
        if not df_hoy.empty: st.table(df_hoy)

# SECCIÓN: REPORTES
elif menu == "📊 Reportes":
    st.header("Reportes de Asistencia")
    st.info("Próximamente: Descarga de consolidados en Excel.")

# SECCIÓN: REINICIO
elif menu == "⚙️ Reinicio":
    if st.checkbox("Confirmar borrado total") and st.button("LIMPIAR DATOS"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Salir"):
    st.session_state.logueado = False; st.rerun()
