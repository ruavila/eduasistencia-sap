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

# Importación de módulos externos
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH

# 1. CONFIGURACIÓN Y BASE DE DATOS
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")
init_db()
conn = get_connection()

# Asegurar columna 'tema' para los reportes
try:
    conn.execute("ALTER TABLE asistencia ADD COLUMN tema TEXT")
    conn.commit()
except:
    pass

# CABECERA INSTITUCIONAL
col_esc, col_txt = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=110)
with col_txt:
    st.markdown(f"<h1 style='margin:0;'>{COLEGIO}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9; font-size:1.2rem;'>{APP_NAME} | <b>Creador: Rubén Darío Ávila Sandoval</b></p>", unsafe_allow_html=True)
st.divider()

# 2. SISTEMA DE LOGIN
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso Docente")
    t1, t2 = st.tabs(["Ingresar", "Registrarse"])
    with t1:
        u = st.text_input("Usuario", key="u_log")
        p = st.text_input("Contraseña", type="password", key="p_log")
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("Contraseña o usuario incorrecto")
    with t2:
        rn, ru, rp = st.text_input("Nombre"), st.text_input("Usuario ID"), st.text_input("Contraseña", type="password")
        if st.button("Crear Cuenta", use_container_width=True):
            try:
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (rn, ru, hash_password(rp)))
                conn.commit(); st.success("Cuenta creada exitosamente")
            except: st.error("El ID de usuario ya está en uso")
    st.stop()

# 3. NAVEGACIÓN PRINCIPAL
st.sidebar.markdown(f"### 👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Reinicio"])

