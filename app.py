import streamlit as st
import pandas as pd
import qrcode
import io
import os
import urllib.parse
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.units import cm
from streamlit_qrcode_scanner import qrcode_scanner

from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH

# --- INICIALIZACIÓN ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()
conn = get_connection()

# CABECERA INSTITUCIONAL
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.get('profe_nom', 'Usuario')}</p>", unsafe_allow_html=True)
st.divider()

# --- AUTENTICACIÓN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab_in, tab_up = st.tabs(["🔐 Ingresar", "📝 Registrarse"])
    with tab_in:
        u_log = st.text_input("Usuario", key="u_l")
        p_log = st.text_input("Contraseña", type="password", key="p_l")
        if st.button("Entrar", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u_log, hash_password(p_log))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u_log, res[0]
                st.rerun()
            else: st.error("Datos incorrectos.")
    with tab_up:
        nu, nn, np = st.text_input("Nuevo ID"), st.text_input("Nombre Completo"), st.text_input("Clave", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (nu, hash_password(np), nn))
                conn.commit(); st.success("Cuenta lista.")
            except: st.error("El usuario ya existe.")
    st.stop()

# --- MENÚ PRINCIPAL ---
menu = st.sidebar.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Cursos":
    st.subheader("Sus Cursos")
    g_in = st.text_input("Grado")
    m_in = st.text_input("Materia")
    if st.button("Añadir Curso"):
        conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g_in, m_in, st.session_state.user))
        conn.commit(); st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Importar Estudiantes (Excel)")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gs, ms = sel.split(" | ")
        f_up = st.file_uploader("Subir listado (.xlsx)", type=["xlsx"])
        
        if f_up and st.button("Procesar y Generar PDF"):
            df = pd.read_excel(f_up); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
            w, h = landscape(legal); x, y = 1.5*cm, h - 5*cm
            col_c = 0
            for _, r in df.iterrows():
                e_id = str(r['estudiante_id']).split('.')[0]
                e_nm = str(r['nombre']).upper()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", (e_id, e_nm, e_ws, gs, ms, st.session_state.user))
                
                qr = qrcode.make(e_id); t_qr = io.BytesIO(); qr.save(t_qr, format='PNG'); t_qr.seek(0)
                canv.drawInlineImage(Image.open(t_qr), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawString(x, y-0.6*cm, e_nm[:22])
                
                col_c += 1
                if col_c >= 3: x, y, col_c = 1.5*cm, y - 6*cm, 0
                else: x += 6.5*cm
                if y < 2*cm: canv.showPage(); x, y, col_c = 1.5*cm, h-5*cm, 0
            
            conn.commit(); canv.save()
            st.download_button("📥 Bajar PDF de Carnets", pdf_io.getvalue(), f"QRs_{gs}.pdf", use_container_width=True)

elif menu == "📷 Scanner QR":
    st.subheader("Registro de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_as = st.selectbox("Clase:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la clase:")
        
        if tema:
            sc_key = f"sc_{ga}_{len(tema)}"
            codigo = qrcode_scanner(key=sc_key)
            if codigo:
                id_cl = "".join(filter(str.isalnum, str(codigo)))
                res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", (f"%{id_cl}%", ga, st.session_state.user)).fetchone()
                if res:
                    doc, nom = res; hoy = datetime.now().strftime("%Y-%m-%d")
                    if not conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", (doc, hoy, tema)).fetchone():
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc, hoy, datetime.now().strftime("%H:%M:%S"), ga, ma, tema, st.session_state.user))
                        conn.commit(); st.success(f"✅ {nom} registrado")

