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
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# Configuración inicial
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CABECERA (RESTAURADA) ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=100)
    else:
        st.write("Libro 📖")
with col_tit:
    st.title(APP_NAME)
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- AUTENTICACIÓN ---
if 'logueado' not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registrarse"])
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else: st.error("Usuario o clave incorrectos")
    with t2:
        reg_n = st.text_input("Nombre Completo")
        reg_u = st.text_input("Crear Usuario")
        reg_p = st.text_input("Crear Clave", type="password")
        if st.button("Registrar Cuenta"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_n, reg_u, hash_password(reg_p)))
                conn.commit()
                st.success("¡Registro exitoso! Ahora ve a la pestaña Ingresar.")
            except: st.error("Ese nombre de usuario ya está ocupado.")
    st.stop()

# --- MENÚ PRINCIPAL ---
st.sidebar.title(f"Hola, {st.session_state.profe_nom}")
menu = st.sidebar.radio("Menú de Gestión", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])

conn = get_connection()

# --- 1. MIS CURSOS ---
if menu == "📚 Mis Cursos":
    st.header("Gestión de Grupos")
    with st.form("nuevo_curso"):
        c1, c2 = st.columns(2)
        gr = c1.text_input("Grado (ej: 601)")
        mat = c2.text_input("Materia")
        if st.form_submit_button("Añadir"):
            if gr and mat:
                conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (gr, mat, st.session_state.user))
                conn.commit()
                st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for i, r in df_c.iterrows():
        col1, col2 = st.columns([5,1])
        col1.info(f"**Grado:** {r['grado']} | **Materia:** {r['materia']}")
        if col2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# --- 2. GESTIONAR ESTUDIANTES ---
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva de Alumnos")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_c.empty:
        st.warning("Primero crea un curso en 'Mis Cursos'.")
    else:
        opc = st.selectbox("Curso para cargar alumnos:", [f"{r['grado']} | {r['materia']}" for i, r in df_c.iterrows()])
        grado_sel, materia_sel = opc.split(" | ")
        
        file = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])
        if file:
            df_al = pd.read_excel(file, engine='openpyxl')
            # Normalizar nombres de columnas para evitar el error KeyError
            df_al.columns = [c.lower().strip() for c in df_al.columns]
            st.write("Vista previa del archivo:")
            st.dataframe(df_al.head())

            if st.button("Generar PDF con QR (4x4 cm)"):
                # Verificar que existan las columnas necesarias
                columnas = df_al.columns
                if not all(k in columnas for k in ['id', 'nombre']):
                    st.error("El Excel debe tener las columnas 'id' y 'nombre'.")
                else:
                    pdf_buf = io.BytesIO()
                    canv = canvas.Canvas(pdf_buf, pagesize=letter)
                    w, h = letter
                    x_pos, y_pos = 1.5*cm, h - 5*cm
                    
                    with st.spinner("Procesando..."):
                        for _, row in df_al.iterrows():
                            est_id = str(row['id'])
                            est_nom = str(row['nombre']).upper()
                            est_ws = str(row.get('whatsapp', 'N/A')) # WhatsApp es opcional

                            # Guardar en base de datos
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)",
                                         (est_id, est_nom, est_ws, grado_sel, materia_sel, st.session_state.user))
                            
                            # Generar QR
                            qr = qrcode.make(est_id)
                            img_b = io.BytesIO(); qr.save(img_b, format="PNG"); img_b.seek(0)
                            canv.drawInlineImage(img_b, x_pos, y_pos, width=4*cm, height=4*cm)
                            
                            # Texto debajo: Iniciales + Nombre
                            letras = est_nom.split()
                            iniciales = "".join([l[0] for l in letras[1:]]) if len(letras)>1 else ""
                            etiqueta = f"{iniciales} {letras[0]} | {grado_sel}"
                            
                            canv.setFont("Helvetica-Bold", 7)
                            canv.drawCentredString(x_pos + 2*cm, y_pos - 0.4*cm, etiqueta)
                            canv.setFont("Helvetica", 6)
                            canv.drawCentredString(x_pos + 2*cm, y_pos - 0.8*cm, materia_sel)
                            
                            # Organizar cuadrícula en la hoja
                            x_pos += 5*cm
                            if x_pos > w - 5*cm:
                                x_pos = 1.5*cm
                                y_pos -= 6*cm
                            if y_pos < 2*cm:
                                canv.showPage()
                                x_pos, y_pos = 1.5*cm, h - 5*cm
                    
                    conn.commit()
                    canv.save()
                    st.success("Estudiantes registrados en la base de datos.")
                    st.download_button("📥 Descargar PDF de QRs", pdf_buf.getvalue(), f"QR_{grado_sel}.pdf", "application/pdf")

# --- REINICIO (SOLICITADO) ---
elif menu == "⚙️ Reinicio":
    st.header("Reinicio del Sistema")
    st.warning("⚠️ Esto borrará todos tus cursos, estudiantes y registros de asistencia.")
    confirma = st.checkbox("Entiendo que esta acción no se puede deshacer.")
    if confirma:
        if st.button("BORRAR TODO MI CONTENIDO", type="secondary"):
            conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
            conn.commit()
            st.success("Sistema reiniciado con éxito.")
            st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
