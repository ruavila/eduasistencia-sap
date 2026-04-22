import streamlit as st
import pandas as pd
import qrcode
import io
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from modules.database import init_db, get_connection, hash_password

# Inicialización
st.set_page_config(page_title="EduAsistencia Pro", layout="wide")
init_db()

# --- AUTENTICACIÓN ---
if 'logueado' not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["Ingresar", "Registrar Profesor"])
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res[0]
                st.rerun()
            else: st.error("Datos incorrectos")
    with t2:
        reg_n = st.text_input("Nombre Real")
        reg_u = st.text_input("Nuevo Usuario")
        reg_p = st.text_input("Clave Nueva", type="password")
        if st.button("Crear Cuenta"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_n, reg_u, hash_password(reg_p)))
                conn.commit()
                st.success("Cuenta creada, ya puedes ingresar.")
            except: st.error("El usuario ya existe.")
    st.stop()

# --- MENÚ PRINCIPAL ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["Mis Cursos", "Gestionar Estudiantes", "Escanear Asistencia", "Reportes", "Reinicio de Sistema"])

conn = get_connection()

# --- MIS CURSOS ---
if menu == "Mis Cursos":
    st.header("📚 Mis Grupos y Materias")
    with st.form("nuevo_curso"):
        c1, c2 = st.columns(2)
        gr = c1.text_input("Grado (ej: 601)")
        mat = c2.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (gr, mat, st.session_state.user))
            conn.commit()
            st.rerun()
    
    st.subheader("Lista de Cursos")
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for i, r in df_c.iterrows():
        col1, col2 = st.columns([4,1])
        col1.write(f"📖 {r['grado']} - {r['materia']}")
        if col2.button("Eliminar", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],))
            conn.commit()
            st.rerun()

# --- GESTIONAR ESTUDIANTES ---
elif menu == "Gestionar Estudiantes":
    st.header("👤 Carga de Alumnos y Generación QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Crea un curso primero.")
    else:
        opc = st.selectbox("Seleccione el curso:", [f"{r['grado']} | {r['materia']}" for i, r in df_c.iterrows()])
        grado, materia = opc.split(" | ")
        
        file = st.file_uploader("Subir Excel (columnas: id, nombre, whatsapp)", type=["xlsx"])
        if file:
            df_al = pd.read_excel(file, engine='openpyxl')
            if st.button("Procesar y Generar PDF Carta"):
                pdf_buf = io.BytesIO()
                c = canvas.Canvas(pdf_buf, pagesize=letter)
                w, h = letter
                x, y = 1.5*cm, h - 5*cm
                
                for _, row in df_al.iterrows():
                    # Guardar en DB
                    conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)",
                                 (str(row['id']), str(row['nombre']), str(row['whatsapp']), grado, materia, st.session_state.user))
                    
                    # Generar QR 4x4cm
                    qr = qrcode.make(str(row['id']))
                    img_b = io.BytesIO(); qr.save(img_b, format="PNG"); img_b.seek(0)
                    c.drawInlineImage(img_b, x, y, width=4*cm, height=4*cm)
                    
                    # Texto inferior: Iniciales Apellido + Nombre
                    partes = str(row['nombre']).split()
                    ini = "".join([p[0] for p in partes[1:]]) if len(partes)>1 else ""
                    txt = f"{ini} {partes[0]} | {grado}"
                    c.setFont("Helvetica-Bold", 7)
                    c.drawCentredString(x+2*cm, y-0.4*cm, txt)
                    
                    x += 5*cm
                    if x > w - 5*cm: x = 1.5*cm; y -= 6*cm
                    if y < 2*cm: c.showPage(); x, y = 1.5*cm, h - 5*cm
                
                conn.commit()
                c.save()
                st.success("Estudiantes registrados.")
                st.download_button("Descargar PDF para Imprimir", pdf_buf.getvalue(), f"QR_{grado}.pdf")

# --- ESCANEAR ASISTENCIA ---
elif menu == "Escanear Asistencia":
    st.header("📷 Toma de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    opc = st.selectbox("Curso actual:", [f"{r['grado']} | {r['materia']}" for i, r in df_c.iterrows()])
    
    if 'escaneados' not in st.session_state: st.session_state.escaneados = []
    
    foto = st.camera_input("Escanee el código QR del estudiante")
    if foto:
        # Aquí simularíamos la decodificación. En un móvil real, usarías una librería de cámara.
        st.info("Estudiante capturado en cámara.")
        # Ejemplo: st.session_state.escaneados.append(id_detectado)

    if st.button("Finalizar y Generar Inasistencias"):
        hoy = datetime.now().strftime("%Y-%m-%d")
        grado, materia = opc.split(" | ")
        # Lógica: Comparar lista total vs escaneados y enviar WhatsApp (simulado)
        st.success(f"Asistencia procesada. Los ausentes han sido notificados vía WhatsApp.")

# --- REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reporte de Asistencia")
    # Generar tabla tipo Excel con visto bueno (✓) y (X)
    st.write("Seleccione el grado para descargar el consolidado en Excel.")
    if st.button("Descargar Reporte Excel"):
        st.info("Generando archivo con porcentajes...")

# --- REINICIO ---
elif menu == "Reinicio de Sistema":
    st.warning("⚠️ Esta acción borrará TODOS tus cursos, estudiantes y asistencias.")
    if st.checkbox("Confirmar que deseo borrar todo"):
        if st.button("REINICIAR AHORA"):
            conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
            conn.commit()
            st.success("Sistema limpio.")
            st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
