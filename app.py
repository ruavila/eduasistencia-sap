import streamlit as st
import pandas as pd
import qrcode
import io
import os
import urllib.parse
import random
import tempfile
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.units import cm
from streamlit_qrcode_scanner import qrcode_scanner

# ==============================================================================
# --- CONSTANTES GLOBALES (Mover al inicio del archivo) ---
APP_NAME = "EduAsistencia-Pro"
APP_VERSION = "v2.1.0"
DEVELOPER_NAME = "Rubén Darío Ávila Sandoval" # <-- Pon tu nombre aquí
IE_INITIALS = "I.E. S.A.P."
COLEGIO = "Institución Educativa San Antonio de Padua" # Valor por defecto
# ==============================================================================

# --- INTEGRACIÓN CON MÓDULOS ---
try:
    from modules.database import supabase, hash_password
    from modules.config import APP_NAME, COLEGIO, ESCUDO_PATH
except Exception as e:
    st.error(f"Error al cargar módulos: {e}")
    APP_NAME = "EduAsistencia-Pro"
    COLEGIO = "Institución Educativa San Antonio de Padua"
    # Ruta al escudo en la carpeta assets
    ESCUDO_PATH = os.path.join("assets", "escudo.png") 

IE_INITIALS = "I.E. S.A.P."

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")

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
            # Insertamos nombre de la app, versión y desarrollador aquí
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
                else: st.error("Credenciales incorrectas.")
        
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
                    except: st.error("El usuario ya existe.")
                else: st.warning("Complete todos los campos.")

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
                        else: st.error("Respuesta incorrecta.")
    st.stop()

# --- CABECERA ---
col_esc, col_txt = st.columns([1, 4])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

menu = st.sidebar.radio("Navegación", ["📚 Cursos", "👤 Estudiantes", "📷 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

# --- 1. CURSOS ---
if menu == "📚 Cursos":
    st.subheader("Configuración de Cursos")
    g, m = st.text_input("Grado"), st.text_input("Asignatura")
    if st.button("Añadir Curso"):
        supabase.table("cursos").insert({"grado": g, "materia": m, "profe_id": st.session_state.user}).execute()
        st.rerun()
    
    res_c = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute()
    if res_c.data:
        df_c = pd.DataFrame(res_c.data)
        for _, r in df_c.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.info(f"{r['grado']} - {r['materia']}")
            if c2.button("🗑️", key=f"del_{r['id']}"):
                supabase.table("cursos").delete().eq("id", r['id']).execute()
                st.rerun()

# --- 2. ESTUDIANTES Y CARNETS ---
elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y Carnetización")
    
    # Importación necesaria para el tamaño carta si no la tienes arriba
    from reportlab.lib.pagesizes import letter 

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos])
        gs, ms = sel.split(" | ")
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        
        if f and st.button("Procesar y Generar PDF"):
            df = pd.read_excel(f)
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            pdf = io.BytesIO()
            # Cambio a letter (Carta) y quitamos el landscape para que sea vertical
            canv = canvas.Canvas(pdf, pagesize=letter)
            ancho_pg, alto_pg = letter # Dimensiones: 21.59cm x 27.94cm
            
            # Ajuste de márgenes iniciales
            x, y, col = 1.5*cm, alto_pg - 5*cm, 0
            
            for index, r in df.iterrows():
                e_id = str(r.get('estudiante_id', r.get('documento', ''))).split('.')[0].strip()
                e_nm = str(r.get('nombre', '')).upper().strip()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                
                # Registro en base de datos
                supabase.table("estudiantes").upsert({
                    "documento": e_id, "nombre": e_nm, "whatsapp": e_ws, 
                    "grado": gs, "materia": ms, "profe_id": st.session_state.user
                }).execute()
                
                # Generación de QR (Usando la lógica de instancia fresca para evitar duplicados)
                qr_engine = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
                qr_engine.add_data(e_id)
                qr_engine.make(fit=True)
                img_qr = qr_engine.make_image(fill_color="black", back_color="white")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{index}.png") as tmp_qr:
                    img_qr.save(tmp_qr.name)
                    tmp_qr_path = tmp_qr.name

                # Dibujar imagen y textos
                canv.drawInlineImage(tmp_qr_path, x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7)
                canv.drawCentredString(x + 2*cm, y-0.4*cm, e_nm[:25])
                canv.setFont("Helvetica", 6)
                canv.drawCentredString(x + 2*cm, y-0.8*cm, f"Grado: {gs} - {IE_INITIALS}")
                
                # --- Lógica de Cuadrícula para Hoja Carta Vertical ---
                col += 1
                if col >= 3: # 3 carnets por fila en vertical
                    x = 1.5*cm
                    y -= 6.0*cm # Espacio entre filas
                    col = 0
                else: 
                    x += 6.5*cm # Espacio entre columnas
                
                # Salto de página si se acaba el espacio vertical
                if y < 2*cm: 
                    canv.showPage()
                    x, y, col = 1.5*cm, alto_pg - 5*cm, 0
                
                os.remove(tmp_qr_path)
                
            canv.save()
            st.success(f"Se generaron carnets para {len(df)} estudiantes en formato Carta.")
            st.download_button("📥 Descargar Carnets", pdf.getvalue(), f"Carnets_{gs}.pdf")

