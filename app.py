import streamlit as st
import pandas as pd
import qrcode
import io
import os
import urllib.parse
import tempfile
import time
import random
import datetime as dt
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from streamlit_qrcode_scanner import qrcode_scanner
from fpdf import FPDF

# ==============================================================================
# --- CONSTANTES GLOBALES ---
APP_NAME = "EduAsistencia-Pro"
APP_VERSION = "v2.2.1"
DEVELOPER_NAME = "Rubén Darío Ávila Sandoval"
IE_INITIALS = "I.E. S.A.P."
COLEGIO = "Institución Educativa San Antonio de Padua"
ESTADOS_ASISTENCIA = ["Presente", "Ausente", "Excusa Médica", "Permiso Institucional", "Llegada Tardía"]

# Variaciones para evitar bloqueos/filtros de spam de WhatsApp al notificar desde móvil
SALUDOS_VARIADOS = [
    "Cordial saludo, señor(a) acudiente.",
    "Buenos días/tardes, estimado(a) acudiente.",
    "Un saludo cordial, señor(a) padre/madre de familia.",
    "Respetado(a) acudiente, le saludamos de la institución."
]

CIERRES_VARIADOS = [
    "Agradecemos su atención y seguimiento en casa.",
    "Quedamos atentos a cualquier justificación o novedad.",
    "Agradecemos su colaboración con la asistencia del estudiante.",
    "Favor comunicarse con la institución si requiere más información."
]
# ==============================================================================

# --- INTEGRACIÓN CON MÓDULOS ---
try:
    from modules.database import supabase, hash_password
    from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH
except Exception as e:
    st.error(f"Error al cargar módulos: {e}")
    APP_NAME = "EduAsistencia-Pro"
    COLEGIO = "Institución Educativa San Antonio de Padua"
    ESCUDO_PATH = os.path.join("assets", "escudo.png") 

IE_INITIALS = "I.E. S.A.P."

# --- FUNCIONES AUXILIARES DE REPORTES ---
def formatear_fecha_reporte(fecha_str):
    if not fecha_str: 
        return ""
    try:
        fecha_obj = dt.datetime.strptime(fecha_str, "%Y-%m-%d")
        return fecha_obj.strftime("%d-%m")
    except ValueError:
        return fecha_str