elif menu == "📊 Reportes":
    st.subheader("Generar Planilla Oficial")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_r = st.selectbox("Curso para Reporte:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gr, mr = sel_r.split(" | ")
        if st.button("📄 Generar Reporte PDF", type="primary", use_container_width=True):
            estudiantes = pd.read_sql("SELECT documento, nombre FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY nombre ASC", conn, params=(gr, mr, st.session_state.user))
            asist_data = pd.read_sql("SELECT estudiante_id, fecha, tema FROM asistencia WHERE grado=? AND materia=? AND profe_id=?", conn, params=(gr, mr, st.session_state.user))
            clases = asist_data[['fecha', 'tema']].drop_duplicates().sort_values(by='fecha').values.tolist()
            
            pdf_io = io.BytesIO()
            canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
            ancho_pag, alto_pag = landscape(legal)
            margen = 1.0*cm
            
            # ESCUDO CON TRANSPARENCIA (mask='auto')
            if os.path.exists(ESCUDO_PATH):
                img = Image.open(ESCUDO_PATH)
                canv.drawInlineImage(img, margen, alto_pag - 2.5*cm, width=2.2*cm, height=2.2*cm, preserveAspectRatio=True, mask='auto')
            
            # ENCABEZADO
            canv.setFont("Helvetica-Bold", 14)
            canv.drawCentredString(ancho_pag/2, alto_pag - 1.2*cm, COLEGIO)
            canv.setFont("Helvetica", 9)
            canv.drawString(margen + 2.5*cm, alto_pag - 1.8*cm, f"Asignatura: {mr}")
            canv.drawString(margen + 2.5*cm, alto_pag - 2.3*cm, f"Docente: {st.session_state.profe_nom}")
            canv.drawString(ancho_pag - 5.5*cm, alto_pag - 1.8*cm, f"Curso: {gr}")

            # LÓGICA DE DISTRIBUCIÓN DINÁMICA DE COLUMNAS
            w_nom = 8.0*cm
            w_totales = 3.2*cm 
            espacio_libre = ancho_pag - (margen * 2) - w_nom - w_totales
            
            n_clases = len(clases)
            # Expande las columnas para cubrir el espacio derecho
            if n_clases > 0:
                w_col = min(max(espacio_libre / n_clases, 1.4*cm), 3.5*cm)
            else:
                w_col = 1.4*cm

            x_curr, y_table = margen, alto_pag - 4.2*cm
            h_row = 0.6*cm
            
            # Cabecera de Tabla
            canv.rect(x_curr, y_table, w_nom, h_row)
            canv.setFont("Helvetica-Bold", 8); canv.drawString(x_curr + 0.2*cm, y_table + 0.2*cm, "NOMBRE DEL ESTUDIANTE")
            
            x_curr += w_nom
            for f, t in clases:
                canv.rect(x_curr, y_table, w_col, h_row)
                canv.saveState()
                canv.translate(x_curr + (w_col/2) + 0.1*cm, y_table + 0.1*cm)
                canv.rotate(90)
                canv.setFont("Helvetica-Bold", 6)
                canv.drawString(0, 0, f"{f} | {t[:12]}")
                canv.restoreState()
                x_curr += w_col
            
            canv.rect(x_curr, y_table, 1.6*cm, h_row); canv.drawCentredString(x_curr + 0.8*cm, y_table + 0.2*cm, "Asist.")
            x_curr += 1.6*cm
            canv.rect(x_curr, y_table, 1.6*cm, h_row); canv.drawCentredString(x_curr + 0.8*cm, y_table + 0.2*cm, "Ausen.")
            
            # Filas de Estudiantes
            y_f = y_table - h_row
            for i, est in estudiantes.iterrows():
                if y_f < margen + 0.5*cm:
                    canv.showPage(); y_f = alto_pag - 3.5*cm
                
                canv.rect(margen, y_f, w_nom, h_row)
                canv.setFont("Helvetica", 8); canv.drawString(margen + 0.1*cm, y_f + 0.2*cm, f"{i+1}. {est['nombre'][:45]}")
                
                x_f, t_as, t_au = margen + w_nom, 0, 0
                for f, t in clases:
                    canv.rect(x_f, y_f, w_col, h_row)
                    if not asist_data[(asist_data['estudiante_id']==est['documento']) & (asist_data['fecha']==f)].empty:
                        canv.setFont("ZapfDingbats", 10); canv.drawCentredString(x_f + w_col/2, y_f + 0.2*cm, "4")
                        canv.setFont("Helvetica", 8); t_as += 1
                    else:
                        canv.drawCentredString(x_f + w_col/2, y_f + 0.2*cm, "X"); t_au += 1
                    x_f += w_col
                
                canv.rect(x_f, y_f, 1.6*cm, h_row); canv.drawCentredString(x_f + 0.8*cm, y_f + 0.2*cm, str(t_as))
                x_f += 1.6*cm
                canv.rect(x_f, y_f, 1.6*cm, h_row); canv.drawCentredString(x_f + 0.8*cm, y_f + 0.2*cm, str(t_au))
                y_f -= h_row
            
            canv.save()
            st.download_button("📥 Descargar Planilla PDF", pdf_io.getvalue(), f"Reporte_{gr}_{mr}.pdf", "application/pdf", use_container_width=True)

elif menu == "⚙️ Reinicio":
    if st.button("LIMPIAR MIS DATOS"):
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
