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
from streamlit_qrcode_scanner import qrcode_scanner

# Módulos locales
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

# --- ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Login", "📝 Registro"])
    with t1:
        u = st.text_input("Usuario", key="l_u")
        p = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Ingresar"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("❌ Error de acceso.")
    with t2:
        n = st.text_input("Nombre Completo")
        us = st.text_input("ID Usuario")
        cl = st.text_input("Contraseña", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (n, us, hash_password(cl)))
                conn.commit(); st.success("✅ Registrado.")
            except: st.error("❌ Usuario ya existe.")
    st.stop()

# --- NAVEGACIÓN ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Menú", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Ajustes"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.header("Mis Grupos")
    with st.form("add_c"):
        c1, c2 = st.columns(2)
        g, m = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Crear"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        col1, col2 = st.columns([6,1])
        col1.info(f"{r['grado']} - {r['materia']}")
        if col2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.header("Carga Masiva (Excel)")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso.")
    else:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso destino:", op)
        g_s, m_s = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file:
            try:
                df = pd.read_excel(file, engine='openpyxl')
                df.columns = [str(c).strip().lower() for c in df.columns]
                st.dataframe(df.head(5))
                if st.button("Generar PDF y Guardar Estudiantes"):
                    if 'estudiante_id' in df.columns and 'nombre' in df.columns:
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x_p, y_p = 1.5*cm, h - 5*cm
                        for _, row in df.iterrows():
                            eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', '')).strip()
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, g_s, m_s, st.session_state.user))
                            # Lógica QR corregida para evitar error de visualización
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
                        st.success("✅ Proceso completado."); st.download_button("📥 Descargar PDF", pdf_io.getvalue(), f"Listado_{g_s}.pdf")
            except Exception as e: st.error(f"Error: {e}")

elif menu == "📷 Escanear Asistencia":
    st.header("📷 Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso.")
    else:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # Cámara activa
        id_qr = qrcode_scanner(key="scanner")
        if id_qr:
            id_q = str(id_qr).strip()
            res_e = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if res_e:
                nom_e, f_h = res_e[0], datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit(); st.success(f"✅ {nom_e} registrado."); st.toast(f"Presente: {nom_e}")
                else: st.warning(f"⚠️ {nom_e} ya estaba registrado.")
            else: st.error(f"❌ ID {id_q} no pertenece a este grupo.")

        # BOTÓN: FINALIZAR Y ENVIAR WHATSAPP
        st.divider()
        if st.button("Finalizar Clase y Notificar Inasistencias", type="primary"):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT documento, nombre, whatsapp FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            presentes = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, g_a, st.session_state.user))
            ausentes = todos[~todos['documento'].isin(presentes['estudiante_id'])]
            
            if ausentes.empty: st.success("🎉 ¡Asistencia Completa!")
            else:
                st.subheader(f"Ausentes detectados: {len(ausentes)}")
                for _, est in ausentes.iterrows():
                    tel = str(est['whatsapp']).strip()
                    if tel and len(tel) > 6:
                        msg = f"Saludos. Informamos que el estudiante *{est['nombre']}* no asistió hoy a la clase de *{m_a}*."
                        link = f"https://wa.me/{tel}?text={msg.replace(' ', '%20')}"
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"❌ {est['nombre']} (Tel: {tel})")
                        c2.link_button("📲 Enviar", link)
                    else: st.error(f"⚠️ {est['nombre']} sin número válido.")

        st.divider()
        st.write("### Registros de Hoy")
        f_act = datetime.now().strftime("%Y-%m-%d")
        df_h = pd.read_sql("SELECT a.hora, e.nombre FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.fecha = ? AND a.grado = ? AND a.profe_id = ? ORDER BY a.hora DESC", conn, params=(f_act, g_a, st.session_state.user))
        st.table(df_h)

elif menu == "📊 Reportes":
    st.header("Reportes")
    st.info("Consulte aquí el historial de asistencia.")

elif menu == "⚙️ Ajustes":
    if st.checkbox("Confirmar borrado total") and st.button("ELIMINAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
