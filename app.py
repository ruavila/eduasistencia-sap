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
init_db() # Crea las tablas al iniciar
conn = get_connection()

# CABECERA VISUAL PROFESIONAL
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH):
        st.image(ESCUDO_PATH, width=100)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.get('profe_nom', 'Usuario')}</p>", unsafe_allow_html=True)
st.divider()

# --- SISTEMA DE AUTENTICACIÓN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    tab_log, tab_reg = st.tabs(["🔐 Iniciar Sesión", "📝 Registro de Docente"])
    
    with tab_log:
        user_in = st.text_input("Usuario (ID)", key="l_user")
        pass_in = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
            res = conn.execute("SELECT nombre FROM usuarios WHERE usuario=? AND password=?", 
                               (user_in, hash_password(pass_in))).fetchone()
            if res:
                st.session_state.logueado = True
                st.session_state.user = user_in
                st.session_state.profe_nom = res[0]
                st.rerun()
            else:
                st.error("⚠️ Usuario o contraseña incorrectos.")

    with tab_reg:
        st.info("Registre sus datos para empezar a gestionar sus cursos.")
        new_user = st.text_input("Defina su Usuario (ID)")
        new_name = st.text_input("Nombre Completo")
        new_pass = st.text_input("Defina su Contraseña", type="password")
        if st.button("Crear mi Cuenta"):
            if new_user and new_name and new_pass:
                try:
                    conn.execute("INSERT INTO usuarios VALUES (?, ?, ?)", 
                                 (new_user, hash_password(new_pass), new_name))
                    conn.commit()
                    st.success("✅ Cuenta creada. Ya puede iniciar sesión.")
                except:
                    st.error("❌ El usuario ya existe en el sistema.")
            else:
                st.warning("Por favor complete todos los campos.")
    st.stop()

