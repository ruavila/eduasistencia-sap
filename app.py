import streamlit as st
import pandas as pd
import qrcode
import io
import os
import urllib.parse
import tempfile
import time
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
APP_VERSION = "v2.2.0"
DEVELOPER_NAME = "Rubén Darío Ávila Sandoval"
IE_INITIALS = "I.E. S.A.P."
COLEGIO = "Institución Educativa San Antonio de Padua"
ESTADOS_ASISTENCIA = ["Presente", "Ausente", "Excusa Médica", "Permiso Institucional", "Llegada Tardía"]
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
                    except: 
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
            supabase.table("cursos").insert({"grado": g, "materia": m, "profe_id": st.session_state.user}).execute()
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
        opciones_cursos = sorted([f"{r['grado']} | {r['materia']}" for r in cursos])
        sel = st.selectbox("Curso:", opciones_cursos)
        
        gs, ms = sel.split(" | ")
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
                    except: pass
                
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

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    
    if cursos:
        col_tit, col_btn_cerrar = st.columns([3, 1])
        with col_btn_cerrar:
            if st.button("🔴 Cerrar Clase", use_container_width=True, help="Limpia la selección actual"):
                if 'captura_finalizada' in st.session_state:
                    st.session_state.captura_finalizada = False
                if 'sel_curso_scan' in st.session_state:
                    del st.session_state['sel_curso_scan']
                st.rerun()

        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            opciones_cursos = sorted(list(set([f"{str(r['grado']).strip()} | {str(r['materia']).strip()}" for r in cursos])))
            sel_as = st.selectbox("Curso:", opciones_cursos, key="sel_curso_scan")
            ga, ma = [item.strip() for item in sel_as.split(" | ")]
        
        with col_c2:
            periodo_actual = st.number_input("Periodo Actual:", min_value=1, max_value=4, value=1, step=1, key="num_periodo")
        
        tab_qr, tab_lista, tab_editar = st.tabs(["📷 Escáner QR", "🔢 Lista Manual", "✏️ Modificar Fechas Anteriores"])
        
        # --- TAB 1: ESCÁNER QR ---
        with tab_qr:
            tema_input = st.text_input("Tema de la clase:", placeholder="Ej: Introducción a la Multimedia", key="tema_qr")
            tema = tema_input.strip() 

            if tema:
                if not st.session_state.captura_finalizada:
                    st.info(f"📋 **{ga} - {ma}** | Periodo: **{periodo_actual}** | Tema: *{tema}*")
                    
                    if st.button("⏹️ Finalizar y Ver Ausentes", type="primary", use_container_width=True):
                        st.session_state.captura_finalizada = True
                        st.rerun()
                    
                    cod = qrcode_scanner(key=f"sc_{ga}_{ma}_{periodo_actual}".replace(" ", "_"))
                    
                    if cod:
                        id_cl = str(cod).strip()
                        res = supabase.table("estudiantes").select("documento, nombre, grado")\
                            .eq("documento", id_cl)\
                            .eq("grado", ga)\
                            .eq("profe_id", st.session_state.user).execute().data
                        
                        if res:
                            estudiante_encontrado = res[0]
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
                                    time.sleep(0.5)
                                except Exception as e:
                                    st.error(f"Error al guardar asistencia: {e}")
                            else:
                                st.toast(f"ℹ️ {nom} ya registrado hoy en P{periodo_actual}", icon="✅")
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
                    
                    saludo = "*Buenos días*" if ahora_col.hour < 12 else ("*Buenas tardes*" if ahora_col.hour < 18 else "*Buenas noches*")
                    
                    todos_est = supabase.table("estudiantes").select("documento, nombre, whatsapp, grado")\
                        .eq("profe_id", st.session_state.user)\
                        .eq("grado", ga).execute().data
                    
                    estudiantes_unicos = {}
                    for e in todos_est:
                        nom_clean = str(e.get('nombre', '')).strip().upper()
                        if nom_clean and nom_clean not in estudiantes_unicos:
                            estudiantes_unicos[nom_clean] = e
                    
                    estudiantes_curso = sorted(list(estudiantes_unicos.values()), key=lambda x: x['nombre'])
                    
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
                            
                            cuerpo_msj = (
                                f"{saludo}, señor(a) padre de familia o acudiente. "
                                f"La Institución Educativa San Antonio de Padua le informa que el estudiante "
                                f"*{aus['nombre']}* no se presentó el día de hoy a la clase de *{ma}* ({ga}).\n\n"
                                f"*Hora de reporte:* {hora_msj}\n"
                                f"*Tema tratado:* {tema}.\n\n"
                                f"Institucionalmente,\n\n"
                                f"*Docente:* {st.session_state.profe_nom}\n"
                                f"*Área:* {ma}"
                            )
                            
                            msg_encoded = urllib.parse.quote(cuerpo_msj)
                            num_wa = str(aus.get('whatsapp', '')).strip()
                            link_wa = f"https://wa.me/57{num_wa}?text={msg_encoded}"
                            col_b.markdown(f"[📲 Notificar]({link_wa})")
                    else:
                        st.success("🎉 ¡No hay reportes de inasistencia pendientes hoy!")
            else:
                st.info("Por favor ingresa el **Tema de la clase** arriba para activar la lectura QR.")

        # --- TAB 2: LISTA MANUAL ---
        with tab_lista:
            st.info(f"Registro Manual para **{ga} - {ma}** | Periodo: **{periodo_actual}**")
            
            tema_manual = st.text_input("Tema de la clase:", placeholder="Ej: Introducción a la Multimedia", key="tema_manual").strip()
            
            col_f1, col_f2 = st.columns([1, 1])
            with col_f1:
                fecha_sel = st.date_input("Fecha de Registro:", value=datetime.now())
                hoy_m = fecha_sel.strftime("%Y-%m-%d")
            with col_f2:
                estado_sel = st.selectbox("Estado del Registro:", ESTADOS_ASISTENCIA, index=0)
            
            if tema_manual:
                todos_est = supabase.table("estudiantes").select("documento, nombre, grado")\
                    .eq("profe_id", st.session_state.user).execute().data
                
                ga_limpio = str(ga).strip().lower()
                estudiantes_curso = []
                vistos = set()
                
                for e in sorted(todos_est, key=lambda x: x['nombre']):
                    g_est = str(e.get('grado', '')).strip().lower()
                    nom_est = str(e.get('nombre', '')).strip().upper()
                    
                    if (g_est == ga_limpio or ga_limpio in g_est) and nom_est not in vistos:
                        if "605" in ga_limpio and "701" in g_est:
                            continue
                        vistos.add(nom_est)
                        estudiantes_curso.append(e)
                
                if estudiantes_curso:
                    nombres_estudiantes = [f"{i+1}. {e['nombre']}" for i, e in enumerate(estudiantes_curso)]
                    
                    est_sel_nombre = st.selectbox(
                        "Seleccione el estudiante:", 
                        nombres_estudiantes, 
                        key=f"sel_man_{ga}_{ma}".replace(" ", "_")
                    )
                    
                    idx_seleccionado = nombres_estudiantes.index(est_sel_nombre)
                    
                    if st.button("✅ Registrar Asistencia Manual", use_container_width=True):
                        est_sel = estudiantes_curso[idx_seleccionado]
                        doc_m, nom_m = str(est_sel['documento']).strip(), est_sel['nombre']
                        ahora_m = dt.datetime.now() - dt.timedelta(hours=5)
                        
                        check_m = supabase.table("asistencia").select("id")\
                            .eq("estudiante_id", doc_m)\
                            .eq("fecha", hoy_m)\
                            .eq("materia", ma)\
                            .eq("periodo", periodo_actual).execute().data
                        
                        tema_guardar = f"{tema_manual} [{estado_sel}]" if estado_sel != "Presente" else tema_manual
                        
                        payload_manual = {
                            "estudiante_id": doc_m, 
                            "fecha": hoy_m, 
                            "hora": ahora_m.strftime("%H:%M:%S"), 
                            "grado": ga, 
                            "materia": ma, 
                            "tema": tema_guardar, 
                            "periodo": periodo_actual,
                            "profe_id": st.session_state.user
                        }
                        
                        if not check_m:
                            supabase.table("asistencia").insert(payload_manual).execute()
                            st.success(f"Registro guardado como **{estado_sel}** para: {nom_m} ({hoy_m})")
                            st.rerun()
                        else:
                            st.warning(f"El estudiante {nom_m} ya cuenta con registro para la fecha {hoy_m}.")
                else:
                    st.warning(f"No se encontraron estudiantes registrados para el grado {ga}.")
            else:
                st.info("Ingresa el tema de la clase antes de continuar.")

        # --- TAB 3: MODIFICAR FECHAS ANTERIORES (SELECCIÓN DINÁMICA DE FECHA Y TEMA) ---
        with tab_editar:
            st.info(f"Edición / Corrección de Asistencia para **{ga} - {ma}** (Periodo {periodo_actual})")

            # Consultar todas las fechas y temas donde hubo actividad para este curso/periodo
            clases_previas = supabase.table("asistencia").select("fecha, tema")\
                .eq("grado", ga)\
                .eq("materia", ma)\
                .eq("periodo", periodo_actual)\
                .eq("profe_id", st.session_state.user)\
                .order("fecha", desc=True).execute().data

            if clases_previas:
                # Filtrar fechas únicas con su respectivo tema base
                fechas_unicas = {}
                for c in clases_previas:
                    f_str = c['fecha']
                    if f_str not in fechas_unicas:
                        t_base = str(c['tema']).split(" [")[0].strip()
                        fechas_unicas[f_str] = t_base

                opciones_fechas = [f"📅 {fecha}  |  Tema: {tema}" for fecha, tema in fechas_unicas.items()]
                
                sel_fecha_lbl = st.selectbox("Seleccione la Clase Registrada a Modificar:", opciones_fechas, key="sel_f_historica")
                
                # Extraer la fecha y tema seleccionados
                fecha_mod_str = sel_fecha_lbl.split(" | ")[0].replace("📅 ", "").strip()
                tema_original = fechas_unicas[fecha_mod_str]

                st.markdown(f"📖 **Tema de la Clase Seleccionada:** *{tema_original}*")

                # Obtener TODOS los estudiantes del grado
                estudiantes_curso = supabase.table("estudiantes").select("documento, nombre")\
                    .eq("grado", ga)\
                    .eq("profe_id", st.session_state.user)\
                    .order("nombre").execute().data

                if estudiantes_curso:
                    # Obtener registros creados para esa fecha
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
    def formatear_fecha_reporte(fecha_str):
        if not fecha_str: return ""
        try:
            fecha_obj = dt.datetime.strptime(fecha_str, "%Y-%m-%d")
            return fecha_obj.strftime("%d-%m")
        except ValueError:
            return fecha_str

    st.subheader("Generación de Reportes Detallados por Periodo (PDF)")

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data

    if cursos:
        col_r1, col_r2, col_r3 = st.columns([2, 1, 1])

        with col_r1:
            opciones_cursos_rep = sorted([f"{r['grado']} | {r['materia']}" for r in cursos])
            sel_as_rep = st.selectbox("Seleccione el Curso:", opciones_cursos_rep, key="sel_curso_rep")
            ga_rep, ma_rep = sel_as_rep.split(" | ")

        with col_r2:
            periodo_rep = st.number_input("Filtrar por Periodo Académico:", min_value=1, max_value=4, value=1, step=1, key="num_periodo_rep")

        with col_r3:
            st.write("")
            st.write("")
            btn_generar = st.button("📊 Generar Reporte PDF", type="primary", use_container_width=True)

        if btn_generar:
            with st.spinner(f"Generando sábana detallada de {ga_rep} ({ma_rep}) - Periodo {periodo_rep}..."):
                todos_est = supabase.table("estudiantes").select("documento, nombre")\
                    .eq("grado", ga_rep)\
                    .eq("profe_id", st.session_state.user).order("nombre").execute().data

                asistencia_data = supabase.table("asistencia").select("estudiante_id, fecha, tema")\
                    .eq("grado", ga_rep)\
                    .eq("materia", ma_rep)\
                    .eq("periodo", periodo_rep)\
                    .eq("profe_id", st.session_state.user).order("fecha").execute().data

            if todos_est and asistencia_data:
                df_reporte = pd.DataFrame(todos_est)
                df_reporte['nombre'] = df_reporte['nombre'].str.upper()
                try:
                    df_reporte['nombre'] = df_reporte['nombre'].str.encode('latin-1', 'ignore').str.decode('latin-1')
                except: pass
                df_reporte = df_reporte.set_index('documento')
                
                df_asistencia = pd.DataFrame(asistencia_data)
                df_asistencia['tema_limpio'] = df_asistencia['tema'].apply(lambda x: x.split(" [")[0].strip() if " [" in str(x) else str(x).strip())
                
                df_clases = df_asistencia[['fecha', 'tema_limpio']].drop_duplicates().sort_values('fecha')
                
                columnas_dinamicas = []
                reporte_final = df_reporte.copy()

                for _, clase in df_clases.iterrows():
                    fecha_fmt = formatear_fecha_reporte(clase['fecha'])
                    tema_raw = clase['tema_limpio']
                    try:
                        tema_latin = tema_raw.encode('latin-1', 'ignore').decode('latin-1')
                        encabezado_col = f"{tema_latin}\n{fecha_fmt}"
                    except:
                        encabezado_col = f"{tema_raw}\n{fecha_fmt}"
                    
                    columnas_dinamicas.append(encabezado_col)
                    reporte_final[encabezado_col] = 'X' 

                check_pi_latin = 'V'.encode('latin-1', 'ignore').decode('latin-1')
                
                for registro in asistencia_data:
                    id_est = registro['estudiante_id']
                    if id_est in reporte_final.index:
                        tema_full = str(registro['tema'])
                        tema_reg = tema_full.split(" [")[0].strip() if " [" in tema_full else tema_full.strip()
                        fecha_fmt_reg = formatear_fecha_reporte(registro['fecha'])
                        
                        try:
                            tema_latin_reg = tema_reg.encode('latin-1', 'ignore').decode('latin-1')
                            col_pi = f"{tema_latin_reg}\n{fecha_fmt_reg}"
                        except:
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

                st.info(f"📉 Sábana detallada (P{periodo_rep} - OFICIO/9PT) generada correctamente para {ga_rep} - {ma_rep}.")
                
                pdf_output_bytes = pdf.output(dest='S')
                pdf_file = io.BytesIO(pdf_output_bytes)
                
                st.download_button(
                    label="📥 Descargar Reporte PDF Detallado (Sábana OFICIO 9PT)",
                    data=pdf_file,
                    file_name=f"Sabana_Asistencia_{ga_rep}_{ma_rep}_P{periodo_rep}_OFICIO_9PT_{ahora_co.strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            elif todos_est and not asistencia_data:
                st.warning(f"No se encontraron registros de asistencia para {ga_rep} - {ma_rep} en el **Periodo Académico {periodo_rep}**.")
            else:
                st.error("Error al consultar los datos de los estudiantes.")

    else:
        st.error("No tienes cursos creados. Ve a la sección de Configuración.")

# --- 5. REINICIO Y PANEL ADMIN ---
elif menu == "⚙️ Reinicio":
    st.subheader("Mantenimiento")
    if st.button("⚠️ BORRAR MIS DATOS"):
        supabase.table("asistencia").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("estudiantes").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("cursos").delete().eq("profe_id", st.session_state.user).execute()
        st.success("Datos eliminados correctamente."); st.rerun()

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
