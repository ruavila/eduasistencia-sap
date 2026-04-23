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
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# Configuración optimizada para móviles (layout "wide" pero con elementos responsivos)
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()

# --- CABECERA CON ESCUDO RESTAURADO ---
col_esc, col_tit = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=100) # Restaurado el escudo
with col_tit:
    st.title(f"{APP_NAME}")
    st.caption(f"{COLEGIO} | {CREADOR}")
st.divider()

# --- CONTROL DE ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.title("🔐 Ingreso")
    t1, t2 = st.tabs(["Entrar", "Registro"])
    with t1:
        u = st.text_input("Usuario", key="u_l")
        p = st.text_input("Contraseña", type="password", key="p_l")
        if st.button("Ingresar", type="primary", use_container_width=True):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
    with t2:
        reg_nom = st.text_input("Nombre Completo")
        reg_usu = st.text_input("ID")
        reg_pass = st.text_input("Pass", type="password")
        if st.button("Registrar", use_container_width=True):
            conn = get_connection()
            conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_nom, reg_usu, hash_password(reg_pass)))
            conn.commit(); st.success("Listo")
    st.stop()

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("Menú", ["📚 Cursos", "👤 Estudiantes", "📷 Asistencia", "📊 Reportes", "⚙️ Salir"])
conn = get_connection()

if menu == "📚 Cursos":
    st.subheader("Mis Cursos")
    with st.expander("➕ Crear Nuevo Curso"):
        g = st.text_input("Grado (ej: 6-1)")
        m = st.text_input("Materia")
        if st.button("Guardar"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        st.info(f"{r['grado']} - {r['materia']}")

elif menu == "👤 Estudiantes":
    st.subheader("Carga Masiva")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Elegir Curso:", op)
        g_s, m_s = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file and st.button("Procesar y Generar QRs", use_container_width=True):
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
                canv.drawString(x, y-0.5*cm, enom[:20])
                x += 5.5*cm
                if x > 15*cm: x, y = 1.5*cm, y-6*cm
            conn.commit(); canv.save()
            st.download_button("📥 Descargar PDF", pdf_io.getvalue(), f"QRs_{g_s}.pdf", use_container_width=True)

elif menu == "📷 Asistencia":
    st.subheader("Registro QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # Cámara optimizada para celular
        codigo = qrcode_scanner(key="cam_mobile")
        if codigo:
            id_q = str(codigo).strip()
            res = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if res:
                f_h = datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit(); st.success(f"✅ {res[0]}")

        if st.button("Finalizar y Notificar Faltas", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, g_a, st.session_state.user))
            aus = todos[~todos['documento'].isin(pres['estudiante_id'])]
            for _, e in aus.iterrows():
                tel = str(e['whatsapp']).strip().replace(".0", "")
                if len(tel) == 10: tel = "57" + tel
                if len(tel) >= 12:
                    msg = f"Cordial saludo. {e['nombre']} no asistio hoy a la clase de {m_a}."
                    st.link_button(f"📲 WhatsApp: {e['nombre']}", f"https://api.whatsapp.com/send?phone={tel}&text={msg.replace(' ', '%20')}", use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("Informe General por Grado")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Ver Reporte de:", op_r)
        g_r, m_r = sel_r.split(" | ")
        
        # 1. Obtener todas las fechas en las que se ha tomado asistencia en este grado
        fechas_clase = pd.read_sql("SELECT DISTINCT fecha FROM asistencia WHERE grado=? AND materia=? AND profe_id=? ORDER BY fecha ASC", 
                                   conn, params=(g_r, m_r, st.session_state.user))
        
        if not fechas_clase.empty:
            # 2. Obtener lista base de estudiantes
            estudiantes = pd.read_sql("SELECT documento, nombre FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY nombre ASC", 
                                      conn, params=(g_r, m_r, st.session_state.user))
            
            # 3. Construir Matriz Detallada
            for _, f_row in fechas_clase.iterrows():
                f_actual = f_row['fecha']
                asistencias_dia = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND materia=? AND profe_id=?", 
                                             conn, params=(f_actual, g_r, m_r, st.session_state.user))
                estudiantes[f_actual] = estudiantes['documento'].apply(lambda x: "✓ Asistió" if x in asistencias_dia['estudiante_id'].values else "X No Asistió")
            
            st.dataframe(estudiantes, use_container_width=True)
            
            # Exportar Excel Detallado
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                estudiantes.to_excel(writer, sheet_name='Detalle_Asistencia', startrow=6, index=False)
                wb = writer.book; ws = writer.sheets['Detalle_Asistencia']
                f_h = wb.add_format({'bold': True, 'size': 14}); f_txt = wb.add_format({'size': 11})
                ws.write('A1', COLEGIO.upper(), f_h)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}", f_txt)
                ws.write('A3', f"ASIGNATURA: {m_r}", f_txt)
                ws.write('A4', f"GRADO: {g_r}", f_txt)
                ws.write('A5', f"REPORTE GENERADO: {datetime.now().strftime('%Y-%m-%d %H:%M')}", f_txt)
            
            st.download_button("📥 Descargar Informe Completo (Excel)", output.getvalue(), f"Reporte_{g_r}_{m_r}.xlsx", use_container_width=True)
        else: st.info("Aún no hay asistencias registradas.")

elif menu == "⚙️ Salir":
    st.session_state.logueado = False; st.rerun()
