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

# CABECERA INSTITUCIONAL EN PANTALLA
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
    t_in, t_up = st.tabs(["🔐 Ingresar", "📝 Registrarse"])
    with t_in:
        u_l = st.text_input("Usuario", key="u_l")
        p_l = st.text_input("Contraseña", type="password", key="p_l")
        if st.button("Entrar", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u_l, hash_password(p_l))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u_l, res[0]
                st.rerun()
            else: st.error("Acceso denegado")
    with t_up:
        nu, nn, np = st.text_input("Nuevo ID"), st.text_input("Nombre Completo"), st.text_input("Defina Clave", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (nu, hash_password(np), nn))
                conn.commit(); st.success("Cuenta creada correctamente.")
            except: st.error("El usuario ya existe.")
    st.stop()

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos")
    g, m = st.text_input("Grado"), st.text_input("Materia")
    if st.button("Añadir"):
        conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
        conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1]); c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga Masiva y Carnetización")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel = st.selectbox("Curso destino:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gs, ms = sel.split(" | ")
        f = st.file_uploader("Archivo Excel (.xlsx)", type=["xlsx"])
        if f and st.button("Procesar Estudiantes"):
            df = pd.read_excel(f); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf = io.BytesIO(); canv = canvas.Canvas(pdf, pagesize=legal)
            x, y, col = 1.5*cm, legal[1]-5*cm, 0
            for _, r in df.iterrows():
                e_id = str(r['estudiante_id']).split('.')[0]
                e_nm = str(r['nombre']).upper()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", (e_id, e_nm, e_ws, gs, ms, st.session_state.user))
                qr = qrcode.make(e_id); t_qr = io.BytesIO(); qr.save(t_qr, format='PNG'); t_qr.seek(0)
                canv.drawInlineImage(Image.open(t_qr), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawString(x, y-0.6*cm, e_nm[:22])
                col += 1
                if col >= 3: x, y, col = 1.5*cm, y-6*cm, 0
                else: x += 6.5*cm
                if y < 2*cm: canv.showPage(); x, y, col = 1.5*cm, legal[1]-5*cm, 0
            conn.commit(); canv.save()
            st.download_button("📥 Descargar PDF de Carnets", pdf.getvalue(), f"Carnets_{gs}.pdf", use_container_width=True)

elif menu == "📷 Scanner QR":
    st.subheader("Control en Tiempo Real")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_as = st.selectbox("Clase:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de hoy:")
        if tema:
            cod = qrcode_scanner(key=f"sc_{ga}_{len(tema)}")
            if cod:
                id_cl = "".join(filter(str.isalnum, str(cod)))
                res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", (f"%{id_cl}%", ga, st.session_state.user)).fetchone()
                if res:
                    doc, nom = res; hoy = datetime.now().strftime("%Y-%m-%d")
                    if not conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", (doc, hoy, tema)).fetchone():
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc, hoy, datetime.now().strftime("%H:%M:%S"), ga, ma, tema, st.session_state.user))
                        conn.commit(); st.success(f"✅ {nom} presente")
        st.divider()
        if st.button("🚀 Notificar Ausentes via WhatsApp", type="primary", use_container_width=True):
            hoy = datetime.now().strftime("%Y-%m-%d")
            all_e = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
            pre_e = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND tema=? AND profe_id=?", conn, params=(hoy, ga, tema, st.session_state.user))
            aus = all_e[~all_e['documento'].astype(str).isin(pre_e['estudiante_id'].astype(str).tolist())]
            for _, e in aus.iterrows():
                num = "".join(filter(str.isdigit, str(e['whatsapp']).split('.')[0]))
                num_f = "57" + num if len(num) == 10 else num
                txt = urllib.parse.quote(f"Aviso: El estudiante {e['nombre']} no asistió hoy a {ma}. Tema: {tema}")
                st.link_button(f"📲 Notificar a {e['nombre'][:18]}", f"https://api.whatsapp.com/send?phone={num_f}&text={txt}", use_container_width=True)

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
            ancho, alto = landscape(legal)
            
            # Margen estrecho (1.0 cm) para cubrir más información
            m = 1.0*cm
            
            # ESCUDO INSTITUCIONAL
            if os.path.exists(ESCUDO_PATH):
                canv.drawInlineImage(Image.open(ESCUDO_PATH), m, alto - 2.3*cm, 1.8*cm, 1.8*cm)
            
            # ENCABEZADO
            canv.setFont("Helvetica-Bold", 14)
            canv.drawCentredString(ancho/2, alto - 1.2*cm, COLEGIO)
            canv.setFont("Helvetica", 9)
            canv.drawString(m + 2.2*cm, alto - 1.8*cm, f"Asignatura: {mr}")
            canv.drawString(m + 2.2*cm, alto - 2.3*cm, f"Docente: {st.session_state.profe_nom}")
            canv.drawString(ancho - 5*cm, alto - 1.8*cm, f"Curso: {gr}")

            # CONFIGURACIÓN TABLA
            x_ini, y_sup = m, alto - 4.2*cm
            w_nom, w_col, h_row = 7.5*cm, 1.3*cm, 0.55*cm
            
            # Cabecera de Tabla
            canv.rect(x_ini, y_sup, w_nom, h_row)
            canv.setFont("Helvetica-Bold", 8); canv.drawString(x_ini + 0.2*cm, y_sup + 0.15*cm, "NOMBRE DEL ESTUDIANTE")
            
            curr_x = x_ini + w_nom
            for f, t in clases:
                canv.rect(curr_x, y_sup, w_col, h_row)
                canv.saveState()
                canv.translate(curr_x + 0.35*cm, y_sup + 0.1*cm)
                canv.rotate(90)
                canv.setFont("Helvetica-Bold", 5)
                # Mostrar Fecha y Tema truncado
                canv.drawString(0, 0, f"{f} | {t[:12]}")
                canv.restoreState()
                curr_x += w_col
            
            canv.rect(curr_x, y_sup, w_col, h_row); canv.drawString(curr_x+0.1*cm, y_sup+0.15*cm, "Asist."); curr_x += w_col
            canv.rect(curr_x, y_sup, w_col, h_row); canv.drawString(curr_x+0.1*cm, y_sup+0.15*cm, "Ausen."); curr_x += w_col
            
            # Cuerpo de la Tabla
            y_f = y_sup - h_row
            for i, est in estudiantes.iterrows():
                if y_f < m + 1*cm:
                    canv.showPage(); y_f = alto - 3*cm
                
                canv.rect(x_ini, y_f, w_nom, h_row)
                canv.setFont("Helvetica", 7); canv.drawString(x_ini + 0.1*cm, y_f + 0.15*cm, f"{i+1}. {est['nombre'][:45]}")
                
                curr_x, t_as, t_au = x_ini + w_nom, 0, 0
                for f, t in clases:
                    canv.rect(curr_x, y_f, w_col, h_row)
                    if not asist_data[(asist_data['estudiante_id']==est['documento']) & (asist_data['fecha']==f)].empty:
                        canv.setFont("ZapfDingbats", 10); canv.drawCentredString(curr_x + w_col/2, y_f + 0.15*cm, "4")
                        canv.setFont("Helvetica", 7); t_as += 1
                    else:
                        canv.drawCentredString(curr_x + w_col/2, y_f + 0.15*cm, "X"); t_au += 1
                    curr_x += w_col
                
                # Totales de Asistencia y Ausencia (Vital para calificar)
                canv.rect(curr_x, y_f, w_col, h_row); canv.drawCentredString(curr_x + w_col/2, y_f + 0.15*cm, str(t_as)); curr_x += w_col
                canv.rect(curr_x, y_f, w_col, h_row); canv.drawCentredString(curr_x + w_col/2, y_f + 0.15*cm, str(t_au))
                y_f -= h_row
            
            canv.save()
            st.download_button("📥 Descargar Planilla PDF", pdf_io.getvalue(), f"Reporte_{gr}_{mr}.pdf", "application/pdf", use_container_width=True)

elif menu == "⚙️ Reinicio":
    st.warning("⚠️ Acción irreversible")
    if st.button("BORRAR TODOS MIS DATOS"):
        conn.execute("DELETE FROM asistencia WHERE profe_id=?"); conn.execute("DELETE FROM estudiantes WHERE profe_id=?"); conn.execute("DELETE FROM cursos WHERE profe_id=?"); conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
