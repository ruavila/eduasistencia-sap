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
from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH

# --- INICIALIZACIÓN ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
init_db()
conn = get_connection()

# CABECERA
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.get('profe_nom', 'Usuario')}</p>", unsafe_allow_html=True)
st.divider()

# --- AUTENTICACIÓN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registrar Docente"])
    with t1:
        u = st.text_input("Usuario (ID)", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", (u, hash_password(p))).fetchone()
            if res:
                st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u, res[0]
                st.rerun()
            else: st.error("Acceso denegado")
    with t2:
        nu, nn, np = st.text_input("Defina Usuario"), st.text_input("Nombre Completo"), st.text_input("Defina Clave", type="password")
        if st.button("Crear mi Cuenta"):
            try:
                conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (nu, hash_password(np), nn))
                conn.commit(); st.success("¡Cuenta creada correctamente!")
            except: st.error("El usuario ya existe.")
    st.stop()

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Cursos":
    st.subheader("Configuración de Cursos")
    with st.form("nuevo_curso"):
        g, m = st.text_input("Grado"), st.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?,?,?)", (g, m, st.session_state.user))
            conn.commit(); st.rerun()
    
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, r in df_c.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"📍 {r['grado']} - {r['materia']}")
        if c2.button("🗑️", key=f"del_c_{r['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y Carnets")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel = st.selectbox("Curso destino:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gs, ms = sel.split(" | ")
        file = st.file_uploader("Subir Excel (.xlsx)", type=["xlsx"])
        
        if file and st.button("Generar QRs"):
            df = pd.read_excel(file); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=letter)
            w, h = letter; x, y = 1.5*cm, h - 5*cm
            col_idx = 0
            for _, row in df.iterrows():
                eid = str(row['estudiante_id']).split('.')[0]
                enom = str(row['nombre']).upper()
                # Limpiamos el número desde la entrada para evitar basura en la BD
                ews = "".join(filter(str.isdigit, str(row.get('whatsapp', '')).split('.')[0]))
                
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", (eid, enom, ews, gs, ms, st.session_state.user))
                
                qr = qrcode.make(eid); tmp = io.BytesIO(); qr.save(tmp, format='PNG'); tmp.seek(0)
                canv.drawInlineImage(Image.open(tmp), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7); canv.drawString(x, y-0.6*cm, enom[:22])
                
                col_idx += 1
                if col_idx >= 3: x, y, col_idx = 1.5*cm, y - 6*cm, 0
                else: x += 6.5*cm
                if y < 2*cm: canv.showPage(); x, y, col_idx = 1.5*cm, h-5*cm, 0
            
            conn.commit(); canv.save()
            st.download_button("📥 Descargar Carnets PDF", pdf_io.getvalue(), f"QRs_{gs}.pdf", use_container_width=True)

elif menu == "📷 Scanner QR":
    st.subheader("Control de Asistencia")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_a = st.selectbox("Clase:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        ga, ma = sel_a.split(" | ")
        tema = st.text_input("Tema de hoy:")
        
        if tema:
            codigo = qrcode_scanner(key=f"sc_{ga}_{len(tema)}")
            if codigo:
                id_q = "".join(filter(str.isalnum, str(codigo)))
                res = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", (f"%{id_q}%", ga, st.session_state.user)).fetchone()
                if res:
                    doc, nom = res; f_h = datetime.now().strftime("%Y-%m-%d")
                    if not conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", (doc, f_h, tema)).fetchone():
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", (doc, f_h, datetime.now().strftime("%H:%M:%S"), ga, ma, tema, st.session_state.user))
                        conn.commit(); st.success(f"✅ Registrado: {nom}")
                    else: st.info(f"{nom} ya asistió.")
        
        st.divider()
        if st.button("🚀 Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            f_h = datetime.now().strftime("%Y-%m-%d")
            todos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", conn, params=(ga, ma, st.session_state.user))
            pres = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND tema=? AND profe_id=?", conn, params=(f_h, ga, tema, st.session_state.user))
            aus = todos[~todos['documento'].astype(str).isin(pres['estudiante_id'].astype(str).tolist())]
            
            if aus.empty: st.success("¡Asistencia Completa!")
            else:
                st.write(f"### Ausentes en {ga} ({len(aus)})")
                for _, e in aus.iterrows():
                    # --- LIMPIEZA ABSOLUTA DE WHATSAPP ---
                    # 1. Asegurar que sea string y quitar .0 de Excel
                    tel_raw = str(e['whatsapp']).split('.')[0]
                    # 2. Quitar CUALQUIER carácter que no sea dígito (incluye el '+')
                    tel_solo_numeros = "".join(filter(str.isdigit, tel_raw))
                    
                    # 3. Lógica de prefijo (Colombia)
                    if len(tel_solo_numeros) == 10:
                        tel_final = "57" + tel_solo_numeros
                    else:
                        tel_final = tel_solo_numeros

                    mensaje = f"Cordial saludo. El estudiante {e['nombre']} no asistió hoy a {ma}. Tema: {tema}"
                    # Protocolo robusto de WhatsApp
                    url_wa = f"https://api.whatsapp.com/send?phone={tel_final}&text={mensaje.replace(' ', '%20')}"
                    
                    st.link_button(f"📲 Notificar a {e['nombre'][:20]}", url_wa, use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("Reportes en Excel")
    df_c = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    if not df_c.empty:
        sel_r = st.selectbox("Reporte:", [f"{r['grado']} | {r['materia']}" for _, r in df_c.iterrows()])
        gr, mr = sel_r.split(" | ")
        df_rep = pd.read_sql("""SELECT e.documento as ID, e.nombre as Estudiante, a.tema as Tema, a.fecha as Fecha, a.hora as Hora 
                                FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                WHERE a.grado=? AND a.materia=? AND a.profe_id=? 
                                ORDER BY a.fecha DESC""", conn, params=(gr, mr, st.session_state.user))
        st.dataframe(df_rep, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_rep.to_excel(writer, sheet_name='Asistencia', startrow=5, index=False)
            wb, ws = writer.book, writer.sheets['Asistencia']
            ws.write('A1', COLEGIO.upper(), wb.add_format({'bold': True, 'size': 14}))
            ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}")
            ws.write('A3', f"CURSO: {gr} | MATERIA: {mr}")
            ws.set_column('A:E', 20)
        st.download_button("📥 Descargar Reporte Excel", output.getvalue(), f"Reporte_{gr}.xlsx", use_container_width=True)

elif menu == "⚙️ Reinicio":
    st.warning("⚠️ Esto borrará todos sus datos de este profesor.")
    if st.button("BORRAR MI INFORMACIÓN"):
        conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
        conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
        conn.commit(); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()