def generar_pdf_reporte(todos_est, asistencia_data, ga_rep, ma_rep, periodo_rep):
    df_reporte = pd.DataFrame(todos_est)
    df_reporte['nombre'] = df_reporte['nombre'].str.upper()
    try:
        df_reporte['nombre'] = df_reporte['nombre'].str.encode('latin-1', 'ignore').str.decode('latin-1')
    except Exception:
        pass
    df_reporte = df_reporte.set_index('documento')
    
    columnas_dinamicas = []
    reporte_final = df_reporte.copy()

    check_pi_latin = 'V'.encode('latin-1', 'ignore').decode('latin-1')

    if asistencia_data:
        df_asistencia = pd.DataFrame(asistencia_data)
        df_asistencia['tema_limpio'] = df_asistencia['tema'].apply(lambda x: x.split(" [")[0].strip() if " [" in str(x) else str(x).strip())
        df_clases = df_asistencia[['fecha', 'tema_limpio']].drop_duplicates().sort_values('fecha')

        for _, clase in df_clases.iterrows():
            fecha_fmt = formatear_fecha_reporte(clase['fecha'])
            tema_raw = clase['tema_limpio']
            try:
                tema_latin = tema_raw.encode('latin-1', 'ignore').decode('latin-1')
                encabezado_col = f"{tema_latin}\n{fecha_fmt}"
            except Exception:
                encabezado_col = f"{tema_raw}\n{fecha_fmt}"
            
            columnas_dinamicas.append(encabezado_col)
            reporte_final[encabezado_col] = 'X' 

        for registro in asistencia_data:
            id_est = registro['estudiante_id']
            if id_est in reporte_final.index:
                tema_full = str(registro['tema'])
                tema_reg = tema_full.split(" [")[0].strip() if " [" in tema_full else tema_full.strip()
                fecha_fmt_reg = formatear_fecha_reporte(registro['fecha'])
                
                try:
                    tema_latin_reg = tema_reg.encode('latin-1', 'ignore').decode('latin-1')
                    col_pi = f"{tema_latin_reg}\n{fecha_fmt_reg}"
                except Exception:
                    col_pi = f"{tema_reg}\n{fecha_fmt_reg}"
                
                if col_pi in reporte_final.columns:
                    if "[Excusa Médica]" in tema_full:
                        val_marcar = 'E'
                    elif "[Permiso Institucional]" in tema_full:
                        val_marcar = 'P'
                    elif "[Llegada Tardía]" in tema_full:
                        val_marcar = 'T'
                    elif "[Ausente]" in tema_full:
                        val_marcar = 'X'
                    else:
                        val_marcar = check_pi_latin
                        
                    reporte_final.loc[id_est, col_pi] = val_marcar

        df_aux = reporte_final[columnas_dinamicas]
        reporte_final['Asist'] = (df_aux == check_pi_latin).sum(axis=1)
        reporte_final['Ausen.'] = (df_aux == 'X').sum(axis=1)
    else:
        reporte_final['Asist'] = 0
        reporte_final['Ausen.'] = 0

    reporte_final['Asist'] = reporte_final['Asist'].astype(str)
    reporte_final['Ausen.'] = reporte_final['Ausen.'].astype(str)
    
    reporte_final = reporte_final.reset_index()
    reporte_final = reporte_final.rename(columns={'nombre': 'ESTUDIANTE'})
    reporte_final.insert(0, 'N°', range(1, 1 + len(reporte_final)))
    reporte_final['N°'] = reporte_final['N°'].astype(str)

    pdf = FPDF('L', 'mm', 'Legal')
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    
    escudo_path = os.path.join("assets", "escudo.png")
    if os.path.exists(escudo_path):
        pdf.image(escudo_path, 10, 8, 25, 25)
    
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists(escudo_path):
        pdf.set_x(40)
    
    pdf.cell(0, 12, "Institución Educativa San Antonio de Padua", 0, 1, 'C')
    pdf.set_font("Arial", '', 11)
    if os.path.exists(escudo_path):
        pdf.set_x(40)
    
    pdf.cell(100, 7, f"Materia: {ma_rep}", 0, 0)
    pdf.cell(80, 7, f"Grado: {ga_rep}", 0, 0)
    pdf.cell(0, 7, f"Docente: {st.session_state.profe_nom}", 0, 1)
    
    if os.path.exists(escudo_path):
        pdf.set_x(40)
    
    pdf.set_font("Arial", 'B', 11)
    ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
    pdf.cell(100, 7, f"Fecha Reporte: {ahora_co.strftime('%d/%m/%Y')}", 0, 0)
    pdf.cell(0, 7, f"Periodo Académico Consultando: {periodo_rep}", 0, 1)
    
    pdf.ln(5)

    num_clases = len(columnas_dinamicas)
    w_num, w_est, w_totales = 12, 70, 18 
    ancho_usado_fijo = w_num + w_est + (w_totales * 2)
    ancho_disponible_dinamico = 335 - ancho_usado_fijo
    
    w_clase = (ancho_disponible_dinamico / num_clases) if num_clases > 0 else ancho_disponible_dinamico

    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    
    pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) 
    pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
    
    x_col, y_col = pdf.get_x(), pdf.get_y()
    if num_clases > 0:
        for enc_completo in columnas_dinamicas:
            pdf.multi_cell(w_clase, 7, enc_completo, 1, 'C', 1)
            x_col += w_clase
            pdf.set_xy(x_col, y_col)
    else:
        pdf.cell(ancho_disponible_dinamico, 14, "Sin registros de asistencia en este periodo", 1, 0, 'C', 1)

    pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
    pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1)

    pdf.set_font("Arial", '', 9)
    
    for _, fila in reporte_final.iterrows():
        pdf.cell(w_num, 8, fila['N°'], 1, 0, 'C')
        pdf.cell(w_est, 8, fila['ESTUDIANTE'], 1, 0)
        
        if num_clases > 0:
            for col_din in columnas_dinamicas:
                pdf.cell(w_clase, 8, fila[col_din], 1, 0, 'C')
        else:
            pdf.cell(ancho_disponible_dinamico, 8, "", 1, 0)
            
        pdf.cell(w_totales, 8, fila['Asist'], 1, 0, 'C')
        pdf.cell(w_totales, 8, fila['Ausen.'], 1, 1, 'C')
        
        if pdf.get_y() > 180: 
            pdf.add_page()
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) 
            pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
            if num_clases > 0:
                x_col_pg, y_col_pg = pdf.get_x(), pdf.get_y()
                for enc_completo_pg in columnas_dinamicas:
                    pdf.multi_cell(w_clase, 7, enc_completo_pg, 1, 'C', 1)
                    x_col_pg += w_clase
                    pdf.set_xy(x_col_pg, y_col_pg)
            pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
            pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1)
            pdf.set_font("Arial", '', 9)

    return pdf.output(dest='S')

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

if 'logueado' not in st.session_state: 
    st.session_state.logueado = False
if 'captura_finalizada' not in st.session_state: 
    st.session_state.captura_finalizada = False

