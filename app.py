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

# Configuración de página optimizada
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")
init_db()

# --- CABECERA ATRACTIVA Y PERSONALIZADA ---
# Usamos columnas para que el escudo y el texto se vean alineados
col_escudo, col_texto = st.columns([1, 5])

with col_escudo:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=120)
    else:
        st.info("Escudo")

with col_texto:
    # Nombre de la Institución y Aplicación
    st.markdown(f"<h1 style='margin-bottom: 0;'>{COLEGIO}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0; color: #4F8BF9;'>{APP_NAME}</h3>", unsafe_allow_html=True)
    # Nombre del Creador
    st.markdown(f"**Desarrollado por:** Rubén Darío Ávila Sandoval")

st.divider()

# --- CONTROL DE ACCESO (LOGIN / REGISTRO) ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso al Sistema")
    tab_login, tab_reg = st.tabs(["Iniciar Sesión", "Registrar Nuevo Docente"])
    
    with tab_login:
        u = st.text_input("Usuario", key="user_login")
        p = st.text_input("Contraseña", type="password", key="pass_login")
        if st.button("Ingresar", type="primary", use_container_width=True):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
                
    with tab_reg:
        r_nom = st.text_input("Nombre Completo del Docente")
        r_usu = st.text_input("Definir Usuario (ID)")
        r_pas = st.text_input("Definir Contraseña", type="password")
        if st.button("Crear Cuenta", use_container_width=True):
            if r_nom and r_usu and r_pas:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (r_nom, r_usu, hash_password(r_pas)))
                    conn.commit()
                    st.success("Cuenta creada exitosamente. Ya puede iniciar sesión.")
                except:
                    st.error("El ID de usuario ya existe.")
    st.stop()

# --- MENÚ DE NAVEGACIÓN ---
st.sidebar.markdown(f"### Bienvenido, \n**{st.session_state.profe_nom}**")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes"])
conn = get_connection()

# 1. GESTIÓN DE CURSOS
if menu == "📚 Mis Cursos":
    st.subheader("Gestión de Cursos")
    with st.expander("➕ Agregar Nuevo Curso"):
        grado = st.text_input("Grado / Grupo")
        materia = st.text_input("Asignatura")
        if st.button("Guardar Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (grado, materia, st.session_state.user))
            conn.commit()
            st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"**Grado:** {r['grado']} | **Materia:** {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# 2. GESTIÓN DE ESTUADIANTES Y QR
elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty:
        st.warning("Primero debe crear un curso.")
    else:
        lista_c = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Seleccione el curso destino:", lista_c)
        g_sel, m_sel = sel.split(" | ")
        
        archivo = st.file_uploader("Cargar Excel (.xlsx)", type=["xlsx"])
        if archivo:
            df = pd.read_excel(archivo)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if st.button("Procesar y Generar PDF de Carnets", use_container_width=True):
                pdf_io = io.BytesIO()
                canv = canvas.Canvas(pdf_io, pagesize=letter)
                w, h = letter
                x, y = 1.5*cm, h - 5*cm
                
                for _, row in df.iterrows():
                    eid = str(row['estudiante_id']).strip()
                    enom = str(row['nombre']).strip().upper()
                    ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                    
                    conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", 
                                 (eid, enom, ews, g_sel, m_sel, st.session_state.user))
                    
                    # Generación de QR
                    qr = qrcode.QRCode(box_size=10, border=1)
                    qr.add_data(eid)
                    qr.make(fit=True)
                    img = qr.make_image().convert('RGB')
                    tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                    
                    canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                    canv.setFont("Helvetica-Bold", 7)
                    canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:20]}")
                    x += 5.5*cm
                    if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                    if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                
                conn.commit()
                canv.save()
                st.success("Estudiantes registrados.")
                st.download_button("📥 Descargar Carnets QR", pdf_io.getvalue(), f"QRs_{g_sel}.pdf", use_container_width=True)

# 3. ASISTENCIA QR (CÁMARA)
elif menu == "📷 Asistencia QR":
    st.subheader("Registro de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # Scanner optimizado para móviles
        id_qr = qrcode_scanner(key="scanner_pro_v5")
        if id_qr:
            id_q = str(id_qr).strip()
            res = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if res:
                f_h = datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit()
                    st.success(f"✅ {res[0]} registrado")

        # Notificación WhatsApp
        st.divider()
        if st.button("Finalizar y Notificar Ausencias", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, g_a, st.session_state.user))
            ausentes = todos[~todos['documento'].isin(pres['estudiante_id'])]
            
            for _, est in ausentes.iterrows():
                tel = str(est['whatsapp']).strip().replace(".0", "")
                if len(tel) == 10: tel = "57" + tel
                if len(tel) >= 12:
                    msg = f"Cordial saludo. El estudiante {est['nombre']} no asistio hoy a la clase de {m_a}."
                    url = f"https://api.whatsapp.com/send?phone={tel}&text={msg.replace(' ', '%20')}"
                    st.link_button(f"📲 Notificar a {est['nombre']}", url, use_container_width=True)

# 4. REPORTES DETALLADOS
elif menu == "📊 Reportes":
    st.subheader("Historial de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Ver reporte de:", op_r)
        g_r, m_r = sel_r.split(" | ")
        
        # Obtener todas las fechas registradas para este curso
        fechas = pd.read_sql("SELECT DISTINCT fecha FROM asistencia WHERE grado=? AND materia=? AND profe_id=? ORDER BY fecha ASC", 
                            conn, params=(g_r, m_r, st.session_state.user))
        
        if not fechas.empty:
            # Lista base de estudiantes
            estudiantes = pd.read_sql("SELECT documento, nombre FROM estudiantes WHERE grado=? AND materia=? AND profe_id=? ORDER BY nombre ASC", 
                                     conn, params=(g_r, m_r, st.session_state.user))
            
            # Generar matriz de asistencia
            for _, f_row in fechas.iterrows():
                f_act = f_row['fecha']
                asistencias_f = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND materia=? AND profe_id=?", 
                                           conn, params=(f_act, g_r, m_r, st.session_state.user))
                estudiantes[f_act] = estudiantes['documento'].apply(lambda x: "✓ Asistió" if x in asistencias_f['estudiante_id'].values else "X No Asistió")
            
            st.dataframe(estudiantes, use_container_width=True)
            
            # Exportación a Excel Profesional
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                estudiantes.to_excel(writer, sheet_name='Asistencia', startrow=7, index=False)
                wb = writer.book
                ws = writer.sheets['Asistencia']
                
                # Formatos
                f_tit = wb.add_format({'bold': True, 'size': 14, 'font_color': '#1f4e78'})
                f_sub = wb.add_format({'size': 11})
                
                # Encabezados en el Excel
                ws.write('A1', COLEGIO.upper(), f_tit)
                ws.write('A2', f"PROYECTO: {APP_NAME}", f_sub)
                ws.write('A3', f"DOCENTE: {st.session_state.profe_nom}", f_sub)
                ws.write('A4', f"DESARROLLADOR: Rubén Darío Ávila Sandoval", f_sub)
                ws.write('A5', f"ASIGNATURA: {m_r} | GRADO: {g_r}", f_sub)
                ws.write('A6', f"FECHA REPORTE: {datetime.now().strftime('%d/%m/%Y %H:%M')}", f_sub)
                
                ws.set_column('A:Z', 18)
            
            st.download_button("📥 Descargar Reporte Completo (Excel)", output.getvalue(), f"Reporte_{g_r}.xlsx", use_container_width=True)
        else:
            st.info("No hay registros de asistencia para este curso.")

# BOTÓN DE SALIR
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
