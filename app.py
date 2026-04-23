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

# Configuración de página e inicialización de DB
st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- CABECERA ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
    else:
        st.info("Logo 📖")

with col_tit:
    st.title(f"🚀 {APP_NAME}")
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- GESTIÓN DE SESIÓN ---
if 'logueado' not in st.session_state: 
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab_l, tab_r = st.tabs(["🔐 Ingresar", "📝 Registrar Profesor"])
    with tab_l:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Iniciar Sesión", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else: 
                st.error("❌ Credenciales incorrectas.")
    with tab_r:
        reg_n = st.text_input("Nombre y Apellido")
        reg_u = st.text_input("ID de Usuario")
        reg_p = st.text_input("Contraseña", type="password")
        if st.button("Registrarse"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_n, reg_u, hash_password(reg_p)))
                conn.commit()
                st.success("✅ Cuenta creada con éxito. Ahora puedes ingresar.")
            except: 
                st.error("❌ El usuario ya existe.")
    st.stop()

# --- MENÚ DE NAVEGACIÓN ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])

conn = get_connection()

# --- SECCIÓN 1: MIS CURSOS ---
if menu == "📚 Mis Cursos":
    st.header("Gestión de Grupos y Materias")
    with st.form("form_curso"):
        c1, c2 = st.columns(2)
        gr = c1.text_input("Grado (ej: 601)")
        mat = c2.text_input("Materia")
        if st.form_submit_button("Crear Curso"):
            if gr and mat:
                conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (gr, mat, st.session_state.user))
                conn.commit()
                st.rerun()
    
    st.subheader("Cursos Registrados")
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for i, r in df_c.iterrows():
        c1, c2 = st.columns([5,1])
        c1.info(f"📖 **{r['grado']}** - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# --- SECCIÓN 2: GESTIONAR ESTUDIANTES ---
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva de Alumnos")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_c.empty:
        st.warning("Debe crear al menos un curso primero.")
    else:
        opc = st.selectbox("Seleccione el curso destino:", [f"{r['grado']} | {r['materia']}" for i, r in df_c.iterrows()])
        grado_sel, materia_sel = opc.split(" | ")
        
        file = st.file_uploader("Subir Excel (estudiante_id, nombre, whatsapp)", type=["xlsx"])
        if file:
            try:
                # Lectura forzando el motor openpyxl
                df_al = pd.read_excel(file, engine='openpyxl')
                df_al.columns = [str(c).strip().lower() for c in df_al.columns]
                
                st.write("✅ Archivo cargado. Vista previa (5 primeros):")
                st.dataframe(df_al.head(5))

                if st.button("Generar PDF con TODOS los Códigos QR (4x4 cm)"):
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_buf = io.BytesIO()
                        canv = canvas.Canvas(pdf_buf, pagesize=letter)
                        w, h = letter
                        x_in, y_in = 1.5*cm, h - 5*cm
                        
                        progreso = st.progress(0)
                        total_est = len(df_al)
                        
                        for idx, row in df_al.iterrows():
                            eid = str(row['estudiante_id']).strip()
                            enom = str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', ''))

                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)",
                                         (eid, enom, ews, grado_sel, materia_sel, st.session_state.user))
                            
                            # CORRECCIÓN TÉCNICA DEL QR
                            qr_img = qrcode.make(eid)
                            img_b = io.BytesIO()
                            qr_img.save(img_b, format="PNG") # Se especifica el formato aquí
                            img_b.seek(0)
                            canv.drawInlineImage(img_b, x_in, y_in, width=4*cm, height=4*cm)
                            
                            nombres = enom.split()
                            nombre_principal = nombres[0]
                            iniciales = "".join([n[0] for n in nombres[1:]]) if len(nombres) > 1 else ""
                            texto_qr = f"{iniciales} {nombre_principal} | {grado_sel}"
                            
                            canv.setFont("Helvetica-Bold", 7)
                            canv.drawCentredString(x_in + 2*cm, y_in - 0.4*cm, texto_qr)
                            canv.setFont("Helvetica", 6)
                            canv.drawCentredString(x_in + 2*cm, y_in - 0.8*cm, materia_sel)
                            
                            x_in += 5*cm
                            if x_in > w - 5*cm:
                                x_in = 1.5*cm
                                y_in -= 6*cm
                            if y_in < 2*cm:
                                canv.showPage()
                                x_in, y_in = 1.5*cm, h - 5*cm
                            
                            progreso.progress((idx + 1) / total_est)
                        
                        conn.commit()
                        canv.save()
                        st.success(f"✅ Se han procesado {total_est} estudiantes correctamente.")
                        st.download_button("📥 Descargar PDF de QRs", pdf_buf.getvalue(), f"QR_{grado_sel}.pdf", "application/pdf")
                    else:
                        st.error("❌ El Excel debe tener las columnas: 'estudiante_id' y 'nombre'.")
            except Exception as e:
                st.error(f"Error técnico: {e}")

# --- SECCIÓN REINICIO ---
elif menu == "⚙️ Reinicio":
    st.header("Limpieza del Sistema")
    confirmar = st.checkbox("Confirmo que deseo eliminar toda mi información.")
    if confirmar and st.button("REINICIAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit()
        st.success("Sistema limpio.")
        st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