# --- BLOQUE 1: AUTENTICACIÓN Y RECUPERACIÓN ---
if not st.session_state.logueado:
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        c1, c2 = st.columns([1, 4])
        with c1:
            if os.path.exists(ESCUDO_PATH): 
                st.image(ESCUDO_PATH, width=80)
        with c2:
            st.markdown(f"### {COLEGIO}")
            st.markdown(
                f"""
                <h1 style='margin:0;'>{APP_NAME}</h1>
                <p style='margin:0; color: grey; font-size: 0.9rem;'>
                    <b>Versión {APP_VERSION}</b> | Desarrollado por: <b>{DEVELOPER_NAME}</b>
                </p>
                """, 
                unsafe_allow_html=True
            )
        
        st.markdown("---")
        t1, t2, t3 = st.tabs(["🔐 Acceso", "📝 Registro", "🔑 Recuperar Clave"])
        
        with t1:
            u_l = st.text_input("Usuario", key="l_u")
            p_l = st.text_input("Contraseña", type="password", key="l_p")
            if st.button("🚀 INGRESAR", use_container_width=True, type="primary"):
                res = supabase.table("usuarios").select("nombre").eq("usuario", u_l).eq("password", hash_password(p_l)).execute()
                if res.data:
                    st.session_state.logueado, st.session_state.user, st.session_state.profe_nom = True, u_l, res.data[0]['nombre']
                    st.rerun()
                else: 
                    st.error("Credenciales incorrectas.")
        
        with t2:
            nu = st.text_input("Definir Usuario ID")
            nn = st.text_input("Nombre Completo")
            np = st.text_input("Definir Contraseña", type="password")
            st.info("Configura tu dato secreto para recuperación:")
            preg = st.selectbox("Pregunta de Seguridad", ["¿Nombre de su primera mascota?", "¿Ciudad de nacimiento?", "¿Comida favorita?"])
            resp = st.text_input("Respuesta Secreta")
            
            if st.button("✨ CREAR CUENTA", use_container_width=True):
                if nu and nn and np and resp:
                    try:
                        supabase.table("usuarios").insert({
                            "usuario": nu, "password": hash_password(np), "nombre": nn, 
                            "pregunta_seguridad": preg, "respuesta_seguridad": resp.strip().lower()
                        }).execute()
                        st.success("Cuenta creada exitosamente.")
                    except Exception: 
                        st.error("El usuario ya existe.")
                else: 
                    st.warning("Complete todos los campos.")

        with t3:
            st.markdown("### Recuperar Acceso")
            ur = st.text_input("Ingrese su Usuario ID:", key="rec_user")
            if ur:
                u_data = supabase.table("usuarios").select("*").eq("usuario", ur).execute().data
                if u_data:
                    st.write(f"**Pregunta:** {u_data[0]['pregunta_seguridad']}")
                    r_int = st.text_input("Su respuesta secreta:", type="password")
                    n_p = st.text_input("Nueva Contraseña:", type="password")
                    if st.button("✅ ACTUALIZAR", use_container_width=True):
                        if r_int.strip().lower() == u_data[0]['respuesta_seguridad']:
                            supabase.table("usuarios").update({"password": hash_password(n_p)}).eq("usuario", ur).execute()
                            st.success("Contraseña actualizada.")
                        else: 
                            st.error("Respuesta incorrecta.")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("📌 Menú")
    menu = st.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner / Asistencia", "📊 Reportes", "⚙️ Reinicio"])
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        st.session_state.logueado = False
        st.rerun()

# --- CABECERA ---
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)

