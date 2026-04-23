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

# --- CABECERA ---
col_esc, col_tit = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(Image.open(ESCUDO_PATH), width=120)
with col_tit:
    st.title(f"🚀 {APP_NAME}")
    st.subheader(f"{COLEGIO} | Docente: {CREADOR}")
st.divider()

# --- ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Login", "📝 Registro"])
    with t1:
        u = st.text_input("Usuario", key="l_u")
        p = st.text_input("Contraseña", type="password", key="l_p")
        if st.button("Ingresar", type="primary"):
            conn = get_connection()
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("❌ Credenciales incorrectas.")
    st.stop()

# --- MENÚ ---
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Navegación", ["📚 Mis Cursos", "👤 Gestionar Estudiantes", "📷 Escanear Asistencia", "⚙️ Reinicio"])
conn = get_connection()

if menu == "📚 Mis Cursos":
    st.header("Gestión de Cursos")
    with st.form("nc"):
        c1, c2 = st.columns(2)
        g, m = c1.text_input("Grado"), c2.text_input("Materia")
        if st.form_submit_button("Añadir"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        col1, col2 = st.columns([6,1])
        col1.info(f"📖 {r['grado']} - {r['materia']}")
        if col2.button("🗑️", key=f"d_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Gestionar Estudiantes":
    st.header("Carga Masiva y QRs")
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
                # RESTAURADO: Limpieza profunda de columnas
                df.columns = [str(c).strip().lower() for c in df.columns]
                st.write("Vista previa de datos cargados:")
                st.dataframe(df.head(5))

                if st.button("Generar PDF con QRs"):
                    # Verificación robusta de columnas
                    if 'estudiante_id' in df.columns and 'nombre' in df.columns:
                        pdf_io = io.BytesIO()
                        canv = canvas.Canvas(pdf_io, pagesize=letter)
                        w, h = letter
                        x_p, y_p = 1.5*cm, h - 5*cm
                        
                        for _, row in df.iterrows():
                            eid = str(row['estudiante_id']).strip()
                            enom = str(row['nombre']).strip().upper()
                            # Capturamos whatsapp si existe, sino queda vacío
                            ews = str(row.get('whatsapp', '')).strip() if 'whatsapp' in df.columns else ""
                            
                            conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", 
                                         (eid, enom, ews, g_s, m_s, st.session_state.user))
                            
                            # PROTECCIÓN CONTRA ERROR BYTESIO
                            qr = qrcode.QRCode(version=1, box_size=10, border=1)
                            qr.add_data(eid); qr.make(fit=True)
                            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                            tmp_img = io.BytesIO(); img_qr.save(tmp_img, format='PNG'); tmp_img.seek(0)
                            
                            canv.drawInlineImage(Image.open(tmp_img), x_p, y_p, width=4*cm, height=4*cm)
                            canv.setFont("Helvetica-Bold", 8)
                            canv.drawCentredString(x_p + 2*cm, y_p - 0.5*cm, f"{enom[:15]} | {g_s}")
                            
                            x_p += 5.2*cm
                            if x_p > w - 5*cm: x_p, y_p = 1.5*cm, y_p - 6*cm
                            if y_p < 2*cm: canv.showPage(); x_p, y_p = 1.5*cm, h - 5*cm
                        
                        conn.commit(); canv.save()
                        st.success("✅ Estudiantes guardados y PDF generado.")
                        st.download_button("📥 Descargar PDF", pdf_io.getvalue(), f"QRs_{g_s}.pdf")
                    else:
                        st.error("❌ El Excel debe tener columnas llamadas 'estudiante_id' y 'nombre'.")
            except Exception as e: st.error(f"Error: {e}")

elif menu == "📷 Escanear Asistencia":
    st.header("📷 Control de Asistencia QR")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if df_c.empty: st.warning("Cree un curso primero.")
    else:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        g_a, m_a = sel_a.split(" | ")
        
        # Escáner de cámara
        id_qr = qrcode_scanner(key="scanner_asistencia")
        
        if id_qr:
            id_q = str(id_qr).strip()
            res_e = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, g_a, st.session_state.user)).fetchone()
            if res_e:
                nom_e, f_h = res_e[0], datetime.now().strftime("%Y-%m-%d")
                ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, g_a)).fetchone()
                if not ya:
                    h_a = datetime.now().strftime("%H:%M:%S")
                    conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (id_q, f_h, h_a, g_a, m_a, st.session_state.user))
                    conn.commit()
                    st.success(f"✅ Registrado: {nom_e}")
                else: st.warning(f"⚠️ {nom_e} ya registró asistencia hoy.")
            else: st.error(f"❌ Estudiante no encontrado en este curso.")

        # BOTÓN DE WHATSAPP (Solo actúa sobre los ausentes)
        st.divider()
        if st.button("Finalizar Clase y Enviar Reporte de Faltas", type="primary"):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT documento, nombre, whatsapp FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(g_a, m_a, st.session_state.user))
            asistieron = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND materia=? AND profe_id=?", conn, params=(f_hoy, g_a, m_a, st.session_state.user))
            ausentes = todos[~todos['documento'].isin(asistieron['estudiante_id'])]
            
            if ausentes.empty: st.success("✅ ¡Todos asistieron!")
            else:
                st.subheader("Ausentes detectados:")
                for _, est in ausentes.iterrows():
                    tel = str(est['whatsapp']).strip()
                    if tel and tel != "None" and len(tel) > 5:
                        msg = f"Saludos. El estudiante *{est['nombre']}* no asistió hoy a clase de *{m_a}*."
                        link = f"https://wa.me/{tel}?text={msg.replace(' ', '%20')}"
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"❌ {est['nombre']}")
                        c2.link_button("📲 Notificar", link)
                    else: st.caption(f"⚠️ {est['nombre']} no tiene número registrado.")

        st.divider()
        st.write("### Asistencia de hoy")
        f_act = datetime.now().strftime("%Y-%m-%d")
        df_h = pd.read_sql("SELECT a.hora, e.nombre FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento WHERE a.fecha = ? AND a.grado = ? AND a.profe_id = ? ORDER BY a.hora DESC", conn, params=(f_act, g_a, st.session_state.user))
        st.table(df_h)

elif menu == "⚙️ Reinicio":
    if st.checkbox("Confirmar borrado de mis datos") and st.button("LIMPIAR"):
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()
