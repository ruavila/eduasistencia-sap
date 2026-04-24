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

# --- CONFIGURACIÓN ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()
conn = get_connection()

# Asegurar que la tabla asistencia tenga la columna tema
try:
    conn.execute("ALTER TABLE asistencia ADD COLUMN tema TEXT")
    conn.commit()
except:
    pass

# CABECERA
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Creador: Rubén Darío Ávila Sandoval</p>", unsafe_allow_html=True)
st.divider()

# --- LOGIN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar", use_container_width=True, type="primary"):
        res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
        if res:
            st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
            st.rerun()
        else: st.error("Acceso denegado")
    st.stop()

# --- MENÚ ---
menu = st.sidebar.radio("Menú", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Mis Cursos":
    st.subheader("Gestión de Cursos")
    with st.form("nuevo_curso"):
        g, m = st.text_input("Grado"), st.text_input("Materia")
        if st.form_submit_button("Añadir"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso:", op)
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file and st.button("Generar QRs (4x4)", use_container_width=True):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            w, h = letter; x, y = 1.5*cm, h - 5.5*cm
            for _, row in df.iterrows():
                eid = str(row['estudiante_id']).strip()
                enom = str(row['nombre']).strip().upper()
                ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(eid); qr.make(fit=True)
                img = qr.make_image().convert('RGB'); tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawCentredString(x + 2*cm, y - 0.4*cm, enom[:22])
                x += 6.5*cm
                if x > w - 5*cm: x, y = 1.5*cm, y - 6.5*cm
                if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5.5*cm
            conn.commit(); canv.save()
            st.download_button("📥 Descargar PDF", pdf_io.getvalue(), f"QRs_{gs}.pdf", use_container_width=True)

elif menu == "📷 Asistencia QR":
    st.subheader("Toma de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Elegir Curso:", op_a)
        ga, ma = sel_a.split(" | ")
        tema = st.text_input("Tema de la clase:", key="tema_dia")
        
        if tema:
            codigo = qrcode_scanner(key="scanner_v11")
            if codigo:
                # Limpieza agresiva de caracteres para celulares
                id_q = "".join(filter(str.isalnum, str(codigo)))
                res = conn.execute("SELECT nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", 
                                   (f"%{id_q}%", ga, st.session_state.user)).fetchone()
                if res:
                    f_h = datetime.now().strftime("%Y-%m-%d")
                    # Permitimos múltiples registros si el docente lo requiere
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", 
                                 (id_q, f_h, h_a, ga, ma, tema, st.session_state.user))
                    conn.commit(); st.success(f"✅ {res[0]} registrado")
                else: st.error(f"El estudiante con ID {id_q} no pertenece a este grupo.")

        st.divider()
        if st.button("Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
            pres = pd.read_sql("SELECT DISTINCT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, ga, st.session_state.user))
            aus = todos[~todos['documento'].isin(pres['estudiante_id'])]
            for _, e in aus.iterrows():
                tel = str(e['whatsapp']).strip().replace(".0", "")
                tel_f = "57" + tel if len(tel) == 10 else tel
                msg = f"Cordial saludo. El estudiante {e['nombre']} no asistio hoy a {ma}. Tema: {tema}"
                st.link_button(f"📲 Notificar {e['nombre'][:15]}", f"https://api.whatsapp.com/send?phone={tel_f}&text={msg.replace(' ', '%20')}", use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("Reporte Detallado y Estadísticas")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Generar reporte de:", op_r)
        gr, mr = sel_r.split(" | ")
        
        # Obtener todos los registros de asistencia
        df_asis = pd.read_sql("""SELECT e.documento as Codigo, e.nombre as Nombre, a.tema as Tema, a.fecha as Fecha, a.hora as Hora 
                                 FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                 WHERE a.grado=? AND a.materia=? AND a.profe_id=? 
                                 ORDER BY a.fecha ASC, a.hora ASC""", conn, params=(gr, mr, st.session_state.user))
        
        if not df_asis.empty:
            st.dataframe(df_asis, use_container_width=True)
            
            # CÁLCULOS ESTADÍSTICOS
            total_clases = df_asis['Fecha'].nunique()
            # Conteo de asistencias por estudiante
            stats = df_asis.groupby(['Codigo', 'Nombre']).size().reset_index(name='Asistencias')
            stats['Inasistencias'] = total_clases - stats['Asistencias']
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Hoja 1: Detalle por clase
                df_asis.to_excel(writer, sheet_name='Detalle', startrow=7, index=False)
                wb = writer.book; ws = writer.sheets['Detalle']
                f_tit = wb.add_format({'bold': True, 'size': 14}); f_info = wb.add_format({'size': 11})
                ws.write('A1', COLEGIO.upper(), f_tit)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}", f_info)
                ws.write('A3', f"MATERIA: {mr} | GRADO: {gr}", f_info)
                ws.write('A4', f"TOTAL CLASES REGISTRADAS: {total_clases}", f_info)
                ws.set_column('A:E', 20)
                
                # Hoja 2: Estadísticas finales
                stats.to_excel(writer, sheet_name='Resumen_Final', index=False)
                ws2 = writer.sheets['Resumen_Final']
                ws2.set_column('A:D', 20)
            
            st.download_button("📥 Descargar Reporte Completo", output.getvalue(), f"Reporte_{gr}.xlsx", use_container_width=True)

elif menu == "⚙️ Reinicio":
    st.warning("Zona de borrado de datos.")
    confirm = st.text_input("Escriba ELIMINAR para confirmar:")
    if st.button("BORRAR DATOS DEL PROFESOR"):
        if confirm == "ELIMINAR":
            conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
            conn.commit(); st.success("Datos borrados."); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
