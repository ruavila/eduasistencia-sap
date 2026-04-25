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

if 'logueado' not in st.session_state: 
    st.session_state.logueado = False
if 'captura_finalizada' not in st.session_state: 
    st.session_state.captura_finalizada = False

# --- AUTENTICACIÓN ---
if not st.session_state.logueado:
    col_esc, col_txt = st.columns([1, 4])
    with col_esc:
        if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=100)
    with col_txt:
        st.title(COLEGIO)
        st.subheader(f"Acceso Docente - {APP_NAME}")
    
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registrarse"])
    with t1:
        u_l = st.text_input("Usuario", key="login_u")
        p_l = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u_l, hash_password(p_l))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u_l, res[0]
                st.rerun()
            else: st.error("Credenciales incorrectas.")
    with t2:
        nu, nn, np = st.text_input("Nuevo ID"), st.text_input("Nombre Docente"), st.text_input("Clave", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (nu, hash_password(np), nn))
                conn.commit(); st.success("Registro exitoso.")
            except: st.error("El usuario ya existe.")
    st.stop()

# --- CABECERA ---
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

menu = st.sidebar.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

# 1. CURSOS
if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos")
    g, m = st.text_input("Grado"), st.text_input("Materia")
    if st.button("Añadir Curso"):
        conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
        conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

