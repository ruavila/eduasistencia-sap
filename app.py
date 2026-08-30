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

# --- 2. ESTUDIANTES Y CARNETS (VERSIÓN CORREGIDA DE QR Y ARCHIVOS TEMPORALES) ---
elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y Carnetización")
    
    from reportlab.lib.pagesizes import letter 
    import tempfile

    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos])
        gs, ms = sel.split(" | ")
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        
        if f and st.button("Procesar y Generar PDF"):
            df = pd.read_excel(f)
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            pdf = io.BytesIO()
            canv = canvas.Canvas(pdf, pagesize=letter)
            ancho_pg, alto_pg = letter # 21.59cm x 27.94cm
            
            # Ajuste de márgenes iniciales
            x, y, col = 1.5*cm, alto_pg - 5*cm, 0
            
            for index, r in df.iterrows():
                # 1. Extracción limpia de ID / Documento
                e_id_raw = str(r.get('estudiante_id', r.get('documento', r.get('id', '')))).split('.')[0].strip()
                
                # Si el id viene vacío o es nan, asignamos un ID temporal único basado en el grado e índice
                if not e_id_raw or e_id_raw.lower() in ['nan', 'none', '']:
                    e_id = f"{gs.replace(' ', '')}_{index + 1}"
                else:
                    e_id = e_id_raw
                
                e_nm = str(r.get('nombre', '')).upper().strip()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                
                # 2. Registro / Actualización en Supabase
                supabase.table("estudiantes").upsert({
                    "documento": e_id, 
                    "nombre": e_nm, 
                    "whatsapp": e_ws, 
                    "grado": gs, 
                    "materia": ms, 
                    "profe_id": st.session_state.user
                }).execute()
                
                # 3. Generación de QR con Instancia Limpia por Estudiante
                qr_engine = qrcode.QRCode(
                    version=1, 
                    error_correction=qrcode.constants.ERROR_CORRECT_H, 
                    box_size=10, 
                    border=4
                )
                qr_engine.add_data(str(e_id))
                qr_engine.make(fit=True)
                img_qr = qr_engine.make_image(fill_color="black", back_color="white")
                
                # 4. Guardado en ruta temporal única sin bloqueo de archivo
                tmp_filename = f"qr_{gs}_{index}_{e_id}.png".replace("/", "_").replace("\\", "_")
                tmp_qr_path = os.path.join(tempfile.gettempdir(), tmp_filename)
                img_qr.save(tmp_qr_path)

                # 5. Dibujar imagen y textos en el PDF
                canv.drawInlineImage(tmp_qr_path, x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7)
                canv.drawCentredString(x + 2*cm, y - 0.4*cm, e_nm[:25])
                canv.setFont("Helvetica", 6)
                canv.drawCentredString(x + 2*cm, y - 0.8*cm, f"Grado: {gs} - {IE_INITIALS}")
                
                # 6. Eliminar inmediatamente la imagen del disco
                if os.path.exists(tmp_qr_path):
                    try:
                        os.remove(tmp_qr_path)
                    except Exception:
                        pass
                
                # 7. Lógica de cuadrícula para Hoja Carta Vertical
                col += 1
                if col >= 3: # 3 carnets por fila
                    x = 1.5*cm
                    y -= 6.0*cm
                    col = 0
                else: 
                    x += 6.5*cm
                
                # Salto de página
                if y < 2*cm: 
                    canv.showPage()
                    x, y, col = 1.5*cm, alto_pg - 5*cm, 0
                
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
elif menu == "📊 Reportes":
    # Importaciones necesarias para esta sección (asegúrate de tener fpdf2, pandas, datetime, io, os instalados)
    from fpdf import FPDF
    import pandas as pd
    import datetime as dt
    import io
    import os

    # Función auxiliar para formatear la fecha a DD-MM (para el PDF)
    def formatear_fecha_reporte(fecha_str):
        """Convierte una fecha YYYY-MM-DD a formato DD-MM."""
        if not fecha_str: return ""
        try:
            fecha_obj = dt.datetime.strptime(fecha_str, "%Y-%m-%d")
            return fecha_obj.strftime("%d-%m") # Solo día y mes
        except ValueError:
            return fecha_str

    st.subheader("Generación de Reportes Detallados por Periodo (PDF)")

    # 1. Consulta de cursos vinculados al docente
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data

    if cursos:
        # --- INTERFAZ DE FILTROS ACTUALIZADA ---
        col_r1, col_r2, col_r3 = st.columns([2, 1, 1])

        with col_r1:
            sel_as_rep = st.selectbox("Seleccione el Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos], key="sel_curso_rep")
            ga_rep, ma_rep = sel_as_rep.split(" | ")

        with col_r2:
            # Selección obligatoria del Periodo
            periodo_rep = st.number_input("Filtrar por Periodo Académico:", min_value=1, max_value=4, value=1, step=1, key="num_periodo_rep")

        with col_r3:
            st.write("") # Espaciadores
            st.write("")
            btn_generar = st.button("📊 Generar Reporte PDF", type="primary", use_container_width=True)

        # 2. Lógica al presionar el botón (Generar PDF Directo)
        if btn_generar:
            with st.spinner(f"Generando sábana detallada de {ga_rep} ({ma_rep}) - Periodo {periodo_rep}..."):
                # --- CONSULTAS A SUPABASE CON FILTRO DE PERIODO ---
                
                # A. Traer todos los estudiantes de ese grado (docente)
                todos_est = supabase.table("estudiantes").select("documento, nombre")\
                    .eq("grado", ga_rep)\
                    .eq("profe_id", st.session_state.user).order("nombre").execute().data

                # B. Traer registros de asistencia de ese curso Y PERIODO
                asistencia_data = supabase.table("asistencia").select("estudiante_id, fecha, tema")\
                    .eq("grado", ga_rep)\
                    .eq("materia", ma_rep)\
                    .eq("periodo", periodo_rep)\
                    .eq("profe_id", st.session_state.user).order("fecha").execute().data

            if todos_est and asistencia_data:
                # ==========================================================
                # --- PROCESAMIENTO DE DATOS CON PANDAS (SÁBANA DETALLADA) ---
                # ==========================================================
                # Crear DataFrame base con todos los estudiantes (mayúsculas y latin-1)
                df_reporte = pd.DataFrame(todos_est)
                df_reporte['nombre'] = df_reporte['nombre'].str.upper()
                try:
                    # Forzar latin-1 para compatibilidad si hay acentos
                    df_reporte['nombre'] = df_reporte['nombre'].str.encode('latin-1', 'ignore').str.decode('latin-1')
                except:
                    pass
                df_reporte = df_reporte.set_index('documento')
                
                # Crear DataFrame con asistencias
                df_asistencia = pd.DataFrame(asistencia_data)
                
                # Identificar clases únicas (Fecha/Tema) del periodo, ordenadas por fecha
                df_clases = df_asistencia[['fecha', 'tema']].drop_duplicates().sort_values('fecha')
                
                # Construir columnas dinámicas (Tema + Fecha DD-MM)
                columnas_dinamicas = []
                # El DataFrame base de los estudiantes es nuestro 'reporte_final'
                reporte_final = df_reporte.copy()

                for _, clase in df_clases.iterrows():
                    # REQUERIMIENTO: Solo día y mes (ej: 12-07)
                    fecha_fmt = formatear_fecha_reporte(clase['fecha'])
                    tema_raw = clase['tema']
                    try:
                        # Forzar latin-1 para el tema también
                        tema_latin = tema_raw.encode('latin-1', 'ignore').decode('latin-1')
                        encabezado_col = f"{tema_latin}\n{fecha_fmt}"
                    except:
                        encabezado_col = f"{tema_raw}\n{fecha_fmt}"
                    
                    columnas_dinamicas.append(encabezado_col)
                    # Inicializar columna dinámica con 'X' (Ausente) por defecto
                    reporte_final[encabezado_col] = 'X' 

                # Llenar 'V' (Presente) y calcular totales
                # El check V requiere codificación latin-1 específica para FPDF (código cuadrado aprox)
                check_pi_latin = 'V'.encode('latin-1', 'ignore').decode('latin-1')
                
                for registro in asistencia_data:
                    id_est = registro['estudiante_id']
                    if id_est in reporte_final.index:
                        tema_reg = registro['tema']
                        fecha_fmt_reg = formatear_fecha_reporte(registro['fecha'])
                        try:
                            tema_latin_reg = tema_reg.encode('latin-1', 'ignore').decode('latin-1')
                            col_pi = f"{tema_latin_reg}\n{fecha_fmt_reg}"
                        except:
                            col_pi = f"{tema_reg}\n{fecha_fmt_reg}"
                        
                        if col_pi in reporte_final.columns:
                            # Marcar presente con check corregido
                            reporte_final.loc[id_est, col_pi] = check_pi_latin

                # Calcular totales al final de cada fila
                df_aux = reporte_final[columnas_dinamicas]
                # Contar 'V' para Asistencias
                reporte_final['Asist'] = (df_aux == check_pi_latin).sum(axis=1)
                # Contar 'X' para Ausencias
                reporte_final['Ausen.'] = (df_aux == 'X').sum(axis=1)
                
                # Asegurar que los totales sean cadenas para MultiCell del PDF
                reporte_final['Asist'] = reporte_final['Asist'].astype(str)
                reporte_final['Ausen.'] = reporte_final['Ausen.'].astype(str)
                
                # Limpiar DataFrame: Índice numérico, Nombre como columna 'ESTUDIANTE', añadir N°
                reporte_final = reporte_final.reset_index()
                reporte_final = reporte_final.rename(columns={'nombre': 'ESTUDIANTE'})
                # Añadir columna de N° correlativo
                reporte_final.insert(0, 'N°', range(1, 1 + len(reporte_final)))
                # Convertir N° a string
                reporte_final['N°'] = reporte_final['N°'].astype(str)

                # ==========================================================
                # --- GENERACIÓN DEL REPORTE PDF CON FPDF2 (FORMATO SÁBANA DETALLADA) ---
                # ==========================================================
                # Crear objeto PDF (Horizontal L, mm, Legal/Oficio)
                pdf = FPDF('L', 'mm', 'Legal')
                pdf.add_page()
                # Márgenes ajustados para el tamaño Oficio
                pdf.set_margins(10, 10, 10)
                
                # --- RESTAURADO: RUTA DEL ESCUDO EN CARPETA ASSETS ---
                # Definir la ruta correcta de la imagen del escudo dentro de 'assets'
                escudo_path = os.path.join("assets", "escudo.png")
                if os.path.exists(escudo_path):
                    # Colocar escudo (x, y, ancho_w, alto_h)
                    pdf.image(escudo_path, 10, 8, 25, 25) # Escudo de 25x25mm
                
                # --- ENCABEZADO INSTITUCIONAL ---
                # Institución (desplazada a la derecha si hay escudo)
                pdf.set_font("Arial", 'B', 16)
                if os.path.exists(escudo_path):
                    pdf.set_x(40) # Mover a 40mm de la izquierda
                
                pdf.cell(0, 12, "Institución Educativa San Antonio de Padua", 0, 1, 'C')
                
                # Datos de la clase
                pdf.set_font("Arial", '', 11)
                if os.path.exists(escudo_path):
                    pdf.set_x(40)
                
                # Fila 1 (conservando tu modelo)
                pdf.cell(100, 7, f"Materia: {ma_rep}", 0, 0)
                pdf.cell(80, 7, f"Grado: {ga_rep}", 0, 0)
                pdf.cell(0, 7, f"Docente: {st.session_state.profe_nom}", 0, 1)
                
                if os.path.exists(escudo_path):
                    pdf.set_x(40)
                
                # Fila 2 (Añadido el Periodo)
                pdf.set_font("Arial", 'B', 11)
                ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                pdf.cell(100, 7, f"Fecha Reporte: {ahora_co.strftime('%d/%m/%Y')}", 0, 0)
                # CRÍTICO: Indica qué periodo se está consultando
                pdf.cell(0, 7, f"Periodo Académico Consultando: {periodo_rep}", 0, 1)
                
                pdf.ln(5) # Espacio antes de la tabla

                # --- TABLA DE DATOS (CUADRÍCULA SÁBANA EN OFICIO) ---
                # 1. DEFINIR ANCHOS DE COLUMNA (CRÍTICO para Horizontal en Oficio)
                # Ancho disponible aprox 335mm (Legal horizontal 355.6mm con márgenes de 10mm)
                num_clases = len(columnas_dinamicas)
                
                # Anchos fijos iniciales y finales (revisados para Oficio y fuente 9pt)
                w_num = 12
                w_est = 70  
                w_totales = 18 
                
                # Calcular ancho dinámico para las clases
                ancho_usado_fijo = w_num + w_est + (w_totales * 2)
                # El ancho disponible es de 335mm
                ancho_disponible_dinamico = 335 - ancho_usado_fijo
                
                if num_clases > 0:
                    w_clase = ancho_disponible_dinamico / num_clases
                else:
                    # Si no hay clases dadas, la tabla no se genera
                    w_clase = ancho_disponible_dinamico

                # 2. ENCABEZADOS DE LA TABLA (DOS LÍNEAS CON MULTICELL)
                # --- RESTAURADO: TAMAÑO DE FUENTE 9PT ---
                pdf.set_font("Arial", 'B', 9)
                pdf.set_fill_color(240, 240, 240) # Gris suave para encabezado
                
                # Fila 1 del encabezado (N°, ESTUDIANTE, Totales ocupan dos líneas)
                # Usamos Cell con alto 14 para los fijos
                pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) 
                pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
                
                # Columnas Dinámicas (MultiCell para dos líneas alto 7mm cada una)
                x_col = pdf.get_x()
                y_col = pdf.get_y()
                if num_clases > 0:
                    for enc_completo in columnas_dinamicas:
                        # MultiCell para el tema (7mm alto cada línea = 14mm total)
                        pdf.multi_cell(w_clase, 7, enc_completo, 1, 'C', 1)
                        
                        # Regresar posición para la siguiente columna (X, Y inicial de encabezado)
                        x_col += w_clase
                        pdf.set_xy(x_col, y_col)
                else:
                     pdf.cell(ancho_disponible_dinamico, 14, "Sin registros de asistencia en este periodo", 1, 0, 'C', 1)

                # Columnas Fijas Finales (alto 14mm)
                pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
                pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1) # Salto de línea final

                # 3. CONTENIDO DE LA TABLA (FILA POR ESTUDIANTE)
                # --- RESTAURADO: TAMAÑO DE FUENTE 9PT ---
                pdf.set_font("Arial", '', 9)
                
                # Iterar sobre las filas del DataFrame final
                for _, fila in reporte_final.iterrows():
                    # Fila por estudiante
                    pdf.cell(w_num, 8, fila['N°'], 1, 0, 'C')
                    # Nombre ya está en latin-1
                    pdf.cell(w_est, 8, fila['ESTUDIANTE'], 1, 0)
                    
                    # Iterar sobre las clases dinámicas (usando la lista que guardamos)
                    if num_clases > 0:
                        for col_din in columnas_dinamicas:
                            # Símbolo Presente (✔ corregido latin-1) o Ausente (X)
                            simbolo = fila[col_din]
                            pdf.cell(w_clase, 8, simbolo, 1, 0, 'C')
                    else:
                        pdf.cell(ancho_disponible_dinamico, 8, "", 1, 0)
                        
                    # Totales (ya están en string)
                    pdf.cell(w_totales, 8, fila['Asist'], 1, 0, 'C')
                    pdf.cell(w_totales, 8, fila['Ausen.'], 1, 1, 'C') # Salto de línea
                    
                    # Salto de página automático si la tabla es muy larga
                    # Ajuste de margen inferior para Oficio horizontal aprox 180mm
                    if pdf.get_y() > 180: 
                        pdf.add_page()
                        # Re-imprimir encabezados
                        pdf.set_font("Arial", 'B', 9)
                        pdf.set_fill_color(240, 240, 240)
                        # Re-imprimir N°, Estudiante, Totales (alto 14mm)
                        pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) 
                        pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
                        # Clases Dinámicas (MultiCell)
                        if num_clases > 0:
                            x_col_pg = pdf.get_x()
                            y_col_pg = pdf.get_y()
                            for enc_completo_pg in columnas_dinamicas:
                                pdf.multi_cell(w_clase, 7, enc_completo_pg, 1, 'C', 1)
                                x_col_pg += w_clase
                                pdf.set_xy(x_col_pg, y_col_pg)
                        # Totales Finales (alto 14mm)
                        pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
                        pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1)
                        # Regresar a fuente normal 9pt
                        pdf.set_font("Arial", '', 9)

                # ==========================================================
                # --- PREPARACIÓN DEL PDF EN MEMORIA (SOLUCIÓN DEFINITIVA 'bytearray') ---
                # ==========================================================
                
                # feedback visual
                st.info(f"📉 Sábana detallada (P{periodo_rep} - OFICIO/9PT) generada correctamente para {ga_rep} - {ma_rep}.")
                
                # --- MANTENIDA: CORRECCIÓN CRÍTICA DE DESCARGA ---
                # Con fpdf2 instalado, output(dest='S') ya devuelve directamente bytes (bytearray).
                # Eliminamos la línea que intentaba codificar manualmente.
                pdf_output_bytes = pdf.output(dest='S')
                
                # Convertir los bytes a un objeto BytesIO para Streamlit
                pdf_file = io.BytesIO(pdf_output_bytes)
                
                # Botón de descarga DIRECTA (sin previsualización de nada)
                # Actualizar el nombre del archivo indicando la fuente 9pt
                st.download_button(
                    label="📥 Descargar Reporte PDF Detallado (Sábana OFICIO 9PT)",
                    data=pdf_file,
                    file_name=f"Sabana_Asistencia_{ga_rep}_{ma_rep}_P{periodo_rep}_OFICIO_9PT_{ahora_co.strftime('%Y%M%d_%H%M')}.pdf",
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

# El botón de cerrar sesión debe ir al final
if st.session_state.logueado:
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logueado = False
        st.rerun()
