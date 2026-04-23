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

# Módulos locales
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH, CREADOR

# 1. Configuración e Inicialización
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

# --- 2. SISTEMA DE ACCESO (LOGIN Y REGISTRO) ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        u = st.text_input("Usuario", key="login_user")
        p = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
                
    with tab2:
        nom = st.text_input("Nombre Completo")
        usr = st.text_input("Defina su ID de Usuario")
        cla = st.text_input("Defina su Contraseña", type="password")
        if st.button("Crear Cuenta"):
            if nom and usr and cla:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (nom, usr, hash_password(cla)))
                    conn.commit()
                    st.success("✅ Cuenta creada con éxito. Ahora puede iniciar sesión.")
                except:
                    st.error("❌ Este ID de usuario ya está registrado.")
    st.stop()

# --- 3. MENÚ DE NAVEGACIÓN ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "📊 Reportes", "⚙️ Reinicio"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.header("Gestión de Grupos")
    with st.form("nuevo_grupo"):
        c1, c2 = st.columns(2)
        grado = c1.text_input("Grado (ej: 1001)")
        materia = c2.text_input("Materia")
        if st.form_submit_button("Crear Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (grado, materia, st.session_state.user))
            conn.commit(); st.rerun()
    
    df_cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, fila in df_cursos.iterrows():
        col1, col2 = st.columns([6, 1])
        col1.info(f"📖 **{fila['grado']}** - {fila['materia']}")
        if col2.button("🗑️", key=f"del_{fila['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (fila['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga de Estudiantes y QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_c.empty:
        st.warning("Debe crear un curso primero en 'Mis Cursos'.")
    else:
        opciones = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        seleccion = st.selectbox("Seleccione el curso destino:", opciones)
        g_sel, m_sel = seleccion.split(" | ")
        
        archivo = st.file_uploader("Subir Excel (.xlsx)", type=["xlsx"])
        if archivo:
            try:
                # Solución al error de columnas y openpyxl
                df_al = pd.read_excel(archivo, engine='openpyxl')
                df_al.columns = [str(c).strip().lower() for c in df_al.columns]
                
                st.write("Vista previa de los datos:")
                st.dataframe(df_al.head(5))

                if st.button("Generar PDF con QRs (Visibles)"):
                    # Verificación de columnas corregida
                    if 'estudiante_id' in df_al.columns and 'nombre' in df_al.columns:
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x, y = 1.5*cm, h - 5*cm
                        
                        for _, row in df_al.iterrows():
                            eid = str(row['estudiante_id']).strip()
                            enom = str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', ''))
                            
                            # Guardar en BD
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", 
                                         (eid, enom, ews, g_sel, m_sel, st.session_state.user))
                            
                            # Solución al error de BytesIO y formato
                            qr = qrcode.QRCode(box_size=10, border=1)
                            qr.add_data(eid)
                            qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white")
                            
                            img_io = io.BytesIO()
                            img_qr.save(img_io, format="PNG")
                            img_io.seek(0)
                            
                            # Dibujar en PDF
                            canv.drawInlineImage(img_io, x, y, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 8)
                            canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:18]} | {g_sel}")
                            
                            x += 5*cm
                            if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                            if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                        
                        conn.commit()
                        canv.save()
                        st.success(f"✅ Se han procesado {len(df_al)} estudiantes.")
                        st.download_button("📥 Descargar PDF para imprimir", pdf_io.getvalue(), f"Listado_QR_{g_sel}.pdf", "application/pdf")
                    else:
                        st.error("❌ El archivo debe tener las columnas 'estudiante_id' y 'nombre'.")
            except Exception as e:
                st.error(f"Error al procesar: {e}")

elif menu == "📷 Escanear Asistencia":
    st.header("Toma de Asistencia")
    st.info("Utilice un escáner de códigos de barras o ingrese el ID manualmente.")

elif menu == "📊 Reportes":
    st.header("Reportes de Asistencia")

elif menu == "⚙️ Reinicio":
    st.header("Zona de Peligro")
    if st.checkbox("Confirmar borrado de todos mis datos registrados") and st.button("LIMPIAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.success("Datos eliminados."); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
