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

# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")
init_db()

col_escudo, col_texto = st.columns([1, 5])
with col_escudo:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=120)
with col_texto:
    st.markdown(f"<h1 style='margin-bottom: 0;'>{COLEGIO}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0; color: #4F8BF9;'>{APP_NAME}</h3>", unsafe_allow_html=True)
    st.markdown(f"**Desarrollado por:** Rubén Darío Ávila Sandoval")
st.divider()

# 2. CONTROL DE ACCESO
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso al Sistema")
    t1, t2 = st.tabs(["Iniciar Sesión", "Registrar Docente"])
    with t1:
        u = st.text_input("Usuario", key="l_u")
        p = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Ingresar", type="primary", use_container_width=True):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("Credenciales incorrectas")
    with t2:
        r_n = st.text_input("Nombre Completo")
        r_u = st.text_input("Usuario (ID)")
        r_p = st.text_input("Contraseña", type="password")
        if st.button("Crear Cuenta", use_container_width=True):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (r_n, r_u, hash_password(r_p)))
                conn.commit(); st.success("Cuenta creada.")
            except: st.error("El usuario ya existe.")
    st.stop()

# 3. MENÚ Y LÓGICA PRINCIPAL
st.sidebar.markdown(f"### 👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Salir"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.subheader("Gestión de Cursos")
    with st.expander("➕ Agregar Nuevo Curso"):
        grado = st.text_input("Grado / Grupo")
        materia = st.text_input("Asignatura")
        if st.button("Guardar Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (grado, materia, st.session_state.user))
            conn.commit(); st.rerun()
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"**{r['grado']}** - {r['materia']}")
        if c2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso destino:", op)
        g_s, m_s = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file and st.button("Procesar y Generar PDF", use_container_width=True):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            x, y = 1.5*cm, 22*cm
            for _, row in df.iterrows():
                eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, g_s, m_s, st.session_state.user))
                qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(eid); qr.make(fit=True)
                img = qr.make_image().convert('RGB'); tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawCentredString(x + 2*cm, y - 0.5*cm, enom[:20])
                x += 5.5*cm
                if x > 15*cm: x, y = 1.5*cm, y-6*cm
            conn.commit(); canv.save()
            st.download_button("📥 Descargar QRs", pdf_io.getvalue(), f"QRs_{g_s}.pdf", use_container_width=True)

elif menu == "📷 Asistencia QR":
    st.subheader("Registro de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Seleccione el curso:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # NUEVO: Campo para el tema de la actividad
        tema_clase = st.text_input("📝 Tema o Actividad del día:", placeholder="Ej: Introducción a Python", key="tema_input")
        
        if not tema_clase:
            st.info("👆 Por favor escribe el tema de la clase para activar el escaner.")
        else:
            id_qr = qrcode_scanner(key="scanner_v7")
            if id_qr:
                id_q = str(id_qr).strip()
                res = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
                if res:
                    f_h = datetime.now().strftime("%Y-%m-%d")
                    ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                    if not ya:
                        h_a = datetime.now().strftime("%H:%M:%S")
                        # Guardamos el tema en la base de datos (asegúrate que tu DB tenga la columna o se manejará como texto extra)
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                        conn.commit(); st.success(f"✅ {res[0]} registrado")
                else: st.error("Estudiante no encontrado en este curso.")

        st.divider()
        if st.button("Finalizar y Notificar Ausencias", type="primary", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, g_a, st.session_state.user))
            aus = todos[~todos['documento'].isin(pres['estudiante_id'])]
            for _, est in aus.iterrows():
                tel = str(est['whatsapp']).strip().replace(".0", "")
                if len(tel) == 10: tel = "57" + tel
                if len(tel) >= 12:
                    msg = f"Cordial saludo. El estudiante {est['nombre']} no asistio hoy a la clase de {m_a}. Tema: {tema_clase}"
                    st.link_button(f"📲 Notificar a {est['nombre']}", f"https://api.whatsapp.com/send?phone={tel}&text={msg.replace(' ', '%20')}", use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("Informes de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Curso:", op_r)
        g_r, m_r = sel_r.split(" | ")
        
        fechas = pd.read_sql("SELECT DISTINCT fecha FROM asistencia WHERE grado=? AND materia=? AND profe_id=? ORDER BY fecha ASC", conn, params=(g_r, m_r, st.session_state.user))
        if not fechas.empty:
            estudiantes = pd.read_sql("SELECT documento, nombre FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY nombre ASC", conn, params=(g_r, m_r, st.session_state.user))
            for _, f_row in fechas.iterrows():
                f_act = f_row['fecha']
                asis_f = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND materia=? AND profe_id=?", conn, params=(f_act, g_r, m_r, st.session_state.user))
                estudiantes[f_act] = estudiantes['documento'].apply(lambda x: "✓" if x in asis_f['estudiante_id'].values else "X")
            
            st.dataframe(estudiantes, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                estudiantes.to_excel(writer, sheet_name='Asistencia', startrow=7, index=False)
                wb, ws = writer.book, writer.sheets['Asistencia']
                f_t = wb.add_format({'bold': True, 'size': 14}); f_s = wb.add_format({'size': 11})
                ws.write('A1', COLEGIO.upper(), f_t)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}", f_s)
                ws.write('A3', f"CREADOR: Rubén Darío Ávila Sandoval", f_s)
                ws.write('A4', f"ASIGNATURA: {m_r} | GRADO: {g_r}", f_s)
                ws.set_column('A:Z', 15)
            st.download_button("📥 Descargar Reporte Excel", output.getvalue(), f"Reporte_{g_r}.xlsx", use_container_width=True)

if menu == "⚙️ Salir" or st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