# --- 3. SCANNER QR Y LISTA MANUAL (INTERFAZ SIMPLIFICADA) ---
elif menu == "📷 Scanner QR":
    import datetime as dt
    import time
    st.subheader("Captura de Asistencia por Periodo")
    
    if 'captura_finalizada' not in st.session_state:
        st.session_state.captura_finalizada = False

    # 1. Consulta de cursos vinculados al docente
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    
    if cursos:
        # --- INTERFAZ SIMPLIFICADA: Sin expander y sin fecha ---
        # Se organizan los elementos en columnas directas en la página
        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            sel_as = st.selectbox("Seleccione el Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos], key="sel_curso_scan")
            ga, ma = sel_as.split(" | ")
        
        with col_c2:
            # Entrada para el Periodo Académico
            periodo_actual = st.number_input("Periodo Actual:", min_value=1, max_value=4, value=1, step=1, key="num_periodo")
        
        # Entrada para el Tema de la clase
        tema_input = st.text_input("Tema de la clase:", placeholder="Ej: Introducción a la Multimedia")
        tema = tema_input.strip() 

        # Solo proceder si hay tema definido
        if tema:
            tab_qr, tab_lista = st.tabs(["📷 Escáner QR", "🔢 Número de Lista (Plan B)"])
            
            with tab_qr:
                if not st.session_state.captura_finalizada:
                    # Barra de información resumida
                    st.success(f"📋 **{ga} - {ma}** | Periodo: **{periodo_actual}** | Tema: *{tema}*")
                    
                    if st.button("⏹️ Finalizar Captura y Ver Ausentes", type="primary", use_container_width=True):
                        st.session_state.captura_finalizada = True
                        st.rerun()
                    
                    # Escáner con clave dinámica por grado y periodo
                    cod = qrcode_scanner(key=f"scanner_{ga}_{periodo_actual}") 
                    
                    if cod:
                        id_cl = str(cod).strip()
                        # Búsqueda en la base de datos de estudiantes
                        res = supabase.table("estudiantes").select("documento, nombre").eq("documento", id_cl).eq("grado", ga).eq("profe_id", st.session_state.user).execute().data
                        
                        if res:
                            doc, nom = res[0]['documento'], res[0]['nombre']
                            # Ajuste de hora Colombia para el registro (UTC-5)
                            ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                            hoy = ahora_co.strftime("%Y-%m-%d")
                            
                            # Check de duplicados incluye PERIODO
                            check = supabase.table("asistencia").select("id")\
                                .eq("estudiante_id", doc)\
                                .eq("fecha", hoy)\
                                .eq("tema", tema)\
                                .eq("periodo", periodo_actual).execute().data
                            
                            if not check:
                                # Inserción incluye PERIODO
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
                                    st.toast(f"✅ Registrado en P{periodo_actual}: {nom}", icon="👤")
                                    # Pequeña pausa para evitar registros múltiples accidentales
                                    time.sleep(0.5) 
                                except Exception as e:
                                    st.error(f"Error al registrar: {e}")
                            else:
                                st.toast(f"ℹ️ {nom} ya registrado hoy en P{periodo_actual}", icon="✅")
                        else:
                            st.toast(f"⚠️ Estudiante no encontrado en {ga}: {id_cl}", icon="❌")
                
                else:
                    # --- SECCIÓN DE AUSENTES ---
                    if st.button("🔄 Volver a escanear / Limpiar", use_container_width=True):
                        st.session_state.captura_finalizada = False
                        st.rerun()

                    st.warning(f"⚠️ Estudiantes Ausentes hoy en {ga} (Periodo {periodo_actual}):")
                    
                    # Tiempo local Colombia
                    ahora_col = dt.datetime.now() - dt.timedelta(hours=5)
                    hoy_col = ahora_col.strftime("%Y-%m-%d")
                    hora_msj = ahora_col.strftime("%I:%M %p")
                    
                    # Determinar saludo cordial en negrita
                    if ahora_col.hour < 12: saludo_bold = "*Buenos días*"
                    elif 12 <= ahora_col.hour < 18: saludo_bold = "*Buenas tardes*"
                    else: saludo_bold = "*Buenas noches*"

                    # Consultas a Supabase
                    todos = supabase.table("estudiantes").select("documento, nombre, whatsapp").eq("grado", ga).eq("profe_id", st.session_state.user).execute().data
                    
                    # Consulta de asistieron filtra por PERIODO
                    asistieron = supabase.table("asistencia").select("estudiante_id")\
                        .eq("grado", ga)\
                        .eq("fecha", hoy_col)\
                        .eq("tema", tema)\
                        .eq("periodo", periodo_actual)\
                        .eq("profe_id", st.session_state.user).execute().data
                    
                    # Lógica de comparación
                    ids_asistieron = [str(a['estudiante_id']).strip() for a in asistieron]
                    ausentes = [e for e in todos if str(e['documento']).strip() not in ids_asistieron]
                    
                    if ausentes:
                        for aus in ausentes:
                            col_a, col_b = st.columns([3, 1])
                            col_a.write(f"❌ {aus['nombre']}")
                            
                            # CUERPO DEL MENSAJE IDÉNTICO A LA IMAGEN
                            cuerpo_msj = (
                                f"{saludo_bold}, señor(a) padre de familia o acudiente. La Institución Educativa San "
                                f"Antonio de Padua le informa que el estudiante *{aus['nombre']}* no se "
                                f"presentó el día de hoy a la clase de *{ma}*.\n\n"
                                f"*Hora de reporte:* {hora_msj}\n"
                                f"*Tema tratado:* {tema}.\n\n"
                                f"Institucionalmente,\n\n"
                                f"*Docente:* {st.session_state.profe_nom}\n"
                                f"*Área:* {ma}"
                            )
                            
                            # Codificación para WhatsApp
                            msg_encoded = cuerpo_msj.replace(" ", "%20").replace("\n", "%0A")
                            link_wa = f"https://wa.me/57{aus['whatsapp']}?text={msg_encoded}"
                            col_b.markdown(f"[📲 Notificar]({link_wa})")
                    else:
                        st.success("¡Asistencia completa!")

            with tab_lista:
                # --- PLAN B: REGISTRO MANUAL ---
                st.info(f"Registro Manual para {ga} - {ma} | Periodo: {periodo_actual}")
                est_lista = supabase.table("estudiantes").select("documento, nombre").eq("grado", ga).eq("profe_id", st.session_state.user).order("nombre").execute().data
                
                if est_lista:
                    num_input = st.number_input("Número de lista:", min_value=1, max_value=len(est_lista), step=1, key="num_manual")
                    
                    if st.button("✅ Registrar por Número", use_container_width=True):
                        est_sel = est_lista[num_input - 1]
                        doc_m, nom_m = est_sel['documento'], est_sel['nombre']
                        # Hora Colombia Plan B
                        ahora_m = dt.datetime.now() - dt.timedelta(hours=5)
                        hoy_m = ahora_m.strftime("%Y-%m-%d")
                        
                        # Check duplicados incluye periodo
                        check_m = supabase.table("asistencia").select("id")\
                            .eq("estudiante_id", doc_m)\
                            .eq("fecha", hoy_m)\
                            .eq("tema", tema)\
                            .eq("periodo", periodo_actual).execute().data
                        
                        if not check_m:
                            # Inserción incluye periodo
                            supabase.table("asistencia").insert({
                                "estudiante_id": doc_m, "fecha": hoy_m, "hora": ahora_m.strftime("%H:%M:%S"), 
                                "grado": ga, "materia": ma, "tema": tema, "periodo": periodo_actual, "profe_id": st.session_state.user
                            }).execute()
                            st.success(f"Asistencia marcada (P{periodo_actual}): {nom_m}")
                        else:
                            st.warning(f"{nom_m} ya está registrado hoy en P{periodo_actual}.")
    else:
        st.error("No tienes cursos creados. Ve a la sección de Configuración.")
# ==============================================================================
# --- 4. SECCIÓN DE REPORTES (PDF DETALLADO POR PERIODO - FORMATO INSTITUCIONAL) ---
# ==============================================================================
elif menu == "📊 Reportes":
    # 1. Importaciones necesarias (se mueven aquí para mayor orden)
    import streamlit as st
    from fpdf import FPDF
    import datetime as dt
    import time
    from io import BytesIO
    import pandas as pd # Necesario para procesar la cuadrícula

    # Función auxiliar para formatear la fecha a dd/mm (para el encabezado de columna)
    def formatear_fecha_corta(fecha_str):
        if not fecha_str: return ""
        try:
            # Supabase devuelve AAAA-MM-DD
            fecha_obj = dt.datetime.strptime(fecha_str, "%Y-%m-%d")
            return fecha_obj.strftime("%d/%m")
        except ValueError:
            return ""

    st.subheader("Generación de Reportes de Asistencia Detallado (PDF)")

    # 1. Consulta de cursos vinculados al docente
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data

    if cursos:
        # --- INTERFAZ DE FILTROS ACTUALIZADA ---
        col_r1, col_r2, col_r3 = st.columns([2, 1, 1])

        with col_r1:
            sel_as_rep = st.selectbox("Seleccione el Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos], key="sel_curso_rep")
            ga_rep, ma_rep = sel_as_rep.split(" | ")

        with col_r2:
            # --- NUEVO: Selección obligatoria del Periodo ---
            periodo_rep = st.number_input("Filtrar por Periodo:", min_value=1, max_value=4, value=1, step=1, key="num_periodo_rep")

        with col_r3:
            st.write("") # Espaciadores para alinear el botón
            st.write("")
            btn_generar = st.button("📊 Generar Reporte PDF", type="primary", use_container_width=True)

        # 2. Lógica al presionar el botón
        if btn_generar:
            # Feedback visual de carga
            with st.spinner(f"Generando cuadrícula detallada de {ga_rep} ({ma_rep}) - Periodo {periodo_rep}..."):
                
                # --- CONSULTAS A SUPABASE CON FILTRO DE PERIODO ---
                
                # A. Traer todos los estudiantes de ese grado
                todos_est = supabase.table("estudiantes").select("documento, nombre")\
                    .eq("grado", ga_rep)\
                    .eq("profe_id", st.session_state.user).order("nombre").execute().data

                # B. Traer TODOS los registros de asistencia de ese curso Y PERIODO (ordenados por fecha)
                asistencia_data = supabase.table("asistencia").select("estudiante_id, fecha, tema")\
                    .eq("grado", ga_rep)\
                    .eq("materia", ma_rep)\
                    .eq("periodo", periodo_rep)\
                    .eq("profe_id", st.session_state.user).order("fecha").execute().data

            if todos_est:
                # ==========================================================
                # --- PROCESAMIENTO DE DATOS PARA LA CUADRÍCULA (TIPO SÁBANA) ---
                # ==========================================================
                
                # Crear un conjunto único de (Fecha, Tema) para las columnas
                # Esto nos dará todas las clases dadas en ese periodo
                temas_fechas = sorted(list(set([(a['fecha'], a['tema']) for a in asistencia_data])), key=lambda x: x[0])
                
                # Inicializar el diccionario de datos para la sábana
                # Columnas fijas iniciales
                matriz_data = {
                    'N°': [],
                    'ESTUDIANTE': []
                }
                
                # Crear columnas dinámicas (ej: "12/04\nTema X")
                for fecha_raw, tema_raw in temas_fechas:
                    fecha_fmt = formatear_fecha_corta(fecha_raw)
                    # El encabezado será de dos líneas para el PDF
                    encabezado_col = f"{tema_raw}\n{fecha_fmt}"
                    matriz_data[encabezado_col] = []
                    
                # Columnas fijas finales
                matriz_data['Asist'] = []
                matriz_data['Ausen.'] = []
                
                # Llenar la matriz estudiante por estudiante
                count_est = 1
                for est in todos_est:
                    id_est = est['documento']
                    matriz_data['N°'].ko_add(str(count_est))
                    # Limpiar nombre para PDF (latin-1)
                    try:
                        nombre_latin = est['nombre'].encode('latin-1', 'ignore').decode('latin-1')
                        matriz_data['ESTUDIANTE'].add(nombre_latin)
                    except:
                        matriz_data['ESTUDIANTE'].add(est['nombre'])
                    
                    cont_asist = 0
                    cont_ausen = 0
                    
                    # Iterar sobre cada clase (columna dinámica)
                    for fecha_raw, tema_raw in temas_fechas:
                        fecha_fmt = formatear_fecha_corta(fecha_raw)
                        encabezado_col = f"{tema_raw}\n{fecha_fmt}"
                        
                        # Buscar si este estudiante asistió a ESTA clase específica (fecha y tema)
                        # Nota: Si usas Opción B (tabla periodos), el filtro de tema es menos necesario
                        check_asist = [a for a in asistencia_data if a['estudiante_id'] == id_est and a['fecha'] == fecha_raw and a['tema'] == tema_raw]
                        
                        if check_asist:
                            matriz_data[encabezado_col].add('Π') # Presente (Código latin-1 aprox para el cuadrado)
                            cont_asist += 1
                        else:
                            matriz_data[encabezado_col].add('X') # Ausente
                            cont_ausen += 1
                            
                    # Llenar totales
                    matriz_data['Asist'].add(str(cont_asist))
                    matriz_data['Ausen.'].add(str(cont_ausen))
                    count_est += 1

                # ==========================================================
                # --- GENERACIÓN DEL REPORTE PDF CON FPDF (RECREANDO EL FORMATO) ---
                # ==========================================================
                
                # Crear objeto PDF (Horizontal L, mm, A4 - para que quepan las columnas)
                pdf = FPDF('L', 'mm', 'A4')
                pdf.add_page()
                pdf.set_margins(10, 10, 10)
                
                # --- ENCABEZADO IDÉNTICO AL ANTERIOR ---
                # Institución
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, "Institución Educativa San Antonio de Padua", 0, 1, 'C')
                
                # Datos de la clase
                pdf.set_font("Arial", '', 11)
                # Fila 1
                pdf.cell(100, 7, f"Materia: {ma_rep}", 0, 0)
                pdf.cell(80, 7, f"Grado: {ga_rep}", 0, 0)
                pdf.cell(0, 7, f"Docente: {st.session_state.profe_nom}", 0, 1)
                
                # Fila 2 (Añadido el Periodo)
                pdf.set_font("Arial", 'B', 11)
                # Hora Colombia (UTC-5)
                ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                pdf.cell(100, 7, f"Fecha Reporte: {ahora_co.strftime('%d/%m/%Y %H:%M')}", 0, 0)
                pdf.cell(0, 7, f"Periodo Académico: {periodo_rep}", 0, 1)
                
                pdf.ln(5) # Espacio

                # --- TABLA DE DATOS (CUADRÍCULA SÁBANA) ---
                
                # 1. DEFINIR ANCHOS DE COLUMNA (CRÍTICO)
                # Ancho disponible aprox 277mm (A4 horizontal con márgenes)
                # Anchos fijos iniciales y finales
                w_num = 10
                w_est = 60
                w_totales = 15 # Ancho para Asist y Ausen.
                
                # Calcular ancho dinámico para las clases
                num_clases = len(temas_fechas)
                ancho_usado_fijo = w_num + w_est + (w_totales * 2)
                ancho_disponible_dinamico = 277 - ancho_usado_fijo
                
                if num_clases > 0:
                    w_clase = ancho_disponible_dinamico / num_clases
                else:
                    w_clase = ancho_disponible_dinamico # Ocurre si no hay asistencias

                # 2. ENCABEZADOS DE LA TABLA (DOS LÍNEAS)
                pdf.set_font("Arial", 'B', 9)
                
                # Fondo gris suave para el encabezado (R, G, B)
                pdf.set_fill_color(240, 240, 240) 
                
                # Fila 1 del encabezado (N°, ESTUDIANTE, Temas, Totales)
                # Usamos MultiCell para permitir el salto de línea en los temas
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                
                # Columnas Fijas Iniciales (una línea)
                pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) # Alto 14 para ocupar dos líneas
                pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
                
                # Columnas Dinámicas (MultiCell para dos líneas)
                for fecha_raw, tema_raw in temas_fechas:
                    fecha_fmt = formatear_fecha_corta(fecha_raw)
                    encabezado_completo = f"{tema_raw}\n{fecha_fmt}"
                    # Guardar posición actual
                    x_col = pdf.get_x()
                    y_col = pdf.get_y()
                    
                    # MultiCell para el tema (7mm alto cada línea = 14mm total)
                    pdf.multi_cell(w_clase, 7, encabezado_completo, 1, 'C', 1)
                    
                    # Regresar posición para la siguiente columna (X, Y inicial)
                    pdf.set_xy(x_col + w_clase, y_col)
                    
                # Columnas Fijas Finales (una línea)
                pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
                pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1) # Salto de línea final

                # 3. CONTENIDO DE LA TABLA (FILA POR ESTUDIANTE)
                pdf.set_font("Arial", '', 9)
                
                # Obtener la lista de nombres de columnas dinámicas (para iterar)
                columnas_dinamicas_nombres = [k for k in matriz_data.keys() if '\n' in k]
                
                # Iterar sobre las filas (usando el índice de una de las columnas)
                num_filas = len(matriz_data['N°'])
                for i in range(num_filas):
                    # Fila por estudiante
                    pdf.cell(w_num, 8, matriz_data['N°'][i], 1, 0, 'C')
                    pdf.cell(w_est, 8, matriz_data['ESTUDIANTE'][i], 1, 0)
                    
                    # Iterar sobre las clases
                    for col_din in columnas_dinamicas_nombres:
                        # Cuadrado (Π) o X
                        simbolo = matriz_data[col_din][i]
                        # Asegurar compatibilidad latin-1 para Π si es necesario
                        if simbolo == 'Π': simbolo = simbolo.encode('latin-1', 'ignore').decode('latin-1')
                        pdf.cell(w_clase, 8, simbolo, 1, 0, 'C')
                        
                    # Totales
                    pdf.cell(w_totales, 8, matriz_data['Asist'][i], 1, 0, 'C')
                    pdf.cell(w_totales, 8, matriz_data['Ausen.'][i], 1, 1, 'C') # Salto de línea
                    
                    # Salto de página automático si la tabla es muy larga
                    if pdf.get_y() > 185: # Margen inferior aprox para horizontal
                        pdf.add_page()
                        # Re-imprimir encabezados
                        pdf.set_font("Arial", 'B', 9)
                        pdf.set_fill_color(240, 240, 240)
                        pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1)
                        pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
                        for fecha_raw, tema_raw in temas_fechas:
                            encabezado_completo = f"{tema_raw}\n{formatear_fecha_corta(fecha_raw)}"
                            x_col = pdf.get_x()
                            y_col = pdf.get_y()
                            pdf.multi_cell(w_clase, 7, encabezado_completo, 1, 'C', 1)
                            pdf.set_xy(x_col + w_clase, y_col)
                        pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
                        pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1)
                        pdf.set_font("Arial", '', 9)

                # ==========================================================
                # --- PREPARACIÓN DE LA DESCARGA DIRECTA ---
                # ==========================================================
                
                # Guardar el PDF en memoria
                try:
                    pdf_output_bytes = pdf.output(dest='S').encode('latin-1')
                except TypeError:
                    # Dependiendo de la versión de fpdf
                    pdf_output_bytes = pdf.output(dest='S')
                
                # Convertir a BytesIO
                pdf_file = BytesIO(pdf_output_bytes)

                # Mensaje de éxito
                st.success(f"📈 Sábana detallada de asistencia (P{periodo_rep}) para {ga_rep} - {ma_rep} generada.")
                
                # Botón de descarga DIRECTA (sin previsualización)
                st.download_button(
                    label="📥 Descargar Reporte PDF Detallado (Sábana)",
                    data=pdf_file,
                    file_name=f"Sabana_Asistencia_{ga_rep}_{ma_rep}_P{periodo_rep}_{ahora_co.strftime('%Y%M%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            elif todos_est and not asistencia_data:
                st.warning(f"No se encontraron registros de asistencia para {ga_rep} - {ma_rep} en el **Periodo {periodo_rep}**.")
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

# El botón de cerrar sesión debe ir al final
if st.session_state.logueado:
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logueado = False
        st.rerun()