# --- MÓDULO 1: CURSOS ---
if menu == "📚 Mis Cursos":
    st.subheader("Gestión de Cursos")
    with st.expander("➕ Crear Nuevo Grado/Curso"):
        g, m = st.text_input("Grado (ej: 6-1)"), st.text_input("Materia")
        if st.button("Registrar Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"📖 {r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

# --- MÓDULO 2: ESTUDIANTES Y GENERACIÓN DE QR (CORREGIDO) ---
elif menu == "👤 Estudiantes":
    st.subheader("Carga y Generación de Carnets QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso destino:", op)
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Subir Excel (.xlsx)", type=["xlsx"])
        if file and st.button("Generar PDF con QRs (4x4)", use_container_width=True):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO()
            canv = canvas.Canvas(pdf_io, pagesize=letter)
            # Medidas para Hoja Carta
            width_p, height_p = letter 
            x_start, y_start = 1.5*cm, height_p - 5.5*cm
            x, y = x_start, y_start

            for _, row in df.iterrows():
                eid = str(row['estudiante_id']).strip()
                enom = str(row['nombre']).strip().upper()
                ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                
                # Guardar en DB
                conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                
                # Crear QR
                qr = qrcode.QRCode(box_size=10, border=1)
                qr.add_data(eid); qr.make(fit=True)
                img = qr.make_image().convert('RGB'); tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                
                # Dibujar en PDF (Tamaño 4x4 cm)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7)
                canv.drawCentredString(x + 2*cm, y - 0.4*cm, enom[:22])
                
                # Lógica de rejilla: 3 columnas por fila
                x += 6.5*cm 
                if x > width_p - 5*cm: # Siguiente fila
                    x = x_start
                    y -= 6*cm
                
                if y < 2*cm: # Siguiente página si se acaba el espacio
                    canv.showPage()
                    x, y = x_start, y_start
            
            conn.commit(); canv.save()
            st.success("✅ Estudiantes registrados y PDF generado.")
            st.download_button("📥 Descargar Carnets QR", pdf_io.getvalue(), f"QRs_{gs}.pdf", use_container_width=True)

# --- MÓDULO 3: ASISTENCIA (CORREGIDO PARA SCANNER) ---
elif menu == "📷 Asistencia QR":
    st.subheader("Escanear Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        ga, ma = sel_a.split(" | ")
        tema_clase = st.text_input("📌 Tema de la actividad:", placeholder="Ej: Las fracciones")
        
        if not tema_clase:
            st.info("Escriba el tema para activar la cámara.")
        else:
            codigo = qrcode_scanner(key="scanner_v10")
            if codigo:
                id_q = str(codigo).strip()
                # Buscamos con TRIM para evitar errores de espacios
                res = conn.execute("SELECT nombre FROM estudiantes WHERE TRIM(documento)=? AND grado=? AND profe_id=?", (id_q, ga, st.session_state.user)).fetchone()
                if res:
                    f_h = datetime.now().strftime("%Y-%m-%d")
                    ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, ga)).fetchone()
                    if not ya:
                        h_a = datetime.now().strftime("%H:%M:%S")
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (id_q, f_h, h_a, ga, ma, tema_clase, st.session_state.user))
                        conn.commit(); st.success(f"✅ REGISTRADO: {res[0]}")
                    else: st.warning(f"El estudiante {res[0]} ya fue registrado.")
                else: st.error(f"❌ Estudiante con ID '{id_q}' no pertenece a este grado.")

        st.divider()
        if st.button("🚀 Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, ga, st.session_state.user))
            aus = todos[~todos['documento'].astype(str).isin(pres['estudiante_id'].astype(str))]
            
            for _, e in aus.iterrows():
                tel = str(e['whatsapp']).strip().replace(".0", "")
                tel_final = "57" + tel if len(tel) == 10 else tel
                if len(tel_final) >= 12:
                    msg = f"Cordial saludo. El estudiante {e['nombre']} no asistio hoy a la clase de {ma}. Tema: {tema_clase}"
                    st.link_button(f"📲 Notificar a {e['nombre'][:15]}", f"https://api.whatsapp.com/send?phone={tel_final}&text={msg.replace(' ', '%20')}", use_container_width=True)

# --- MÓDULO 4: REPORTE ---
elif menu == "📊 Reportes":
    st.subheader("Reportes en Excel")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Ver curso:", op_r)
        gr, mr = sel_r.split(" | ")
        df_rep = pd.read_sql("SELECT a.fecha, a.hora, a.tema, e.nombre, e.documento FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.grado=? AND a.materia=? AND a.profe_id=?", conn, params=(gr, mr, st.session_state.user))
        
        if not df_rep.empty:
            st.dataframe(df_rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_rep.to_excel(writer, sheet_name='Asistencia', startrow=7, index=False)
                wb = writer.book; ws = writer.sheets['Asistencia']
                fmt = wb.add_format({'bold': True, 'size': 14})
                ws.write('A1', COLEGIO.upper(), fmt)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}")
                ws.write('A3', f"DESARROLLADOR: Rubén Darío Ávila Sandoval")
                ws.write('A4', f"GRADO: {gr} | MATERIA: {mr}")
                ws.set_column('A:E', 25)
            st.download_button("📥 Descargar Reporte", output.getvalue(), f"Reporte_{gr}.xlsx", use_container_width=True)

# --- MÓDULO 5: REINICIO (CORREGIDO CON VALIDACIÓN) ---
elif menu == "⚙️ Reinicio":
    st.subheader("⚙️ Zona de Peligro")
    st.warning("Desde aquí puede limpiar la base de datos de sus cursos y estudiantes.")
    
    with st.form("form_reinicio"):
        st.write("Para confirmar, escriba la palabra **ELIMINAR** en el recuadro y marque la casilla.")
        confirm_txt = st.text_input("Escriba la palabra de seguridad:")
        confirm_check = st.checkbox("Entiendo que esta acción no se puede deshacer.")
        
        if st.form_submit_button("BORRAR TODOS MIS DATOS", type="secondary"):
            if confirm_txt == "ELIMINAR" and confirm_check:
                conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
                conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
                conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
                conn.commit()
                st.success("🔥 Todos sus datos han sido borrados. La aplicación se reiniciará.")
                st.rerun()
            else:
                st.error("❌ Verificación fallida. Escriba la palabra correctamente y marque la casilla.")

# BOTÓN DE SALIR SIEMPRE VISIBLE
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
