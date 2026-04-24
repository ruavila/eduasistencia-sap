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

# Asegurar que la base de datos tenga la columna tema
try:
    conn.execute("ALTER TABLE asistencia ADD COLUMN tema TEXT")
    conn.commit()
except:
    pass

# CABECERA VISUAL
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Desarrollador: Rubén Darío Ávila Sandoval</p>", unsafe_allow_html=True)
st.divider()

# --- SISTEMA DE LOGUEO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar", use_container_width=True, type="primary"):
        res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
        if res:
            st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
            st.rerun()
        else: st.error("Acceso denegado")
    st.stop()

# --- MENÚ DE NAVEGACIÓN ---
menu = st.sidebar.radio("Menú", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Mis Cursos":
    st.subheader("Gestión de Cursos")
    with st.form("nuevo_curso"):
        g, m = st.text_input("Grado"), st.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"📖 {r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Seleccione el Curso:", op)
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file and st.button("Generar QRs y Guardar", use_container_width=True):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            w, h = letter; x, y = 1.5*cm, h - 5.5*cm
            for _, row in df.iterrows():
                eid = str(row['estudiante_id']).strip().split('.')[0]
                enom = str(row['nombre']).strip().upper()
                ews = str(row.get('whatsapp', '')).strip().split('.')[0]
                conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(eid); qr.make(fit=True)
                img = qr.make_image().convert('RGB'); tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawCentredString(x + 2*cm, y - 0.4*cm, enom[:22])
                x += 6.5*cm
                if x > w - 5*cm: x, y = 1.5*cm, y - 6.5*cm
                if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5.5*cm
            conn.commit(); canv.save()
            st.download_button("📥 Descargar PDF de QRs", pdf_io.getvalue(), f"QRs_{gs}.pdf", use_container_width=True)

elif menu == "📷 Asistencia QR":
    st.subheader("Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        ga, ma = sel_a.split(" | ")
        tema = st.text_input("Tema de la clase:", key="t_asistencia")
        
        if not tema:
            st.warning("⚠️ Escriba el tema para activar el scanner.")
        else:
            cam_key = f"scan_{ga.replace(' ','')}_{len(tema)}"
            codigo = qrcode_scanner(key=cam_key)
            if codigo:
                id_q = "".join(filter(str.isalnum, str(codigo)))
                res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", (f"%{id_q}%", ga, st.session_state.user)).fetchone()
                if res:
                    doc_db, nom_est = res
                    f_h = datetime.now().strftime("%Y-%m-%d")
                    dupe = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=? AND grado=?", (doc_db, f_h, tema, ga)).fetchone()
                    if not dupe:
                        h_a = datetime.now().strftime("%H:%M:%S")
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc_db, f_h, h_a, ga, ma, tema, st.session_state.user))
                        conn.commit(); st.success(f"✅ {nom_est} registrado")
                    else: st.info(f"{nom_est} ya fue registrado.")
                else: st.error(f"ID {id_q} no encontrado.")

        st.divider()
        if st.button("🚀 Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            try:
                f_hoy = datetime.now().strftime("%Y-%m-%d")
                todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
                pres_df = pd.read_sql("SELECT DISTINCT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, ga, st.session_state.user))
                pres_list = pres_df['estudiante_id'].astype(str).tolist()
                aus = todos[~todos['documento'].astype(str).isin(pres_list)]
                
                if aus.empty: st.success("¡Asistencia completa!")
                else:
                    for _, e in aus.iterrows():
                        tel = str(e['whatsapp']).strip().split('.')[0]
                        tel_f = "57" + tel if len(tel) == 10 else tel
                        msg = f"Cordial saludo. El estudiante {e['nombre']} no asistio hoy a la clase de {ma}. Tema: {tema}"
                        st.link_button(f"📲 WhatsApp {e['nombre'][:15]}", f"https://api.whatsapp.com/send?phone={tel_f}&text={msg.replace(' ', '%20')}", use_container_width=True)
            except Exception as ex: st.error(f"Error: {ex}")

elif menu == "📊 Reportes":
    st.subheader("Reporte General")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Elegir Reporte:", op_r)
        gr, mr = sel_r.split(" | ")
        df_rep = pd.read_sql("""SELECT e.documento as Codigo, e.nombre as Nombre, a.tema as Tema, a.fecha as Fecha, a.hora as Hora 
                                FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                WHERE a.grado=? AND a.materia=? AND a.profe_id=? 
                                ORDER BY a.fecha ASC, e.documento ASC""", conn, params=(gr, mr, st.session_state.user))
        if not df_rep.empty:
            st.dataframe(df_rep, use_container_width=True)
            t_clases = df_rep['Fecha'].nunique()
            resumen = df_rep.groupby(['Codigo', 'Nombre']).size().reset_index(name='Asistencias')
            resumen['Inasistencias'] = t_clases - resumen['Asistencias']
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_rep.to_excel(writer, sheet_name='Detalle', startrow=7, index=False)
                wb, ws = writer.book, writer.sheets['Detalle']
                f_tit = wb.add_format({'bold': True, 'size': 14}); f_inf = wb.add_format({'size': 11})
                ws.write('A1', COLEGIO.upper(), f_tit)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}", f_inf)
                ws.write('A3', f"MATERIA: {mr} | GRADO: {gr}", f_inf)
                ws.write('A4', f"TOTAL SESIONES: {t_clases}", f_inf)
                ws.set_column('A:E', 25)
                resumen.to_excel(writer, sheet_name='Estadisticas', index=False)
            st.download_button("📥 Descargar Reporte Completo", output.getvalue(), f"Reporte_{gr}.xlsx", use_container_width=True)

elif menu == "⚙️ Reinicio":
    st.warning("Zona de borrado.")
    conf = st.text_input("Escriba ELIMINAR:")
    if st.button("LIMPIAR MI CUENTA") and conf == "ELIMINAR":
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
