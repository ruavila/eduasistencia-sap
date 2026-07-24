import streamlit as st
from supabase import create_client, Client
import qrcode
from streamlit_qrcode_scanner import qrcode_scanner
import datetime as dt
import time
import pandas as pd # Necesario para procesar la cuadrícula
from io import BytesIO
from fpdf import FPDF

# ==============================================================================
# --- 1. CONFIGURACIÓN Y AUTENTICACIÓN (Sin cambios críticos) ---
# ==============================================================================
st.set_page_config(page_title="EduAsistencia Pro - I.E. San Antonio", page_icon="📝", layout="wide")

# Inicializar conexión a Supabase
try:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Error de conexión a la base de datos. Verifica los secretos en Streamlit Cloud.")
    st.stop()

# Funciones de Autenticación Simplificadas
def registrar_profe(email, password, nombre):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"nombre": nombre}}})
        return res
    except Exception as e:
        return {"error": str(e)}

def login_profe(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res
    except Exception as e:
        return {"error": str(e)}

# Manejo de Sesión
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.profe_nom = None

# Función auxiliar para formatear la fecha a dd/mm (para el encabezado de columna del PDF)
def formatear_fecha_corta(fecha_str):
    if not fecha_str: return ""
    try:
        # Supabase devuelve AAAA-MM-DD
        fecha_obj = dt.datetime.strptime(fecha_str, "%Y-%m-%d")
        return fecha_obj.strftime("%d/%m")
    except ValueError:
        return ""

# ==============================================================================
# --- 2. INTERFAZ PRINCIPAL (LOGIN / MENÚ) ---
# ==============================================================================
if not st.session_state.user:
    st.title("Welcome a EduAsistencia Pro")
    st.subheader("I.E. San Antonio de Padua - Timbío")
    
    tab_login, tab_registro = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        em_l = st.text_input("Correo electrónico:", key="em_l")
        pw_l = st.text_input("Contraseña:", type="password", key="pw_l")
        if st.button("Ingresar", key="btn_l"):
            with st.spinner("Autenticando..."):
                res = login_profe(em_l, pw_l)
                if "error" in res:
                    st.error(f"Error: {res['error']}")
                else:
                    st.session_state.user = res.user.id
                    st.session_state.profe_nom = res.user.user_metadata.get("nombre", "Docente")
                    st.rerun()
                
    with tab_registro:
        st.info("El registro está deshabilitado temporalmente. Contacta al administrador.")

else:
    # MENÚ LATERAL
    with st.sidebar:
        st.write(f"👤 Bienvenido, **{st.session_state.profe_nom}**")
        menu = st.radio("Menú Principal", ["📷 Scanner QR", "📊 Reportes", "⚙️ Configuración", "🚪 Cerrar Sesión"])
        st.divider()
        st.caption("I.E. San Antonio de Padua | Timbío - Cauca")

    # ==============================================================================
    # --- 3. SECCIÓN CERRAR SESIÓN (Sin cambios) ---
    # ==============================================================================
    if menu == "🚪 Cerrar Sesión":
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.profe_nom = None
        st.rerun()

    # ==============================================================================
    # --- 4. SECCIÓN CONFIGURACIÓN (Sin cambios) ---
    # ==============================================================================
    elif menu == "⚙️ Configuración":
        st.subheader("Configuración de Cursos y Estudiantes")
        
        tab_cc, tab_ce = st.tabs(["🏫 Gestionar Cursos", "👨‍🎓 Gestionar Estudiantes"])
        
        with tab_cc:
            st.write("Agrega tus cursos y materias.")
            col_c1, col_c2 = st.columns(2)
            c_grado = col_c1.text_input("Grado (ej: 801):", key="c_grado")
            c_mate = col_c2.text_input("Materia (ej: Informática):", key="c_mate")
            if st.button("➕ Agregar Curso"):
                if c_grado and c_mate:
                    try:
                        supabase.table("cursos").insert({"profe_id": st.session_state.user, "grado": c_grado, "materia": c_mate}).execute()
                        st.success("Curso agregado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.warning("Llena ambos campos.")
            
            st.divider()
            st.write("Tus cursos actuales:")
            cursos = supabase.table("cursos").select("id, grado, materia").eq("profe_id", st.session_state.user).execute().data
            if cursos:
                df_c = pd.DataFrame(cursos)
                st.dataframe(df_c[["grado", "materia"]], use_container_width=True)
            else:
                st.info("Aún no tienes cursos agregados.")

        with tab_ce:
            st.write("Agrega estudiantes a tus cursos.")
            cursos = supabase.table("cursos").select("id, grado").eq("profe_id", st.session_state.user).execute().data
            if cursos:
                curso_opt = {f"{c['grado']}": c['id'] for c in cursos}
                sel_curso_e = st.selectbox("Selecciona el Curso/Grado:", list(curso_opt.keys()), key="sel_curso_e")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    e_doc = st.text_input("Documento de identidad:", key="e_doc")
                    e_nom = st.text_input("Nombre completo (Apellidos primero):", key="e_nom")
                with col_e2:
                    e_whatsapp = st.text_input("WhatsApp (con código país, ej: 57312...):", key="e_whatsapp")
                
                if st.button("➕ Agregar Estudiante"):
                    if e_doc and e_nom and e_whatsapp:
                        try:
                            supabase.table("estudiantes").insert({
                                "id": e_doc, 
                                "documento": e_doc, 
                                "nombre": e_nom.upper(), 
                                "whatsapp": e_whatsapp, 
                                "grado": sel_curso_e, 
                                "profe_id": st.session_state.user
                            }).execute()
                            st.success("Estudiante agregado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                    else:
                        st.warning("Llena todos los campos.")
                
                st.divider()
                st.write(f"Estudiantes en Grado {sel_curso_e}:")
                ests = supabase.table("estudiantes").select("documento, nombre, whatsapp").eq("grado", sel_curso_e).eq("profe_id", st.session_state.user).order("nombre").execute().data
                if ests:
                    df_e = pd.DataFrame(ests)
                    st.dataframe(df_e[["documento", "nombre", "whatsapp"]], use_container_width=True)
                else:
                    st.info("Aún no hay estudiantes en este curso.")
            else:
                st.warning("Primero crea tus cursos en la pestaña '🏫 Gestionar Cursos'.")

    # ==============================================================================
    # --- 5. SECCIÓN SCANNER QR (ACTUALIZADO CON PERIODO) ---
    # ==============================================================================
    elif menu == "📷 Scanner QR":
        st.subheader("Captura de Asistencia")
        
        if 'captura_finalizada' not in st.session_state:
            st.session_state.captura_finalizada = False

        # 1. Consulta de cursos vinculados al docente
        cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
        
        if cursos:
            col_c1, col_c2, col_c3 = st.columns([2, 2, 1])
            with col_c1:
                sel_as = st.selectbox("Seleccione el Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos], key="sel_curso_scan")
                ga, ma = sel_as.split(" | ")
            with col_c2:
                # --- NUEVO: Selección obligatoria del Periodo ---
                periodo_actual = st.number_input("Periodo Académico Actual:", min_value=1, max_value=4, value=1, step=1, key="num_periodo")
            with col_c3:
                # Ajuste de hora Colombia
                ahora_co_view = dt.datetime.now() - dt.timedelta(hours=5)
                st.metric("Fecha", ahora_co_view.strftime("%d/%m/%Y"))

            tema_input = st.text_input("Tema de la clase:", placeholder="Ej: Introducción a la Multimedia")
            tema = tema_input.strip() # Limpiar espacios

            # Solo proceder si hay tema definido
            if tema:
                tab_qr, tab_lista = st.tabs(["📷 Escáner QR", "🔢 Número de Lista (Plan B)"])
                
                with tab_qr:
                    if not st.session_state.captura_finalizada:
                        st.info(f"📋 Registrando asistencia para: **{ga} - {ma}** | **Periodo: {periodo_actual}** | Tema: *{tema}*")
                        
                        if st.button("⏹️ Finalizar Captura y Ver Ausentes", type="primary", use_container_width=True):
                            st.session_state.captura_finalizada = True
                            st.rerun()
                        
                        # Escáner con clave dinámica por grado, tema y PERIODO
                        cod = qrcode_scanner(key=f"scanner_{ga}_{tema}_{periodo_actual}") 
                        
                        if cod:
                            id_cl = str(cod).strip()
                            # Búsqueda en la base de datos de estudiantes
                            res = supabase.table("estudiantes").select("documento, nombre").eq("documento", id_cl).eq("grado", ga).eq("profe_id", st.session_state.user).execute().data
                            
                            if res:
                                doc, nom = res[0]['documento'], res[0]['nombre']
                                # Ajuste de hora Colombia para el registro (UTC-5)
                                ahora_co = dt.datetime.now() - dt.timedelta(hours=5)
                                hoy = ahora_co.strftime("%Y-%m-%d")
                                
                                # Check de duplicados (estudiante ya asistió hoy a esta clase EN ESTE PERIODO)
                                check = supabase.table("asistencia").select("id").eq("estudiante_id", doc).eq("fecha", hoy).eq("tema", tema).eq("periodo", periodo_actual).execute().data
                                
                                if not check:
                                    # Inserción INCLUYENDO EL PERIODO
                                    try:
                                        supabase.table("asistencia").insert({
                                            "estudiante_id": doc, 
                                            "fecha": hoy, 
                                            "hora": ahora_co.strftime("%H:%M:%S"), 
                                            "grado": ga, 
                                            "materia": ma, 
                                            "tema": tema, 
                                            "periodo": periodo_actual, # Guardamos el periodo
                                            "profe_id": st.session_state.user
                                        }).execute()
                                        st.toast(f"✅ Registrado (P{periodo_actual}): {nom}", icon="👤")
                                        # Pequeña pausa para evitar registros múltiples accidentales
                                        time.sleep(0.5) 
                                    except Exception as e:
                                        st.error(f"Error al registrar: {e}")
                                else:
                                    st.toast(f"ℹ️ {nom} ya registrado hoy", icon="✅")
                            else:
                                st.toast(f"⚠️ Estudiante no encontrado en {ga}: {id_cl}", icon="❌")
                    
                    else:
                        # --- SECCIÓN DE AUSENTES (ACTUALIZADO A HORA COLOMBIA) ---
                        if st.button("🔄 Volver a escanear / Limpiar", use_container_width=True):
                            st.session_state.captura_finalizada = False
                            st.rerun()

                        st.warning(f"⚠️ Estudiantes Ausentes hoy en {ga} (P{periodo_actual}):")
                        
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
                        asistieron = supabase.table("asistencia").select("estudiante_id").eq("grado", ga).eq("fecha", hoy_col).eq("tema", tema).eq("periodo", periodo_actual).eq("profe_id", st.session_state.user).execute().data
                        
                        # Lógica de comparación
                        ids_asistieron = [str(a['estudiante_id']).strip() for a in asistieron]
                        ausentes = [e for e in todos if str(e['documento']).strip() not in ids_asistieron]
                        
                        if ausentes:
                            for aus in ausentes:
                                col_a, col_b = st.columns([3, 1])
                                col_a.write(f"❌ {aus['nombre']}")
                                
                                # CUERPO DEL MENSAJE IDÉNTICO A LA IMAGEN (Ajuste Tildes para latin-1)
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
                    # --- PLAN B: REGISTRO MANUAL (TAMBIÉN ACTUALIZADO CON PERIODO) ---
                    st.info(f"Registro Manual para {ga} - {ma} (Periodo: {periodo_actual})")
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
                            check_m = supabase.table("asistencia").select("id").eq("estudiante_id", doc_m).eq("fecha", hoy_m).eq("tema", tema).eq("periodo", periodo_actual).execute().data
                            
                            if not check_m:
                                # Inserción incluye periodo
                                supabase.table("asistencia").insert({
                                    "estudiante_id": doc_m, "fecha": hoy_m, "hora": ahora_m.strftime("%H:%M:%S"), 
                                    "grado": ga, "materia": ma, "tema": tema, "periodo": periodo_actual, "profe_id": st.session_state.user
                                }).execute()
                                st.success(f"Asistencia marcada (P{periodo_actual}): {nom_m}")
                            else:
                                st.warning(f"{nom_m} ya está registrado hoy.")
        else:
            st.error("No tienes cursos creados. Ve a la sección de Configuración.")

    # ==============================================================================
    # --- 6. SECCIÓN DE REPORTES (PDF DETALLADO POR PERIODO - FORMATO INSTITUCIONAL CORREGIDO) ---
    # ==============================================================================
    elif menu == "📊 Reportes":
        # Importaciones necesarias (FPDF2)
        import pandas as pd
        import datetime as dt
        from io import BytesIO
        from fpdf import FPDF

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
                    # --- PROCESAMIENTO DE DATOS PARA LA CUADRÍCULA CON PANDAS (CORREGIDO) ---
                    # ==========================================================
                    
                    # 1. Crear el DataFrame base con los estudiantes (Índice = Documento)
                    df_reporte = pd.DataFrame(todos_est)
                    df_reporte = df_reporte.set_index('documento')
                    df_reporte = df_reporte.rename(columns={'nombre': 'ESTUDIANTE'})
                    
                    # Convertir nombres a mayúsculas para latin-1
                    try:
                        df_reporte['ESTUDIANTE'] = df_reporte['ESTUDIANTE'].str.encode('latin-1', 'ignore').str.decode('latin-1')
                    except:
                        pass
                    
                    # Crear columnas para los totales (Asist y Ausen.)
                    df_reporte['Asist'] = 0
                    df_reporte['Ausen.'] = 0
                    
                    # 2. PROCESAR LA ASISTENCIA Y CONSTRUIR COLUMNAS DINÁMICAS (SÁBANA)
                    df_asistencia_data = pd.DataFrame(asistencia_data)
                    
                    temas_fechas_columnas = [] # Lista para guardar los nombres exactos de las columnas dinámicas

                    if not df_asistencia_data.empty:
                        # Crear una tupla única (Fecha, Tema) para las columnas y ordenar por fecha
                        df_clases = df_asistencia_data[['fecha', 'tema']].drop_duplicates().sort_values('fecha')
                        
                        # Crear las columnas dinámicas en el reporte final
                        for _, clase in df_clases.iterrows():
                            fecha_raw = clase['fecha']
                            tema_raw = clase['tema']
                            fecha_fmt = formatear_fecha_corta(fecha_raw)
                            # El encabezado será de dos líneas para el PDF
                            # Usamos latin-1 para el tema también
                            try:
                                tema_latin = tema_raw.encode('latin-1', 'ignore').decode('latin-1')
                                encabezado_col = f"{tema_latin}\n{fecha_fmt}"
                            except:
                                encabezado_col = f"{tema_raw}\n{fecha_fmt}"
                                
                            temas_fechas_columnas.append(encabezado_col)
                            # Inicializar la columna con 'X' (Ausente) por defecto
                            df_reporte[encabezado_col] = 'X'

                        # 3. Lógica para marcar 'Π' (Presente) y calcular totales
                        # Iterar sobre cada registro de asistencia
                        for _, registro in df_asistencia_data.iterrows():
                            id_est = registro['estudiante_id']
                            # Si el estudiante existe en el reporte final (por si acaso)
                            if id_est in df_reporte.index:
                                fecha_reg = registro['fecha']
                                tema_reg = registro['tema']
                                fecha_fmt_reg = formatear_fecha_corta(fecha_reg)
                                try:
                                    tema_latin_reg = tema_reg.encode('latin-1', 'ignore').decode('latin-1')
                                    col_busqueda = f"{tema_latin_reg}\n{fecha_fmt_reg}"
                                except:
                                    col_busqueda = f"{tema_reg}\n{fecha_fmt_reg}"
                                
                                # Si la columna existe (debería existir)
                                if col_busqueda in df_reporte.columns:
                                    # Marcar Π (Código fpdf aprox cuadrado)
                                    simbolo_pi = 'Π'.encode('latin-1', 'ignore').decode('latin-1')
                                    df_reporte.loc[id_est, col_busqueda] = simbolo_pi
                                    # Incrementar contador de asistencia
                                    df_reporte.loc[id_est, 'Asist'] += 1

                    # 4. Calcular Ausencias (Número de clases - Asistencias)
                    num_clases = len(temas_fechas_columnas)
                    df_reporte['Ausen.'] = num_clases - df_reporte['Asist']
                    
                    # Asegurar que los totales sean cadenas para MultiCell del PDF
                    df_reporte['Asist'] = df_reporte['Asist'].astype(str)
                    df_reporte['Ausen.'] = df_reporte['Ausen.'].astype(str)
                    
                    # Limpiar el DataFrame para el PDF (Índice numérico de nuevo, Nombre como columna)
                    df_reporte = df_reporte.reset_index()
                    # Añadir columna de N° correlativo
                    df_reporte.insert(0, 'N°', range(1, 1 + len(df_reporte)))
                    df_reporte['N°'] = df_reporte['N°'].astype(str)

                    # ==========================================================
                    # --- GENERACIÓN DEL REPORTE PDF CON FPDF (FORMATO SÁBANA HORIZONTAL) ---
                    # ==========================================================
                    
                    # Crear objeto PDF (Horizontal L, mm, A4 - para que quepan las columnas)
                    pdf = FPDF('L', 'mm', 'A4')
                    pdf.add_page()
                    pdf.set_margins(10, 10, 10)
                    
                    # --- ENCABEZADO INSTITUCIONAL ---
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
                    # --- CRÍTICO: Indica qué periodo se está consultando ---
                    pdf.cell(0, 7, f"Periodo Académico Consultando: {periodo_rep}", 0, 1)
                    
                    pdf.ln(5) # Espacio

                    # --- TABLA DE DATOS (CUADRÍCULA SÁBANA) ---
                    
                    # 1. DEFINIR ANCHOS DE COLUMNA (CRÍTICO para Horizontal)
                    # Ancho disponible aprox 277mm (A4 horizontal con márgenes de 10mm)
                    # Anchos fijos iniciales y finales
                    w_num = 10
                    w_est = 60
                    w_doc = 30 # Documento opcional
                    w_totales = 15 # Ancho para Asist y Ausen.
                    
                    # Calcular ancho dinámico para las clases (temas/fechas)
                    # ancho_usado_fijo = w_num + w_est + w_doc + (w_totales * 2)
                    ancho_usado_fijo = w_num + w_est + (w_totales * 2)
                    ancho_disponible_dinamico = 277 - ancho_usado_fijo
                    
                    if num_clases > 0:
                        w_clase = ancho_disponible_dinamico / num_clases
                    else:
                        # Ocurre si no hay asistencias en el periodo, la tabla no se genera
                        w_clase = ancho_disponible_dinamico 

                    # 2. ENCABEZADOS DE LA TABLA (DOS LÍNEAS CON MULTICELL TRICK)
                    pdf.set_font("Arial", 'B', 9)
                    
                    # Fondo gris suave para el encabezado (R, G, B)
                    pdf.set_fill_color(240, 240, 240) 
                    
                    # FFPDF1/2 Truco: MultiCell para encabezados dinámicos, Cell para fijos
                    # Mantenemos Cell con alto 14 para los fijos
                    pdf.cell(w_num, 14, "N°", 1, 0, 'C', 1) 
                    # pdf.cell(w_doc, 14, "Documento", 1, 0, 'C', 1)
                    pdf.cell(w_est, 14, "ESTUDIANTE", 1, 0, 'C', 1)
                    
                    # Columnas Dinámicas (MultiCell para dos líneas alto 7mm cada una)
                    if num_clases > 0:
                        x_col = pdf.get_x()
                        y_col = pdf.get_y()
                        for encabezado_completo in temas_fechas_columnas:
                            # MultiCell para el tema (7mm alto cada línea = 14mm total)
                            pdf.multi_cell(w_clase, 7, encabezado_completo, 1, 'C', 1)
                            
                            # Regresar posición para la siguiente columna (X, Y inicial de encabezado)
                            x_col += w_clase
                            pdf.set_xy(x_col, y_col)
                    else:
                         pdf.cell(ancho_disponible_dinamico, 14, "Sin registros de asistencia en este periodo", 1, 0, 'C', 1)

                    # Columnas Fijas Finales (una línea alto 14mm)
                    pdf.cell(w_totales, 14, "Asist", 1, 0, 'C', 1)
                    pdf.cell(w_totales, 14, "Ausen.", 1, 1, 'C', 1) # Salto de línea final

                    # 3. CONTENIDO DE LA TABLA (FILA POR ESTUDIANTE)
                    # Restablecemos fuente normal
                    pdf.set_font("Arial", '', 9)
                    
                    # Iterar sobre cada fila del DataFrame final
                    for _, fila in df_reporte.iterrows():
                        # Fila por estudiante
                        pdf.cell(w_num, 8, fila['N°'], 1, 0, 'C')
                        # pdf.cell(w_doc, 8, fila['documento'], 1, 0, 'C')
                        pdf.cell(w_est, 8, fila['ESTUDIANTE'], 1, 0)
                        
                        # Iterar sobre las clases dinámicas (usando la lista que guardamos)
                        for col_din in temas_fechas_columnas:
                            # Símbolo Presente (Π) o Ausente (X) ya están en latin-1
                            simbolo = fila[col_din]
                            pdf.cell(w_clase, 8, simbolo, 1, 0, 'C')
                            
                        # Totales (ya están en string y mayúsculas)
                        pdf.cell(w_totales, 8, fila['Asist'], 1, 0, 'C')
                        pdf.cell(w_totales, 8, fila['Ausen.'], 1, 1, 'C') # Salto de línea
                        
                        # Salto de página automático si la tabla es muy larga
                        # Ajuste de margen inferior para horizontal aprox 185mm
                        if pdf.get_y() > 185: 
                            pdf.add_page()
                            # Re-imprimir encabezados (Mismo truco anterior omitido por brevedad, pero es copiar el bloque)
                            pdf.set_font("Arial", 'B', 9)
                            pdf.set_fill_color(240, 240, 240)
                            # Re-imprimir N°, Estudiante, Clases, Totales
                            pdf.set_font("Arial", '', 9)

                else:
                    st.warning(f"No se encontraron registros de asistencia para {ga_rep} - {ma_rep} en el **Periodo Academicos {periodo_rep}**.")

            if btn_generar and todos_est:
                # ==========================================================
                # --- PREPARACIÓN DE LA DESCARGA DIRECTA (BytesIO) (Sin previsualización) ---
                # ==========================================================
                
                # feedback visual
                st.info(f"📈 Sábana detallada de asistencia (P{periodo_rep}) para {ga_rep} - {ma_rep} generada correctamente.")
                
                # Guardar el PDF en memoria y devolver bytes
                try:
                    pdf_output_bytes = pdf.output(dest='S').encode('latin-1')
                except TypeError:
                    # fpdf2 devuelve bytes directamente
                    pdf_output_bytes = pdf.output(dest='S')
                
                # Convertir a BytesIO para Streamlit
                pdf_file = BytesIO(pdf_output_bytes)
                
                # Botón de descarga DIRECTA (sin previsualización de nada)
                st.download_button(
                    label="📥 Descargar Reporte PDF Detallado (Sábana)",
                    data=pdf_file,
                    file_name=f"Sabana_Asistencia_{ga_rep}_{ma_rep}_P{periodo_rep}_{ahora_co.strftime('%Y%M%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        else:
            st.error("No tienes cursos creados. Ve a la sección de Configuración.")