# 2. ESTUDIANTES
elif menu == "👤 Estudiantes":
    st.subheader("Listado de Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gs, ms = sel.split(" | ")
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        if f and st.button("Procesar"):
            df = pd.read_excel(f); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf = io.BytesIO(); canv = canvas.Canvas(pdf, pagesize=landscape(legal))
            x, y, col = 1.5*cm, landscape(legal)[1]-5*cm, 0
            for _, r in df.iterrows():
                e_id, e_nm = str(r['estudiante_id']).split('.')[0], str(r['nombre']).upper()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", (e_id, e_nm, e_ws, gs, ms, st.session_state.user))
                qr = qrcode.make(e_id); t_qr = io.BytesIO(); qr.save(t_qr, format='PNG'); t_qr.seek(0)
                canv.drawInlineImage(Image.open(t_qr), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawString(x, y-0.6*cm, e_nm[:22])
                col += 1
                if col >= 3: x, y, col = 1.5*cm, y-6*cm, 0
                else: x += 6.5*cm
                if y < 2*cm: canv.showPage(); x, y, col = 1.5*cm, landscape(legal)[1]-5*cm, 0
            conn.commit(); canv.save()
            st.download_button("📥 Descargar Carnets QR", pdf.getvalue(), f"QR_{gs}.pdf", use_container_width=True)

# 3. SCANNER QR Y GESTIÓN DE AUSENTES (SECCIÓN SOLICITADA)
elif menu == "📷 Scanner QR":
    st.subheader("Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if not df_c.empty:
        sel_as = st.selectbox("Seleccione el Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la clase (obligatorio para iniciar):")
        
        if tema:
            if not st.session_state.captura_finalizada:
                # --- MODO 1: ESCANEO ACTIVO ---
                st.markdown("### 📷 Capturando Asistencia...")
                st.info("El sistema está registrando los códigos QR. Al terminar, presione el botón de abajo.")
                
                cod = qrcode_scanner(key=f"scanner_{ga}")
                if cod:
                    id_cl = "".join(filter(str.isalnum, str(cod)))
                    res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", (f"%{id_cl}%", ga, st.session_state.user)).fetchone()
                    if res:
                        doc, nom = res; hoy = datetime.now().strftime("%Y-%m-%d")
                        if not conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", (doc, hoy, tema)).fetchone():
                            conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc, hoy, datetime.now().strftime("%H:%M:%S"), ga, ma, tema, st.session_state.user))
                            conn.commit(); st.success(f"Estudiante Registrado: {nom}")

                if st.button("⏹️ Finalizar Captura y Ver Ausentes", type="primary", use_container_width=True):
                    st.session_state.captura_finalizada = True
                    st.rerun()
            
            else:
                # --- MODO 2: REPORTE DE AUSENTES ---
                st.markdown("### 🔔 Estudiantes Ausentes")
                st.write("A continuación, se muestran los estudiantes que no asistieron. Puede enviar la notificación directamente.")
                
                if st.button("🔄 Volver al Scanner"):
                    st.session_state.captura_finalizada = False
                    st.rerun()

                st.divider()
                hoy = datetime.now().strftime("%Y-%m-%d")
                total_est = pd.read_sql("SELECT documento, nombre, whatsapp FROM estudiantes WHERE grado=? AND profe_id=?", conn, params=(ga, st.session_state.user))
                presentes = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND tema=?", conn, params=(hoy, ga, tema))
                ausentes = total_est[~total_est['documento'].isin(presentes['estudiante_id'])]
                
                if ausentes.empty:
                    st.success("¡Excelente! Todos los estudiantes registrados en este curso asistieron.")
                else:
                    for _, aus in ausentes.iterrows():
                        with st.container():
                            c1, c2 = st.columns([3, 1])
                            c1.error(f"🔴 {aus['nombre']}")
                            
                            if aus['whatsapp']:
                                # MENSAJE ORGANIZADO Y PROFESIONAL
                                saludo = "Cordial saludo, Sr. Padre de Familia / Acudiente."
                                cuerpo = f"Le informo que el estudiante {aus['nombre']} NO asistió hoy ({hoy}) a la clase de {ma} (Tema: {tema})."
                                despedida = f"Atentamente,\nProf. {st.session_state.profe_nom}\n{COLEGIO}"
                                
                                mensaje_completo = f"{saludo}\n\n{cuerpo}\n\n{despedida}"
                                link = f"https://wa.me/57{aus['whatsapp']}?text={urllib.parse.quote(mensaje_completo)}"
                                
                                c2.markdown(f'<a href="{link}" target="_blank"><button style="background-color:#25d366; color:white; border:none; padding:8px 15px; border-radius:5px; cursor:pointer; width:100%; font-weight:bold;">📲 Notificar</button></a>', unsafe_allow_html=True)
                            else:
                                c2.warning("Sin número")
                        st.divider()

# 4. REPORTES PDF
elif menu == "📊 Reportes":
    st.subheader("Generación de Planillas PDF")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_r = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gr, mr = sel_r.split(" | ")
        if st.button("📄 Generar Reporte Completo", type="primary"):
            estudiantes = pd.read_sql("SELECT documento, nombre FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY nombre ASC", conn, params=(gr, mr, st.session_state.user))
            asist_data = pd.read_sql("SELECT estudiante_id, fecha, tema FROM asistencia WHERE grado=? AND materia=? AND profe_id=?", conn, params=(gr, mr, st.session_state.user))
            clases = asist_data[['fecha', 'tema']].drop_duplicates().sort_values(by='fecha').values.tolist()
            
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
            ancho_pag, alto_pag = landscape(legal); margen = 1.0*cm
            if os.path.exists(ESCUDO_PATH): canv.drawImage(ESCUDO_PATH, margen, alto_pag-2.5*cm, width=2.2*cm, height=2.2*cm, mask='auto')
            
            canv.setFont("Helvetica-Bold", 14); canv.drawCentredString(ancho_pag/2, alto_pag-1.2*cm, COLEGIO)
            canv.setFont("Helvetica", 9); x_i = margen+2.5*cm
            canv.drawString(x_i, alto_pag-1.7*cm, f"Asignatura: {mr} | Grado: {gr}")
            canv.drawString(x_i, alto_pag-2.3*cm, f"Docente: {st.session_state.profe_nom}")

            w_nom, w_totales = 8.0*cm, 3.2*cm 
            espacio_libre = ancho_pag - (margen * 2) - w_nom - w_totales
            n_c = len(clases)
            w_col = min(max(espacio_libre / n_c, 1.4*cm), 3.5*cm) if n_c > 0 else 1.4*cm

            x_curr, y_cab = margen, alto_pag-4.2*cm
            h_cab = 1.2*cm 
            canv.rect(x_curr, y_cab, w_nom, h_cab)
            canv.setFont("Helvetica-Bold", 8); canv.drawCentredString(x_curr+w_nom/2, y_cab+0.5*cm, "NOMBRE DEL ESTUDIANTE")
            
            x_h = x_curr + w_nom
            for f, t in clases:
                canv.rect(x_h, y_cab, w_col, h_cab); canv.line(x_h, y_cab+0.6*cm, x_h+w_col, y_cab+0.6*cm)
                canv.setFont("Helvetica-Bold", 6); canv.drawCentredString(x_h+w_col/2, y_cab+0.85*cm, f"{t[:15]}")
                canv.setFont("Helvetica", 6); canv.drawCentredString(x_h+w_col/2, y_cab+0.25*cm, f"{f}")
                x_h += w_col
            
            canv.rect(x_h, y_cab, 1.6*cm, h_cab); canv.drawCentredString(x_h+0.8*cm, y_cab+0.5*cm, "Asist.")
            canv.rect(x_h+1.6*cm, y_cab, 1.6*cm, h_cab); canv.drawCentredString(x_h+2.4*cm, y_cab+0.5*cm, "Ausen.")
            
            h_row, y_f = 0.55*cm, y_cab-0.55*cm
            for i, est in estudiantes.iterrows():
                if y_f < margen+0.5*cm: canv.showPage(); y_f = alto_pag-3.5*cm
                canv.rect(margen, y_f, w_nom, h_row)
                canv.setFont("Helvetica", 7); canv.drawString(margen+0.1*cm, y_f+0.15*cm, f"{i+1}. {est['nombre'][:45]}")
                x_f, t_as, t_au = margen+w_nom, 0, 0
                for f, t in clases:
                    canv.rect(x_f, y_f, w_col, h_row)
                    if not asist_data[(asist_data['estudiante_id']==est['documento']) & (asist_data['fecha']==f)].empty:
                        canv.setFont("ZapfDingbats", 9); canv.drawCentredString(x_f+w_col/2, y_f+0.15*cm, "4")
                        canv.setFont("Helvetica", 7); t_as += 1
                    else: canv.drawCentredString(x_f+w_col/2, y_f+0.15*cm, "X"); t_au += 1
                    x_f += w_col
                canv.rect(x_f, y_f, 1.6*cm, h_row); canv.drawCentredString(x_f+0.8*cm, y_f+0.15*cm, str(t_as))
                canv.rect(x_f+1.6*cm, y_f, 1.6*cm, h_row); canv.drawCentredString(x_f+2.4*cm, y_f+0.15*cm, str(t_au))
                y_f -= h_row
            canv.save(); st.download_button("📥 Descargar Reporte PDF", pdf_io.getvalue(), f"Reporte_{gr}.pdf", use_container_width=True)

# 5. REINICIO
elif menu == "⚙️ Reinicio":
    if st.button("LIMPIAR BASE DE DATOS"):
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.success("Datos eliminados exitosamente."); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.session_state.captura_finalizada = False
    st.rerun()
