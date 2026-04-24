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

from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH

# --- INICIALIZACIÓN ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()
conn = get_connection()

# CABECERA
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Desarrollador: Rubén Darío Ávila Sandoval</p>", unsafe_allow_html=True)
st.divider()

# --- ACCESO Y REGISTRO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab_in, tab_reg = st.tabs(["🔐 Ingresar", "📝 Registrarme"])
    with tab_in:
        u = st.text_input("Usuario", key="l_u")
        p = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Entrar", use_container_width=True):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("Error de acceso")
    with tab_reg:
        nu, nn, np = st.text_input("ID Usuario"), st.text_input("Nombre"), st.text_input("Clave", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (nu, hash_password(np), nn))
                conn.commit(); st.success("¡Creado!")
            except: st.error("El usuario ya existe")
    st.stop()

# --- MENÚ ---
menu = st.sidebar.radio("Menú", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Cursos":
    st.subheader("Mis Cursos")
    g, m = st.text_input("Grado"), st.text_input("Materia")
    if st.button("Añadir"):
        conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
        conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Importar Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Excel", type=["xlsx"])
        if file and st.button("Procesar"):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            x, y = 1.5*cm, 22*cm
            for _, row in df.iterrows():
                eid = str(row['estudiante_id']).split('.')[0]
                enom = str(row['nombre']).upper()
                ews = str(row.get('whatsapp', '')).split('.')[0]
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                qr = qrcode.make(eid); tmp = io.BytesIO(); qr.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.drawString(x, y-0.5*cm, enom[:20])
                x += 6.5*cm
                if x > 15*cm: x, y = 1.5*cm, y - 6*cm
            conn.commit(); canv.save()
            st.download_button("Descargar QRs", pdf_io.getvalue(), "QRs.pdf")

elif menu == "📷 Scanner QR":
    st.subheader("Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_a = st.selectbox("Clase:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        ga, ma = sel_a.split(" | ")
        tema = st.text_input("Tema:")
        if tema:
            codigo = qrcode_scanner(key=f"c_{ga}_{len(tema)}")
            if codigo:
                id_q = "".join(filter(str.isalnum, str(codigo)))
                res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=?", (f"%{id_q}%", ga)).fetchone()
                if res:
                    doc, nom = res; f_h = datetime.now().strftime("%Y-%m-%d")
                    if not conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", (doc, f_h, tema)).fetchone():
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc, f_h, datetime.now().strftime("%H:%M:%S"), ga, ma, tema, st.session_state.user))
                        conn.commit(); st.success(f"Registrado: {nom}")
        st.divider()
        if st.button("🚀 Finalizar y Notificar"):
            f_h = datetime.now().strftime("%Y-%m-%d")
            # AQUÍ SE CORRIGIÓ EL ERROR: Se ordena por documento, NO por id
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY documento ASC", conn, params=(ga, ma, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=?", (f_h, ga))
            aus = todos[~todos['documento'].astype(str).isin(pres['estudiante_id'].astype(str))]
            for _, e in aus.iterrows():
                tel = "57" + str(e['whatsapp']).split('.')[0]
                msg = f"El estudiante {e['nombre']} no asistió a {ma}. Tema: {tema}"
                st.link_button(f"WhatsApp {e['nombre'][:10]}", f"https://api.whatsapp.com/send?phone={tel}&text={msg.replace(' ', '%20')}")

elif menu == "📊 Reportes":
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_r = st.selectbox("Ver:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gr, mr = sel_r.split(" | ")
        df_rep = pd.read_sql("SELECT e.nombre, a.tema, a.fecha, a.hora FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.grado=? AND a.profe_id=?", conn, params=(gr, st.session_state.user))
        st.dataframe(df_rep)

elif menu == "⚙️ Reinicio":
    if st.button("LIMPIAR TODO"):
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Salir"):
    st.session_state.logueado = False; st.rerun()