# --- DASHBOARD DE MÉTRICAS EN CABECERA ---
try:
    ahora_m_dash = datetime.now() - timedelta(hours=5)
    hoy_m_dash = ahora_m_dash.strftime("%Y-%m-%d")

    asist_hoy = (
        supabase.table("asistencia")
        .select("id, estudiante_id, grado")
        .eq("fecha", hoy_m_dash)
        .eq("profe_id", st.session_state.user)
        .execute()
        .data
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(label="📋 Registros de Asistencia Hoy", value=len(asist_hoy))
    with m2:
        clases_atendidas = len(set(a["grado"] for a in asist_hoy)) if asist_hoy else 0
        st.metric(label="👥 Cursos Atendidos Hoy", value=clases_atendidas)
    with m3:
        st.metric(label="🟢 Estado del Sistema", value="Conectado")
except Exception:
    st.caption("Cargando métricas del día...")

st.divider()

# --- 1. CURSOS ---
if menu == "📚 Cursos":
    st.subheader("Configuración de Cursos")
    g, m = st.text_input("Grado"), st.text_input("Asignatura")
    if st.button("Añadir Curso"):
        if g.strip() and m.strip():
            supabase.table("cursos").insert({"grado": g.strip(), "materia": m.strip(), "profe_id": st.session_state.user}).execute()
            st.rerun()
        else:
            st.warning("Por favor ingresa tanto el Grado como la Asignatura.")
    
    res_c = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute()
    if res_c.data:
        df_c = pd.DataFrame(res_c.data)
        df_c = df_c.sort_values(by="grado", ascending=True)
        
        for _, r in df_c.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.info(f"{r['grado']} - {r['materia']}")
            if c2.button("🗑️", key=f"del_{r['id']}"):
                supabase.table("cursos").delete().eq("id", r['id']).execute()
                st.rerun()

# --- 2. ESTUDIANTES Y CARNETS ---
elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y Carnetización")
    import uuid

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        opciones_cursos = sorted([f"{r['grado'].strip()} | {r['materia'].strip()}" for r in cursos])
        sel = st.selectbox("Curso:", opciones_cursos)
        
        gs, ms = [x.strip() for x in sel.split(" | ")]
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        
        if f and st.button("Procesar y Generar PDF"):
            df = pd.read_excel(f)
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            pdf = io.BytesIO()
            canv = canvas.Canvas(pdf, pagesize=letter)
            ancho_pg, alto_pg = letter
            
            x, y, col = 1.5*cm, alto_pg - 5*cm, 0
            
            for index, r in df.iterrows():
                id_base = str(r.get('estudiante_id', r.get('documento', r.get('id', '')))).split('.')[0].strip()
                
                if not id_base or id_base.lower() in ['nan', 'none', '']:
                    e_id = f"EST-{uuid.uuid4().hex[:8].upper()}"
                else:
                    e_id = f"{gs.replace(' ', '')}-{id_base}"
                
                e_nm = str(r.get('nombre', '')).upper().strip()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                
                supabase.table("estudiantes").upsert({
                    "documento": e_id, 
                    "nombre": e_nm, 
                    "whatsapp": e_ws, 
                    "grado": gs, 
                    "materia": ms, 
                    "profe_id": st.session_state.user
                }, on_conflict="documento").execute()
                
                qr_engine = qrcode.QRCode(
                    version=1, 
                    error_correction=qrcode.constants.ERROR_CORRECT_H, 
                    box_size=10, 
                    border=4
                )
                qr_engine.add_data(str(e_id))
                qr_engine.make(fit=True)
                img_qr = qr_engine.make_image(fill_color="black", back_color="white")
                
                tmp_filename = f"qr_{gs}_{index}_{e_id}.png".replace("/", "_").replace("\\", "_")
                tmp_qr_path = os.path.join(tempfile.gettempdir(), tmp_filename)
                img_qr.save(tmp_qr_path)

                canv.drawInlineImage(tmp_qr_path, x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7)
                canv.drawCentredString(x + 2*cm, y - 0.4*cm, e_nm[:25])
                canv.setFont("Helvetica", 6)
                canv.drawCentredString(x + 2*cm, y - 0.8*cm, f"Grado: {gs} - {IE_INITIALS}")
                
                if os.path.exists(tmp_qr_path):
                    try: os.remove(tmp_qr_path)
                    except Exception: pass
                
                col += 1
                if col >= 3:
                    x = 1.5*cm
                    y -= 6.0*cm
                    col = 0
                else: 
                    x += 6.5*cm
                
                if y < 2*cm: 
                    canv.showPage()
                    x, y, col = 1.5*cm, alto_pg - 5*cm, 0
                
            canv.save()
            st.success(f"Se generaron carnets para {len(df)} estudiantes en formato Carta.")
            st.download_button("📥 Descargar Carnets", pdf.getvalue(), f"Carnets_{gs}.pdf")

# --- 3. SCANNER QR, LISTA MANUAL Y MODIFICACIÓN ---
elif menu == "📷 Scanner / Asistencia":
    st.subheader("Captura y Gestión de Asistencia por Periodo")
    
    if 'captura_finalizada' not in st.session_state:
        st.session_state.captura_finalizada = False
    if 'tema_clase_actual' not in st.session_state:
        st.session_state.tema_clase_actual = ""

    def resetear_estado_escaneo():
        for key in list(st.session_state.keys()):
            if key.startswith("sc_"):
                del st.session_state[key]
        st.session_state.captura_finalizada = False

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    
    if cursos:
        col_tit, col_btn_cerrar = st.columns([3, 1])
        with col_btn_cerrar:
            if st.button("🔴 Cerrar Clase", use_container_width=True, help="Limpia la selección actual y el tema"):
                st.session_state.captura_finalizada = False
                st.session_state.tema_clase_actual = ""
                resetear_estado_escaneo()
                st.session_state["sel_curso_scan"] = None
                st.rerun()

        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            opciones_cursos = sorted(list(set([f"{str(r['grado']).strip()} | {str(r['materia']).strip()}" for r in cursos])))
            
            if "sel_curso_scan" not in st.session_state:
                st.session_state["sel_curso_scan"] = None
                
            sel_as = st.selectbox(
                "Curso:", 
                opciones_cursos, 
                index=None, 
                placeholder="-- Seleccione un curso --", 
                key="sel_curso_scan",
                on_change=resetear_estado_escaneo
            )

        if sel_as is None:
            st.info("👈 Por favor, seleccione un curso para iniciar la clase.")
        else:
            ga, ma = [item.strip() for item in sel_as.split(" | ")]
            
            with col_c2:
                periodo_actual = st.number_input("Periodo Actual:", min_value=1, max_value=4, value=1, step=1, key="num_periodo")
            
            tema_input = st.text_input(
                "Tema de la clase (Sincronizado entre QR y Lista Manual):", 
                value=st.session_state.tema_clase_actual,
                placeholder="Ej: Introducción a la Multimedia", 
                key="input_tema_global"
            )
            st.session_state.tema_clase_actual = tema_input.strip()
            tema = st.session_state.tema_clase_actual

            tab_qr, tab_lista, tab_editar = st.tabs(["📷 Escáner QR", "🔢 Lista Manual", "✏️ Modificar Fechas Anteriores"])
            
            # --- TAB 1: ESCÁNER QR ---
            with tab_qr:
                if tema:
                    if not st.session_state.captura_finalizada:
                        st.info(f"📋 **{ga} - {ma}** | Periodo: **{periodo_actual}** | Tema: *{tema}*")
                        
                        if st.button("⏹️ Finalizar y Ver Ausentes", type="primary", use_container_width=True):
                            st.session_state.captura_finalizada = True
                            st.rerun()
                        
                        key_scanner = f"sc_{ga}_{ma}_{periodo_actual}".replace(" ", "_")
                        cod = qrcode_scanner(key=key_scanner)
                        
                        if cod:
                            id_cl = str(cod).strip()
                            res = supabase.table("estudiantes").select("documento, nombre, grado")\
                                .eq("documento", id_cl)\
                                .eq("profe_id", st.session_state.user).execute().data
                            
                            res_filtrado = [e for e in res if str(e.get('grado', '')).strip().upper() == ga.upper()]
                            
                            if res_filtrado:
                                estudiante_encontrado = res_filtrado[0]
                                doc = str(estudiante_encontrado['documento']).strip()
                                nom = estudiante_encontrado['nombre']
                                ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                                hoy = ahora_co.strftime("%Y-%m-%d")
                                
                                check = supabase.table("asistencia").select("id")\
                                    .eq("estudiante_id", doc)\
                                    .eq("fecha", hoy)\
                                    .eq("materia", ma)\
                                    .eq("periodo", periodo_actual).execute().data
                                
                                if not check:
                                    try:
                                        supabase.table("asistencia").insert({
                                            "estudiante_id": doc, 
                                            "fecha": hoy, 
                                            "hora": ahora_co.strftime("%H:%M:%S"), 
                                            "grado": ga, 
                                            "materia": ma, 
                                            "tema": tema, 
                                            "periodo": periodo_actual,
                                            "profe_id": st.session_state.user
                                        }).execute()
                                        
                                        st.toast(f"✅ Registrado (P{periodo_actual}): {nom}", icon="👤")
                                        st.success(f"👤 **Estudiante detectado ({ga}):** {nom}")
                                        
                                        if key_scanner in st.session_state:
                                            del st.session_state[key_scanner]
                                            
                                        time.sleep(0.5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al guardar asistencia: {e}")
                                else:
                                    st.toast(f"ℹ️ {nom} ya registrado hoy", icon="✅")
                                    st.warning(f"El estudiante **{nom}** ya fue registrado previamente hoy.")
                            else:
                                st.toast(f"⚠️ Código {id_cl} no asignado a {ga}", icon="❌")
                                st.error(f"El código **{id_cl}** no se encuentra registrado en el grado **{ga}**.")
                    
                    else:
                        if st.button("🔄 Volver a escanear / Reabrir Clase", use_container_width=True):
                            st.session_state.captura_finalizada = False
                            st.rerun()

                        st.warning(f"⚠️ Estudiantes Ausentes en {ga} ({ma} - Periodo {periodo_actual}):")
                        
                        ahora_col = dt.datetime.now() - dt.timedelta(hours=5)
                        hoy_col = ahora_col.strftime("%Y-%m-%d")
                        hora_msj = ahora_col.strftime("%I:%M %p")
                        
                        todos_est = supabase.table("estudiantes").select("documento, nombre, whatsapp, grado")\
                            .eq("profe_id", st.session_state.user).execute().data
                        
                        estudiantes_curso = [e for e in todos_est if str(e.get('grado', '')).strip().upper() == ga.upper()]
                        estudiantes_curso = sorted(estudiantes_curso, key=lambda x: x['nombre'])
                        
                        asistieron_raw = supabase.table("asistencia").select("estudiante_id, tema")\
                            .eq("grado", ga)\
                            .eq("materia", ma)\
                            .eq("fecha", hoy_col)\
                            .eq("periodo", periodo_actual).execute().data
                        
                        registros_excluidos = set()
                        for r in asistieron_raw:
                            est_id = str(r.get('estudiante_id', '')).strip()
                            tema_r = str(r.get('tema', '')).strip()
                            if not ("[Ausente]" in tema_r):
                                registros_excluidos.add(est_id)

                        ausentes = [e for e in estudiantes_curso if str(e['documento']).strip() not in registros_excluidos]
                        
                        if ausentes:
                            st.write(f"Total ausentes: **{len(ausentes)}** de **{len(estudiantes_curso)}** matriculados.")
                            for aus in ausentes:
                                col_a, col_b = st.columns([3, 1])
                                col_a.write(f"❌ **{aus['nombre']}**")
                                
                                # --- GENERACIÓN DINÁMICA ANTI-SPAM DE WHATSAPP ---
                                saludo_unico = random.choice(SALUDOS_VARIADOS)
                                cierre_unico = random.choice(CIERRES_VARIADOS)
                                marca_tiempo = dt.datetime.now().strftime("%H:%M:%S")
                                
                                cuerpo_msj = (
                                    f"{saludo_unico}\n\n"
                                    f"La Institución Educativa San Antonio de Padua le informa que el estudiante "
                                    f"*{aus['nombre']}* no se presentó el día de hoy a la clase de *{ma}* ({ga}).\n\n"
                                    f"📌 *Hora de reporte:* {hora_msj}\n"
                                    f"📖 *Tema tratado:* {tema}\n\n"
                                    f"{cierre_unico}\n\n"
                                    f"*Docente:* {st.session_state.profe_nom}\n"
                                    f"*Área:* {ma}\n"
                                    f"_Ref: {marca_tiempo}_"
                                )
                                
                                msg_encoded = urllib.parse.quote(cuerpo_msj)
                                num_wa = str(aus.get('whatsapp', '')).strip()
                                link_wa = f"https://wa.me/57{num_wa}?text={msg_encoded}"
                                col_b.markdown(f"[📲 Notificar]({link_wa})")
                        else:
                            st.success("🎉 ¡No hay reportes de inasistencia pendientes hoy!")
                else:
                    st.info("Por favor ingresa el **Tema de la clase** arriba para activar el Escáner QR.")

            # --- TAB 2: LISTA MANUAL ---
            with tab_lista:
                st.info(f"Registro Manual para **{ga} - {ma}** | Periodo: **{periodo_actual}**")
                
                if tema:
                    ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                    hoy_m = ahora_co.strftime("%Y-%m-%d")
                    
                    estado_sel = st.selectbox("Estado del Registro:", ESTADOS_ASISTENCIA, index=0, key="sel_est_manual")
                    
                    todos_est_raw = supabase.table("estudiantes").select("documento, nombre, grado")\
                        .eq("profe_id", st.session_state.user).execute().data
                    
                    ga_objetivo = ga.strip().upper()
                    estudiantes_curso = []
                    vistos = set()
                    
                    for e in sorted(todos_est_raw, key=lambda x: str(x.get('nombre', ''))):
                        grado_est = str(e.get('grado', '')).strip().upper()
                        nom_est = str(e.get('nombre', '')).strip().upper()
                        
                        if grado_est == ga_objetivo and nom_est not in vistos:
                            vistos.add(nom_est)
                            estudiantes_curso.append(e)

                    with st.expander("🔍 Herramienta de Inspección de Estudiantes", expanded=False):
                        st.caption(f"Mostrando estudiantes asignados exactamente al grado **{ga_objetivo}**:")
                        if estudiantes_curso:
                            st.dataframe(pd.DataFrame(estudiantes_curso)[['documento', 'nombre', 'grado']])
                        else:
                            st.warning(f"No hay estudiantes etiquetados exactamente con el grado '{ga_objetivo}'.")

                    if estudiantes_curso:
                        ya_registrados_raw = supabase.table("asistencia").select("estudiante_id")\
                            .eq("grado", ga)\
                            .eq("materia", ma)\
                            .eq("fecha", hoy_m)\
                            .eq("periodo", periodo_actual).execute().data
                        
                        ids_registrados = set(str(r['estudiante_id']).strip() for r in ya_registrados_raw)

                        nombres_estudiantes = []
                        for i, e in enumerate(estudiantes_curso):
                            doc_clean = str(e['documento']).strip()
                            marca = "✅ (Ya en lista)" if doc_clean in ids_registrados else "⏳ (Pendiente)"
                            nombres_estudiantes.append(f"{i+1}. {e['nombre']} — {marca}")
                        
                        est_sel_nombre = st.selectbox(
                            "Seleccione el estudiante a registrar:", 
                            nombres_estudiantes, 
                            key=f"sel_man_{ga}_{ma}".replace(" ", "_")
                        )
                        
                        idx_seleccionado = nombres_estudiantes.index(est_sel_nombre)
                        
                        if st.button("✅ Registrar Asistencia Manual", use_container_width=True, type="primary"):
                            est_sel = estudiantes_curso[idx_seleccionado]
                            doc_m, nom_m = str(est_sel['documento']).strip(), est_sel['nombre']
                            
                            check_m = supabase.table("asistencia").select("id")\
                                .eq("estudiante_id", doc_m)\
                                .eq("fecha", hoy_m)\
                                .eq("materia", ma)\
                                .eq("periodo", periodo_actual).execute().data
                            
                            tema_guardar = f"{tema} [{estado_sel}]" if estado_sel != "Presente" else tema
                            
                            payload_manual = {
                                "estudiante_id": doc_m, 
                                "fecha": hoy_m, 
                                "hora": ahora_co.strftime("%H:%M:%S"), 
                                "grado": ga, 
                                "materia": ma, 
                                "tema": tema_guardar, 
                                "periodo": periodo_actual,
                                "profe_id": st.session_state.user
                            }
                            
                            if not check_m:
                                supabase.table("asistencia").insert(payload_manual).execute()
                                st.success(f"Guardado como **{estado_sel}**: {nom_m}")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.warning(f"El estudiante **{nom_m}** ya estaba registrado hoy.")
                    else:
                        st.warning(f"No hay estudiantes registrados para el grado **{ga}**.")
            else:
                st.info("Ingresa el **Tema de la clase** en el campo superior antes de seleccionar en lista.")

            # --- TAB 3: MODIFICAR FECHAS ANTERIORES ---
            with tab_editar:
                st.info(f"Edición / Corrección de Asistencia para **{ga} - {ma}** (Periodo {periodo_actual})")

                clases_previas = supabase.table("asistencia").select("fecha, tema")\
                    .eq("grado", ga)\
                    .eq("materia", ma)\
                    .eq("periodo", periodo_actual)\
                    .eq("profe_id", st.session_state.user)\
                    .order("fecha", desc=True).execute().data

                if clases_previas:
                    fechas_unicas = {}
                    for c in clases_previas:
                        f_str = c['fecha']
                        if f_str not in fechas_unicas:
                            t_base = str(c['tema']).split(" [")[0].strip()
                            fechas_unicas[f_str] = t_base

                    opciones_fechas = [f"📅 {fecha}  |  Tema: {tema_hist}" for fecha, tema_hist in fechas_unicas.items()]
                    
                    sel_fecha_lbl = st.selectbox("Seleccione la Clase Registrada a Modificar:", opciones_fechas, key="sel_f_historica")
                    
                    fecha_mod_str = sel_fecha_lbl.split(" | ")[0].replace("📅 ", "").strip()
                    tema_original = fechas_unicas[fecha_mod_str]

                    st.markdown(f"📖 **Tema de la Clase Seleccionada:** *{tema_original}*")

                    todos_est_raw = supabase.table("estudiantes").select("documento, nombre, grado")\
                        .eq("profe_id", st.session_state.user).execute().data
                    
                    estudiantes_curso = [e for e in todos_est_raw if str(e.get('grado', '')).strip().upper() == ga.strip().upper()]
                    estudiantes_curso = sorted(estudiantes_curso, key=lambda x: x['nombre'])

                    if estudiantes_curso:
                        registros_existentes = supabase.table("asistencia").select("id, estudiante_id, tema")\
                            .eq("grado", ga)\
                            .eq("materia", ma)\
                            .eq("periodo", periodo_actual)\
                            .eq("fecha", fecha_mod_str)\
                            .eq("profe_id", st.session_state.user).execute().data

                        mapa_asistencia = {r['estudiante_id']: r for r in registros_existentes}

                        opciones_mod = []
                        mapa_opciones = {}

                        for e in estudiantes_curso:
                            doc = e['documento']
                            nombre = e['nombre']

                            if doc in mapa_asistencia:
                                reg = mapa_asistencia[doc]
                                tema_full = str(reg['tema'])
                                estado_actual = "Presente"
                                for est in ESTADOS_ASISTENCIA:
                                    if f"[{est}]" in tema_full:
                                        estado_actual = est
                                        break
                            else:
                                estado_actual = "Ausente"
                                reg = None

                            lbl = f"{nombre}  |  Estado actual: [{estado_actual}]"
                            opciones_mod.append(lbl)
                            mapa_opciones[lbl] = {"estudiante": e, "registro": reg, "estado_actual": estado_actual}

                        col_est, col_est_nuevo = st.columns([2, 1])
                        with col_est:
                            est_seleccionado_lbl = st.selectbox("Estudiante:", opciones_mod, key="sel_mod_est_tab")
                        with col_est_nuevo:
                            nuevo_estado = st.selectbox("Nuevo Estado:", ESTADOS_ASISTENCIA, key="sel_nuevo_est_tab")

                        datos_sel = mapa_opciones[est_seleccionado_lbl]

                        if st.button("💾 Guardar Cambio de Estado", type="primary", use_container_width=True):
                            tema_guardar = f"{tema_original} [{nuevo_estado}]" if nuevo_estado != "Presente" else tema_original
                            doc_est = datos_sel["estudiante"]["documento"]
                            reg = datos_sel["registro"]

                            if reg:
                                supabase.table("asistencia").update({
                                    "tema": tema_guardar
                                }).eq("id", reg['id']).execute()
                            else:
                                ahora_mod = dt.datetime.now() - dt.timedelta(hours=5)
                                supabase.table("asistencia").insert({
                                    "estudiante_id": doc_est,
                                    "fecha": fecha_mod_str,
                                    "hora": ahora_mod.strftime("%H:%M:%S"),
                                    "grado": ga,
                                    "materia": ma,
                                    "tema": tema_guardar,
                                    "periodo": periodo_actual,
                                    "profe_id": st.session_state.user
                                }).execute()

                            st.success(f"✅ Estado de **{datos_sel['estudiante']['nombre']}** actualizado a **{nuevo_estado}**.")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning(f"No hay estudiantes matriculados en el grado **{ga}**.")
                else:
                    st.warning(f"No hay clases registradas previamente para **{ga} - {ma}** en el Periodo {periodo_actual}.")
    else:
        st.error("No tienes cursos asignados. Por favor, crea un curso primero en la configuración.")

# --- 4. SECCIÓN DE REPORTES ---
elif menu == "📊 Reportes":
    st.subheader("Generación de Reportes Detallados por Periodo (PDF)")

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data

    if not cursos:
        st.error("No tienes cursos creados. Ve a la sección de Configuración.")
    else:
        col_r1, col_r2, col_r3 = st.columns([2, 1, 1])

        with col_r1:
            opciones_cursos_rep = sorted([f"{r['grado'].strip()} | {r['materia'].strip()}" for r in cursos])
            sel_as_rep = st.selectbox("Seleccione el Curso:", opciones_cursos_rep, key="sel_curso_rep")
            ga_rep, ma_rep = [item.strip() for item in sel_as_rep.split(" | ")]

        with col_r2:
            periodo_rep = st.number_input("Filtrar por Periodo Académico:", min_value=1, max_value=4, value=1, step=1, key="num_periodo_rep")

        with col_r3:
            st.write("")
            st.write("")
            btn_generar = st.button("📊 Generar Reporte PDF", type="primary", use_container_width=True)

        if btn_generar:
            with st.spinner(f"Generando sábana detallada de {ga_rep} ({ma_rep}) - Periodo {periodo_rep}..."):
                todos_est_raw = supabase.table("estudiantes").select("documento, nombre, grado")\
                    .eq("profe_id", st.session_state.user).order("nombre").execute().data

                todos_est = [e for e in todos_est_raw if str(e.get('grado', '')).strip().upper() == ga_rep.strip().upper()]

                asistencia_data = supabase.table("asistencia").select("estudiante_id, fecha, tema")\
                    .eq("grado", ga_rep)\
                    .eq("materia", ma_rep)\
                    .eq("periodo", periodo_rep)\
                    .eq("profe_id", st.session_state.user).order("fecha").execute().data

            if not todos_est:
                st.error(f"No hay estudiantes matriculados en el grado {ga_rep}.")
            else:
                pdf_output_bytes = generar_pdf_reporte(todos_est, asistencia_data, ga_rep, ma_rep, periodo_rep)
                ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                pdf_file = io.BytesIO(pdf_output_bytes)
                
                st.info(f"📉 Sábana detallada (P{periodo_rep} - OFICIO/9PT) generada correctamente para {ga_rep} - {ma_rep}.")
                st.download_button(
                    label="📥 Descargar Reporte PDF Detallado (Sábana OFICIO 9PT)",
                    data=pdf_file,
                    file_name=f"Sabana_Asistencia_{ga_rep}_{ma_rep}_P{periodo_rep}_OFICIO_9PT_{ahora_co.strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# --- 5. REINICIO Y PANEL ADMIN ---
elif menu == "⚙️ Reinicio":
    st.subheader("Mantenimiento")
    if st.button("⚠️ BORRAR MIS DATOS"):
        supabase.table("asistencia").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("estudiantes").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("cursos").delete().eq("profe_id", st.session_state.user).execute()
        st.success("Datos eliminados correctamente.")
        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.expander("🛠️ Panel Programador"):
        m_k = st.text_input("Clave Master", type="password")
        if m_k == "AdminEdu2026":
            st.info("🔓 Sesión Admin")
            usuarios_data = supabase.table("usuarios").select("usuario, nombre, pregunta_seguridad").execute().data
            if usuarios_data:
                df_u = pd.DataFrame(usuarios_data)
                st.dataframe(df_u)
                st.markdown("### Resetear Clave")
                u_sel = st.selectbox("Seleccione el Profesor:", df_u['usuario'].tolist())
                n_pass = st.text_input("Nueva clave temporal:", type="password")
                if st.button("Actualizar Clave"):
                    supabase.table("usuarios").update({"password": hash_password(n_pass)}).eq("usuario", u_sel).execute()
                    st.success(f"Clave actualizada para {u_sel}.")

# --- PIE DE PÁGINA GLOBAL ---
st.markdown("---")
footer_html = f"""
    <div style='text-align: center; color: grey; font-size: 0.8rem;'>
        <b>{APP_NAME}</b> {APP_VERSION} | 
        Desarrollado por <b>{DEVELOPER_NAME}</b> | 
        &copy; 2026
    </div>
"""
st.markdown(footer_html, unsafe_allow_html=True)
