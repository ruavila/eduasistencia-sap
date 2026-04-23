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

# --- CONTROL DE ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.title(f"🔐 Acceso a {APP_NAME}")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        u = st.text_input("Usuario", key="u_log")
        p = st.text_input("Contraseña", type="password", key="p_log")
        if st.button("Entrar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("❌ Credenciales incorrectas.")
                
    with tab_reg:
        st.subheader("Crear nueva cuenta")
        reg_nom = st.text_input("Nombre Completo")
        reg_usu = st.text_input("ID de Usuario")
        reg_pass = st.text_input("Contraseña", type="password")
        if st.button("Registrar Cuenta"):
            if reg_nom and reg_usu and reg_pass:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (reg_nom, reg_usu, hash_password(reg_pass)))
                    conn.commit(); st.success("✅ Registro exitoso.")
                except: st.error("❌ El usuario ya existe.")
    st.stop()

# --- CONTENIDO PRINCIPAL ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Reinicio"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.header("Gestión de Cursos")
    with st.form("nc"):
        c1, c2 = st.columns(2)
        g, m = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in cursos.iterrows():
        col_i, col_b = st.columns([6,1])
        col_i.info(f"📖 {r['grado']} - {r['materia']}")
        if col_b.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.header("Carga de Estudiantes y QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Curso destino:", op)
        g_s, m_s = sel.split(" | ")
        file = st.file_uploader("Subir Excel", type=["xlsx"])
        if file:
            try:
                df = pd.read_excel(file, engine='openpyxl')
                df.columns = [str(c).strip().lower() for c in df.columns]
                st.dataframe(df.head(5))
                if st.button("Generar PDF con QRs"):
                    if 'estudiante_id' in df.columns and 'nombre' in df.columns:
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x, y = 1.5*cm, h - 5*cm
                        for _, row in df.iterrows():
                            eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                            ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, g_s, m_s, st.session_state.user))
                            
                            qr = qrcode.QRCode(version=1, box_size=10, border=1)
                            qr.add_data(eid); qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                            tmp = io.BytesIO(); img_qr.save(tmp, format='PNG'); tmp.seek(0)
                            
                            canv.drawInlineImage(Image.open(tmp), x, y, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 8); canv.drawCentredString(x + 2*cm, y - 0.5*cm, f"{enom[:15]} | {g_s}")
                            x += 5.2*cm
                            if x > w - 5*cm: x, y = 1.5*cm, y - 6*cm
                            if y < 2*cm: canv.showPage(); x, y = 1.5*cm, h - 5*cm
                        conn.commit(); canv.save()
                        st.success("✅ Guardado."); st.download_button("📥 Descargar QRs", pdf_io.getvalue(), f"QRs_{g_s}.pdf")
            except Exception as e: st.error(f"Error: {e}")

elif menu == "📷 Asistencia QR":
    st.header("Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        id_qr = qrcode_scanner(key="scanner_vfinal") # Visor de cámara
        if id_qr:
            id_q = str(id_qr).strip()
            res = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if res:
                nom_e, f_h = res[0], datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit(); st.success(f"✅ {nom_e} registrado.")

        st.divider()
        if st.button("Finalizar y Reportar Inasistencias", type="primary"):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT documento, nombre, whatsapp FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            asistieron = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, g_a, st.session_state.user))
            ausentes = todos[~todos['documento'].isin(asistieron['estudiante_id'])]
            
            if ausentes.empty: st.success("🎉 Todos presentes.")
            else:
                st.subheader(f"Inasistencias: {len(ausentes)}")
                for _, est in ausentes.iterrows():
                    tel = str(est['whatsapp']).strip().replace(".0", "")
                    if len(tel) == 10: tel_final = "57" + tel
                    else: tel_final = tel
                    
                    if len(tel_final) >= 12:
                        txt = f"Cordial saludo. El estudiante {est['nombre']} no asistio hoy a la clase de {m_a}."
                        # Link directo a WhatsApp Web/App
                        url_ws = f"https://api.whatsapp.com/send?phone={tel_final}&text={txt.replace(' ', '%20')}"
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"❌ {est['nombre']} ({tel_final})")
                        c2.link_button("📲 Notificar", url_ws)
                    else: st.caption(f"⚠️ {est['nombre']} sin número válido.")

        st.divider()
        st.write("### Registrados hoy")
        f_act = datetime.now().strftime("%Y-%m-%d")
        df_h = pd.read_sql("SELECT a.hora, e.nombre FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.fecha = ? AND a.grado = ? AND a.profe_id = ? ORDER BY a.hora DESC", conn, params=(f_act, g_a, st.session_state.user))
        st.table(df_h)

elif menu == "📊 Reportes":
    st.header("Historial de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("No hay datos disponibles.")
    else:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Filtrar por curso:", op_r)
        g_r, m_r = sel_r.split(" | ")
        
        df_rep = pd.read_sql("""SELECT a.fecha, a.hora, e.nombre, e.documento 
                                FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                WHERE a.grado = ? AND a.materia = ? AND a.profe_id = ? 
                                ORDER BY a.fecha DESC, a.hora DESC""", conn, params=(g_r, m_r, st.session_state.user))
        
        if not df_rep.empty:
            st.dataframe(df_rep, use_container_width=True)
            csv = df_rep.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Reporte CSV", csv, f"Reporte_{g_r}.csv", "text/csv")
        else: st.info("No se han registrado asistencias para este curso aún.")

elif menu == "⚙️ Reinicio":
    if st.checkbox("Confirmar borrado") and st.button("BORRAR TODO"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Salir"):
    st.session_state.logueado = False; st.rerun()
