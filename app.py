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

# Importación de módulos existentes
from modules.database import init_db, get_connection, hash_password
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()

# Asegurar que la columna 'tema' exista en la base de datos
conn = get_connection()
try:
    conn.execute("ALTER TABLE asistencia ADD COLUMN tema TEXT")
    conn.commit()
except:
    pass # La columna ya existe

# CABECERA VISUAL
col_escudo, col_texto = st.columns([1, 4])
with col_escudo:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_texto:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9; font-weight:bold;'>{APP_NAME} | Desarrollado por: Rubén Darío Ávila Sandoval</p>", unsafe_allow_html=True)
st.divider()

# 2. CONTROL DE ACCESO
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.subheader("🔐 Acceso al Sistema")
    t1, t2 = st.tabs(["Ingresar", "Registrar"])
    with t1:
        u = st.text_input("Usuario", key="u_ing")
        p = st.text_input("Contraseña", type="password", key="p_ing")
        if st.button("Entrar", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("Error de acceso")
    with t2:
        rn, ru, rp = st.text_input("Nombre"), st.text_input("ID"), st.text_input("Pass", type="password")
        if st.button("Crear", use_container_width=True):
            try:
                conn.execute("INSERT INTO usuarios (nombre, usuario, password) VALUES (?,?,?)", (rn, ru, hash_password(rp)))
                conn.commit(); st.success("Creado")
            except: st.error("ID ya existe")
    st.stop()

# 3. NAVEGACIÓN
st.sidebar.title(f"👨‍🏫 {st.session_state.profe_nom}")
menu = st.sidebar.radio("Menú", ["📚 Cursos", "👤 Estudiantes", "📷 Asistencia QR", "📊 Reportes", "⚙️ Salir"])

if menu == "📚 Cursos":
    st.subheader("Mis Cursos")
    with st.expander("➕ Nuevo Curso"):
        g, m = st.text_input("Grado"), st.text_input("Materia")
        if st.button("Añadir"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"{r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga y QRs")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel = st.selectbox("Elegir Curso:", op)
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Subir Excel (.xlsx)", type=["xlsx"])
        if file and st.button("Generar QRs", use_container_width=True):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            x, y = 1.5*cm, 22*cm
            for _, row in df.iterrows():
                eid, enom = str(row['estudiante_id']).strip(), str(row['nombre']).strip().upper()
                ews = str(row.get('whatsapp', '')).strip().replace(".0", "")
                conn.execute("INSERT OR REPLACE INTO estudiantes (documento, nombre, whatsapp, grado, materia, profe_id) VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(eid); qr.make(fit=True)
                img = qr.make_image().convert('RGB'); tmp = io.BytesIO(); img.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.drawString(x, y-0.5*cm, enom[:20])
                x += 5.5*cm
                if x > 15*cm: x, y = 1.5*cm, y-6*cm
            conn.commit(); canv.save()
            st.download_button("📥 Descargar PDF", pdf_io.getvalue(), f"Carnets_{gs}.pdf", use_container_width=True)

elif menu == "📷 Asistencia QR":
    st.subheader("📷 Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_a = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_a = st.selectbox("Curso actual:", op_a)
        ga, ma = sel_a.split(" | ")
        
        # Campo de Tema - Obligatorio para activar cámara
        tema_hoy = st.text_input("📌 Tema de la clase:", placeholder="Escriba el tema aquí...", key="tema_clase")
        
        if not tema_hoy:
            st.warning("Escriba el tema para iniciar el escaner.")
        else:
            codigo = qrcode_scanner(key="scanner_mobile_v8")
            if codigo:
                id_q = str(codigo).strip()
                est = conn.execute("SELECT nombre FROM estudiantes WHERE documento=? AND grado=? AND profe_id=?", (id_q, ga, st.session_state.user)).fetchone()
                if est:
                    f_h = datetime.now().strftime("%Y-%m-%d")
                    ya = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND grado=?", (id_q, f_h, ga)).fetchone()
                    if not ya:
                        h_a = datetime.now().strftime("%H:%M:%S")
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", 
                                     (id_q, f_h, h_a, ga, ma, tema_hoy, st.session_state.user))
                        conn.commit(); st.success(f"✅ {est[0]} - Registrado")
                else: st.error("Estudiante no registrado en este grado.")

        st.divider()
        # Botón de Notificación optimizado para celular
        if st.button("🚀 Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND profe_id=?", conn, params=(f_hoy, ga, st.session_state.user))
            aus = todos[~todos['documento'].isin(pres['estudiante_id'])]
            
            if aus.empty: st.success("¡Asistencia completa!")
            else:
                st.write(f"Ausencias detectadas: {len(aus)}")
                for _, e in aus.iterrows():
                    tel = str(e['whatsapp']).strip().replace(".0", "")
                    if len(tel) == 10: tel = "57" + tel
                    if len(tel) >= 12:
                        txt = f"Cordial saludo. El estudiante {e['nombre']} no asistio hoy a la clase de {ma}. Tema: {tema_hoy}"
                        st.link_button(f"📲 WhatsApp {e['nombre'][:15]}", f"https://api.whatsapp.com/send?phone={tel}&text={txt.replace(' ', '%20')}", use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("📊 Reportes Detallados")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        op_r = [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()]
        sel_r = st.selectbox("Ver curso:", op_r)
        gr, mr = sel_r.split(" | ")
        
        # Obtener asistencias incluyendo el TEMA
        df_rep = pd.read_sql("""SELECT a.fecha, a.hora, a.tema, e.nombre, e.documento 
                                FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                WHERE a.grado = ? AND a.materia = ? AND a.profe_id = ? 
                                ORDER BY a.fecha DESC""", conn, params=(gr, mr, st.session_state.user))
        
        if not df_rep.empty:
            st.dataframe(df_rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_rep.to_excel(writer, sheet_name='Asistencia', startrow=7, index=False)
                wb = writer.book; ws = writer.sheets['Asistencia']
                fmt = wb.add_format({'bold': True, 'size': 12})
                ws.write('A1', COLEGIO.upper(), fmt)
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}")
                ws.write('A3', f"MATERIA: {mr}")
                ws.write('A4', f"GRADO: {gr}")
                ws.write('A5', f"CREADO POR: Rubén Darío Ávila Sandoval")
                ws.set_column('A:E', 20)
            st.download_button("📥 Descargar Excel", output.getvalue(), f"Reporte_{gr}.xlsx", use_container_width=True)
        else: st.info("Sin registros.")

if menu == "⚙️ Salir" or st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