# --- MENÚ DE NAVEGACIÓN ---
menu = st.sidebar.radio("Navegación Principal", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos y Grados")
    with st.form("form_curso"):
        grado = st.text_input("Nombre del Grado (Ej: 601, 702)")
        materia = st.text_input("Materia (Ej: Informática)")
        if st.form_submit_button("Crear Curso"):
            conn.execute("INSERT INTO cursos (grado, materia, profe_id) VALUES (?, ?, ?)", 
                         (grado, materia, st.session_state.user))
            conn.commit()
            st.rerun()
    
    st.write("### Sus Cursos Activos")
    df_cursos = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    for _, fila in df_cursos.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.info(f"📍 {fila['grado']} - {fila['materia']}")
        if c2.button("Eliminar", key=f"del_c_{fila['id']}"):
            conn.execute("DELETE FROM cursos WHERE id=?", (fila['id'],))
            conn.commit()
            st.rerun()

elif menu == "👤 Estudiantes":
    st.subheader("Carga Masiva y Generación de QRs")
    df_cursos = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if df_cursos.empty:
        st.warning("Debe crear un curso primero.")
    else:
        opciones = [f"{r['grado']} | {r['materia']}" for _, r in df_cursos.iterrows()]
        seleccion = st.selectbox("Seleccione el curso destino:", opciones)
        g_sel, m_sel = seleccion.split(" | ")
        
        archivo = st.file_uploader("Subir listado en Excel (.xlsx)", type=["xlsx"])
        
        if archivo and st.button("Procesar Listado y Generar PDF"):
            df_est = pd.read_excel(archivo)
            df_est.columns = [str(c).strip().lower() for c in df_est.columns]
            
            # Preparar PDF
            pdf_buffer = io.BytesIO()
            c_pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
            ancho, alto = letter
            x_ini, y_ini = 1.5 * cm, alto - 5 * cm
            curr_x, curr_y = x_ini, y_ini
            columnas = 0
            
            for _, r in df_est.iterrows():
                e_id = str(r['estudiante_id']).split('.')[0]
                e_nom = str(r['nombre']).upper()
                e_ws = str(r.get('whatsapp', '')).split('.')[0]
                
                # Guardar en BD
                conn.execute("INSERT OR REPLACE INTO estudiantes VALUES (?,?,?,?,?,?)", 
                             (e_id, e_nom, e_ws, g_sel, m_sel, st.session_state.user))
                
                # Generar QR
                qr_img = qrcode.make(e_id)
                img_io = io.BytesIO()
                qr_img.save(img_io, format='PNG')
                img_io.seek(0)
                
                # Dibujar en PDF
                c_pdf.drawInlineImage(Image.open(img_io), curr_x, curr_y, 4*cm, 4*cm)
                c_pdf.setFont("Helvetica-Bold", 7)
                c_pdf.drawString(curr_x, curr_y - 0.5*cm, e_nom[:22])
                
                # Lógica de posición y multihaja
                columnas += 1
                if columnas >= 3:
                    curr_x = x_ini
                    curr_y -= 6 * cm
                    columnas = 0
                else:
                    curr_x += 6.5 * cm
                
                if curr_y < 2 * cm:
                    c_pdf.showPage()
                    curr_x, curr_y = x_ini, y_ini
                    columnas = 0
            
            conn.commit()
            c_pdf.save()
            st.success("✅ Estudiantes procesados exitosamente.")
            st.download_button("📥 Descargar PDF con QRs", pdf_buffer.getvalue(), f"QRs_{g_sel}.pdf", use_container_width=True)

elif menu == "📷 Scanner QR":
    st.subheader("Control de Asistencia en Tiempo Real")
    df_cursos = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if not df_cursos.empty:
        opciones = [f"{r['grado']} | {r['materia']}" for _, r in df_cursos.iterrows()]
        sel_as = st.selectbox("Clase actual:", opciones)
        ga, ma = sel_as.split(" | ")
        tema_clase = st.text_input("Tema de la clase (Obligatorio para escanear):")
        
        if tema_clase:
            # Llave dinámica para que Streamlit detecte cambios y reinicie la cámara
            cam_key = f"scanner_{ga.replace(' ','')}_{len(tema_clase)}"
            codigo_leido = qrcode_scanner(key=cam_key)
            
            if codigo_leido:
                id_limpio = "".join(filter(str.isalnum, str(codigo_leido)))
                est = conn.execute("SELECT documento, nombre FROM estudiantes WHERE documento LIKE ? AND grado=? AND profe_id=?", 
                                   (f"%{id_limpio}%", ga, st.session_state.user)).fetchone()
                
                if est:
                    doc, nom = est
                    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                    # Verificar si ya marcó asistencia hoy para este tema
                    check = conn.execute("SELECT id FROM asistencia WHERE estudiante_id=? AND fecha=? AND tema=?", 
                                         (doc, fecha_hoy, tema_clase)).fetchone()
                    if not check:
                        conn.execute("INSERT INTO asistencia (estudiante_id, fecha, hora, grado, materia, tema, profe_id) VALUES (?,?,?,?,?,?,?)", 
                                     (doc, fecha_hoy, datetime.now().strftime("%H:%M:%S"), ga, ma, tema_clase, st.session_state.user))
                        conn.commit()
                        st.success(f"🔔 REGISTRADO: {nom}")
                    else:
                        st.info(f"ℹ️ {nom} ya se encuentra en la lista de hoy.")
                else:
                    st.error("⚠️ El código no pertenece a un estudiante de este curso.")

        st.divider()
        if st.button("🚀 Finalizar y Notificar Ausentes", type="primary", use_container_width=True):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            # 1. Obtener todos los inscritos
            inscritos = pd.read_sql("SELECT nombre, whatsapp, documento FROM estudiantes WHERE grado=? AND materia=? AND profe_id=?", 
                                    conn, params=(ga, ma, st.session_state.user))
            # 2. Obtener los que asistieron hoy
            presentes = pd.read_sql("SELECT estudiante_id FROM asistencia WHERE fecha=? AND grado=? AND tema=? AND profe_id=?", 
                                    conn, params=(f_hoy, ga, tema_clase, st.session_state.user))
            presentes_ids = presentes['estudiante_id'].astype(str).tolist()
            # 3. Filtrar ausentes
            ausentes = inscritos[~inscritos['documento'].astype(str).isin(presentes_ids)]
            
            if ausentes.empty:
                st.success("🎉 ¡Asistencia Completa! Todos los estudiantes están presentes.")
            else:
                st.subheader(f"Estudiantes Ausentes ({len(ausentes)})")
                for _, e in ausentes.iterrows():
                    # LIMPIEZA DE NÚMERO (Elimina +, espacios, puntos)
                    num_base = "".join(filter(str.isdigit, str(e['whatsapp'])))
                    # Asegurar 57 al inicio si el número es de 10 dígitos
                    num_final = "57" + num_base if len(num_base) == 10 else num_base
                    
                    texto_msg = f"Cordial saludo. Se informa que el estudiante {e['nombre']} no asistió hoy a la clase de {ma}. Tema: {tema_clase}"
                    enlace_wa = f"https://wa.me/{num_final}?text={texto_msg.replace(' ', '%20')}"
                    
                    st.link_button(f"📲 Notificar a {e['nombre'][:20]}", enlace_wa, use_container_width=True)

elif menu == "📊 Reportes":
    st.subheader("Generación de Reportes en Excel")
    df_cursos = pd.read_sql("SELECT grado, materia FROM cursos WHERE profe_id=?", conn, params=(st.session_state.user,))
    
    if not df_cursos.empty:
        sel_rep = st.selectbox("Ver reporte de:", [f"{r['grado']} | {r['materia']}" for _, r in df_cursos.iterrows()])
        gr, mr = sel_rep.split(" | ")
        
        df_final = pd.read_sql("""SELECT e.documento as Identidad, e.nombre as Estudiante, a.tema as Tema, a.fecha as Fecha, a.hora as Hora 
                                  FROM asistencia a JOIN estudiantes e ON a.estudiante_id = e.documento 
                                  WHERE a.grado=? AND a.materia=? AND a.profe_id=? 
                                  ORDER BY a.fecha DESC, a.hora DESC""", conn, params=(gr, mr, st.session_state.user))
        
        if not df_final.empty:
            st.dataframe(df_final, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name='Asistencia', startrow=5, index=False)
                wb = writer.book
                ws = writer.sheets['Asistencia']
                ws.write('A1', COLEGIO.upper(), wb.add_format({'bold': True, 'size': 14}))
                ws.write('A2', f"DOCENTE: {st.session_state.profe_nom}")
                ws.write('A3', f"CURSO: {gr} | MATERIA: {mr}")
                ws.set_column('A:E', 20)
            st.download_button("📥 Descargar Reporte Completo", output.getvalue(), f"Reporte_{gr}_{mr}.xlsx", use_container_width=True)
        else:
            st.info("No hay registros de asistencia para este curso todavía.")

elif menu == "⚙️ Reinicio":
    st.error("### ⚠️ Zona de Peligro")
    st.write("Esta acción borrará todos sus cursos, estudiantes y registros de asistencia permanentemente.")
    confirm = st.text_input("Para confirmar, escriba ELIMINAR:")
    if st.button("BORRAR TODA MI INFORMACIÓN"):
        if confirm == "ELIMINAR":
            conn.execute("DELETE FROM asistencia WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM estudiantes WHERE profe_id=?", (st.session_state.user,))
            conn.execute("DELETE FROM cursos WHERE profe_id=?", (st.session_state.user,))
            conn.commit()
            st.success("Datos eliminados. Reiniciando...")
            st.rerun()
        else:
            st.warning("Debe escribir la palabra correctamente para continuar.")

if st.sidebar.button("Cerrar Sesión"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
