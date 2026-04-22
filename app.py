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

# --- CABECERA (ESCUDO Y TÍTULO RESTAURADOS) ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    # Busca el escudo en assets/escudo.png según tu configuración
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
    else:
        st.info("Subir escudo a assets/")

with col_tit:
    st.title(f"🚀 {APP_NAME}")
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- AUTENTICACIÓN ---
if 'logueado' not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registrar Profesor"])
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else: st.error("❌ Credenciales incorrectas.")
    with t2:
        reg_n = st.text_input("Nombre y Apellido")
        reg_u = st.text_input("ID de Usuario")
        reg_p = st.text_input("Contraseña", type="password")
        if st.button("Registrarse"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_n, reg_u, hash_password(reg_p)))
                conn.commit()
                st.success("✅ Cuenta creada con éxito.")
            except: st.error("❌ El usuario ya existe.")
    st.stop()

# --- MENÚ PRINCIPAL ---
st.sidebar.title(f"Hola, {st.session_state.profe_nom}")
menu = st.sidebar.radio("Menú", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])

conn = get_connection()

# --- 1. MIS CURSOS ---
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
    
    st.subheader("Tus Cursos:")
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for i, r in df_c.iterrows():
        c1, c2 = st.columns([5,1])
        c1.info(f"📖 **{r['grado']}** - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# --- 2. GESTIONAR ESTUDIANTES ---
elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva de Estudiantes")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_c.empty:
        st.warning("Debe crear al menos un curso primero.")
    else:
        opc = st.selectbox("Seleccione el curso:", [f"{r['grado']} | {r['materia']}" for i, r in df_c.iterrows()])
        grado_sel, materia_sel = opc.split(" | ")
        
        file = st.file_uploader("Subir Excel (estudiante_id, nombre, whatsapp)", type=["xlsx"])
        if file:
            try:
                df_al = pd.read_excel(file, engine='openpyxl')
                st.write("Vista previa de los datos:")
                st.dataframe(df_al.head())

                if st.button("Generar PDF con Códigos QR (4x4 cm)"):
                    # Verificar nombres de columnas exactos
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_buf = io.BytesIO()
                        canv = canvas.Canvas(pdf_buf, pagesize=letter)
                        w, h = letter
                        x_in, y_in = 1.5*cm, h - 5*cm
                        
                        for _, row in df_al.iterrows():
                            eid = str(row['estudiante_id'])
                            enom = str(row['nombre']).upper()
                            ews = str(row.get('whatsapp', ''))

                            # Guardar en Base de Datos
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)",
                                         (eid, enom, ews, grado_sel, materia_sel, st.session_state.user))
                            
                            # Crear QR 4x4 cm
                            qr_img = qrcode.make(eid)
                            img_b = io.BytesIO(); qr_img.save(img_b, format="PNG"); img_b.seek(0)
                            canv.drawInlineImage(img_b, x_in, y_in, width=4*cm, height=4*cm)
                            
                            # Texto: Iniciales + Nombre y Grado
                            partes = enom.split()
                            iniciales = "".join([p[0] for p in partes[1:]]) if len(partes)>1 else ""
                            etiqueta = f"{iniciales} {partes[0]} | {grado_sel}"
                            
                            canv.setFont("Helvetica-Bold", 7)
                            canv.drawCentredString(x_in + 2*cm, y_in - 0.4*cm, etiqueta)
                            canv.setFont("Helvetica", 6)
                            canv.drawCentredString(x_in + 2*cm, y_in - 0.8*cm, materia_sel)
                            
                            # Movimiento de cuadrícula en papel carta
                            x_in += 5*cm
                            if x_in > w - 5*cm:
                                x_in = 1.5*cm
                                y_in -= 6*cm
                            if y_in < 2*cm:
                                canv.showPage()
                                x_in, y_in = 1.5*cm, h - 5*cm
                        
                        conn.commit()
                        canv.save()
                        st.success("✅ Estudiantes registrados y PDF listo.")
                        st.download_button("📥 Descargar PDF para Imprimir", pdf_buf.getvalue(), f"QR_{grado_sel}.pdf", "application/pdf")
                    else:
                        st.error("❌ El Excel debe tener las columnas exactas: 'estudiante_id' y 'nombre'.")
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

# --- 3. REINICIO ---
elif menu == "⚙️ Reinicio":
    st.header("Limpieza del Sistema")
    st.error("CUIDADO: Esto eliminará todos tus cursos y estudiantes registrados.")
    confirmar = st.checkbox("Confirmo que deseo borrar toda mi información.")
    if confirmar:
        if st.button("REINICIAR TODO"):
            conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
            conn.commit()
            st.success("Sistema reiniciado.")
            st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
