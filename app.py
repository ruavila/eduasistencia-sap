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

# Importación de módulos locales
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# Inicialización
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CABECERA ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
with col_tit:
    st.title(f"🚀 {APP_NAME}")
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- SISTEMA DE ACCESO (RESTAURADO) ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else:
                st.error("❌ Usuario o clave incorrectos.")
                
    with tab2:
        nom = st.text_input("Nombre Completo")
        usr = st.text_input("Nuevo Usuario")
        cla = st.text_input("Nueva Contraseña", type="password")
        if st.button("Crear Cuenta"):
            if nom and usr and cla:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (nom, usr, hash_password(cla)))
                    conn.commit()
                    st.success("✅ Registro exitoso. Ahora puede iniciar sesión.")
                except:
                    st.error("❌ El usuario ya existe.")
    st.stop()

# --- MENÚ PRINCIPAL ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.header("Mis Grupos")
    with st.form("nuevo_c"):
        c1, c2 = st.columns(2)
        g, m = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Añadir"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        st.info(f"📖 {r['grado']} - {r['materia']}")

elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga y Generación de QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty:
        st.warning("Cree un curso primero.")
    else:
        opc = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        grado_sel, materia_sel = opc.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        
        if file:
            try:
                # Limpieza de columnas para evitar error de image_b36989.png
                df_al = pd.read_excel(file, engine='openpyxl')
                df_al.columns = [str(c).strip().lower() for c in df_al.columns]
                st.write("Vista previa:")
                st.dataframe(df_al.head(5))

                if st.button("Generar PDF con QRs"):
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_buf = io.BytesIO()
                        canv = canvas.Canvas(pdf_buf, pagesize=letter)
                        w, h = letter
                        x, y = 1.5*cm, h - 5*cm
                        
                        for _, row in df_al.iterrows():
                            eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', ''))
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, grado_sel, materia_sel, st.session_state.user))
                            
                            # Generación segura de QR para evitar error de image_b4479d.png
                            qr = qrcode.QRCode(box_size=10, border=1)
                            qr.add_data(eid); qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white")
                            img_io = io.BytesIO()
                            img_qr.save(img_io, format="PNG")
                            img_io.seek(0)
                            
                            canv.drawInlineImage(img_io, x, y, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 7)
                            canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:20]} | {grado_sel}")
                            
                            x += 5*cm
                            if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                            if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                        
                        conn.commit(); canv.save()
                        st.success("✅ ¡PDF Generado!")
                        st.download_button("📥 Descargar PDF", pdf_buf.getvalue(), f"QRs_{grado_sel}.pdf")
            except Exception as e: st.error(f"Error: {e}")

elif menu == "📷 Escanear Asistencia":
    st.header("Escaneo de Códigos")
    st.info("Utilice un lector o la cámara para registrar asistencia.")

elif menu == "📊 Reportes":
    st.header("Reportes de Asistencia")

elif menu == "⚙️ Reinicio":
    if st.checkbox("Confirmar borrado") and st.button("BORRAR DATOS"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
