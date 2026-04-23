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

st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CONTROL DE ACCESO (LOGIN) ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.title(f"🔐 Acceso a {APP_NAME}")
    tab_login, tab_reg = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab_login:
        u = st.text_input("Usuario", key="user_input")
        p = st.text_input("Contraseña", type="password", key="pass_input")
        if st.button("Entrar", type="primary"):
            conn = get_connection()
            # Buscamos el nombre para guardarlo en la sesión
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
                
    with tab_reg:
        reg_nom = st.text_input("Nombre Completo")
        reg_usu = st.text_input("Crear Usuario (ID)")
        reg_pass = st.text_input("Crear Contraseña", type="password")
        if st.button("Registrar Cuenta"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_nom, reg_usu, hash_password(reg_pass)))
                conn.commit()
                st.success("✅ Registro exitoso. Ahora puedes iniciar sesión.")
            except:
                st.error("❌ El usuario ya existe.")
    st.stop()

# --- SI ESTÁ LOGUEADO, MOSTRAR EL CONTENIDO ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "⚙️ Reinicio"])
conn = get_connection()

# 1. GESTIÓN DE CURSOS
if menu == "📚 Mis Cursos":
    st.header("Mis Cursos")
    with st.form("nuevo_curso"):
        c1, c2 = st.columns(2)
        grado = c1.text_input("Grado (Ej: Sexto A)")
        materia = c2.text_input("Materia")
        if st.form_submit_button("Crear Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (grado, materia, st.session_state.user))
            conn.commit()
            st.rerun()
            
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        col_i, col_b = st.columns([5, 1])
        col_i.info(f"📖 {r['grado']} - {r['materia']}")
        if col_b.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# 2. CARGA DE EXCEL Y QRs (RESTAURADO AL 100%)
elif menu == "👤 Estudiantes":
    st.header("Carga Masiva y Generación de QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty:
        st.warning("Primero crea un curso en 'Mis Cursos'.")
    else:
        lista_cursos = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Seleccione el curso:", lista_cursos)
        g_sel, m_sel = sel.split(" | ")
        
        archivo = st.file_uploader("Cargar archivo Excel (.xlsx)", type=["xlsx"])
        if archivo:
            try:
                df = pd.read_excel(archivo, engine='openpyxl')
                # Normalización de columnas para que no falle
                df.columns = [str(c).strip().lower() for c in df.columns]
                st.dataframe(df.head(5))
                
                if st.button("Procesar Estudiantes y Generar PDF"):
                    if 'estudiante_id' in df.columns and 'nombre' in df.columns:
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x, y = 1.5*cm, h - 5*cm
                        
                        for _, row in df.iterrows():
                            eid = str(row['estudiante_id']).strip()
                            enom = str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', '')).strip()
                            
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", 
                                         (eid, enom, ews, g_sel, m_sel, st.session_state.user))
                            
                            # PROTECCIÓN QR BYTESIO
                            qr = qrcode.QRCode(version=1, box_size=10, border=1)
                            qr.add_data(eid)
                            qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                            tmp = io.BytesIO()
                            img_qr.save(tmp, format='PNG')
                            tmp.seek(0)
                            
                            canv.drawInlineImage(Image.open(tmp), x, y, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 8)
                            canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:15]} | {g_sel}")
                            
                            x += 5.2*cm
                            if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                            if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                            
                        conn.commit()
                        canv.save()
                        st.success("✅ Estudiantes registrados correctamente.")
                        st.download_button("📥 Descargar Carnets PDF", pdf_io.getvalue(), f"QRs_{g_sel}.pdf")
                    else:
                        st.error("❌ El Excel debe tener columnas 'estudiante_id' y 'nombre'.")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

# 3. ESCANEO Y WHATSAPP
elif menu == "📷 Asistencia QR":
    st.header("Asistencia por Cámara")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty:
        st.warning("No hay cursos registrados.")
    else:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # Cámara activa
        codigo = qrcode_scanner(key="scanner_v3")
        if codigo:
            id_q = str(codigo).strip()
            est = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if est:
                nom_e, f_h = est[0], datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit()
                    st.success(f"✅ {nom_e} registrado.")
            else:
                st.error("❌ Estudiante no encontrado en este curso.")

        st.divider()
        if st.button("Finalizar y Reportar Inasistencias"):
            f_h = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT documento, nombre, whatsapp FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            presentes = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_h, g_a, st.session_state.user))
            ausentes = todos[~todos['documento'].isin(presentes['estudiante_id'])]
            
            if ausentes.empty:
                st.success("🎉 Todos los estudiantes asistieron.")
            else:
                for _, aus in ausentes.iterrows():
                    tel = str(aus['whatsapp']).strip()
                    if tel and len(tel) > 5:
                        txt = f"Hola, el estudiante *{aus['nombre']}* no asistió hoy a *{m_a}*.".replace(" ", "%20")
                        st.link_button(f"📲 Notificar a {aus['nombre']}", f"https://wa.me/{tel}?text={txt}")

# BOTÓN SALIR
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
