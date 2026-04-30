# =================================================================
# PROYECTO: eduasistencia-pro 
# INSTITUCIÓN: I.E. San Antonio de Padua - Sede Timbío
# FUNCIÓN: Gestión de Asistencia y Generación de QR (Versión Migrada)
# =================================================================

import streamlit as st
import sqlite3
import qrcode
import pandas as pd
import datetime
import time
from io import BytesIO
from PIL import Image

# --- CONFIGURACIÓN GLOBAL DE LA INTERFAZ ---
st.set_page_config(
    page_title="eduasistencia-pro | Gestión Escolar",
    page_icon="🔖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PERSONALIZADOS (Líneas 25-50) ---
def local_css():
    st.markdown("""
        <style>
        .main { background-color: #f8f9fa; }
        .stMetric { border: 1px solid #d1d5db; padding: 10px; border-radius: 8px; background: white; }
        .qr-card { border: 2px solid #e5e7eb; border-radius: 12px; padding: 20px; background-color: #ffffff; text-align: center; margin-bottom: 15px; }
        .sidebar-header { color: #1f2937; font-weight: bold; font-size: 1.2rem; }
        .success-text { color: #059669; font-weight: 600; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- GESTIÓN DE LA BASE DE DATOS (Sincronizada con image_c92259.png) ---
def get_db_connection():
    """Establece conexión con asistencia.db asegurando el manejo de hilos."""
    try:
        conn = sqlite3.connect('asistencia.db', check_same_thread=False)
        return conn
    except sqlite3.Error as e:
        st.error(f"⚠️ Error crítico: No se pudo conectar a la base de datos. {e}")
        return None

def validar_migracion(conn):
    """Verifica si la columna 'estudiante_id' existe tras la migración."""
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(estudiantes)")
        columnas = [info[1] for info in cursor.fetchall()]
        # Según tu imagen image_c92259.png, debe existir 'estudiante_id'
        return "estudiante_id" in columnas
    except Exception as e:
        st.error(f"Error al validar estructura: {e}")
        return False

@st.cache_data
def cargar_datos_estudiantes():
    """Carga y limpia los datos de los estudiantes para el reporte."""
    conn = get_db_connection()
    if conn:
        if not validar_migracion(conn):
            st.error("❌ La base de datos no tiene la columna 'estudiante_id'.")
            return pd.DataFrame()
        
        try:
            # Query ajustado a los datos de tu imagen image_c92259.png
            query = "SELECT id, estudiante_id, nombre_completo, grado FROM estudiantes"
            df = pd.read_sql_query(query, conn)
            # Limpieza básica
            df['nombre_completo'] = df['nombre_completo'].fillna("Sin Nombre")
            df['grado'] = df['grado'].fillna("Sin Grado")
            return df
        except Exception:
            # Fallback si solo existen las columnas básicas de la imagen
            query = "SELECT id, estudiante_id FROM estudiantes"
            return pd.read_sql_query(query, conn)
        finally:
            conn.close()
    return pd.DataFrame()

# --- NÚCLEO DE GENERACIÓN DE IDENTIFICADORES (Líneas 100-150) ---
def crear_qr_estudiante(codigo_id):
    """
    Genera el código QR con 'border=4' para corregir el error de lectura anterior[cite: 1].
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4, # <--- INDISPENSABLE para que el lector no falle[cite: 1]
        )
        # Usamos el código de la columna 'estudiante_id' de image_c92259.png[cite: 1]
        qr.add_data(f"SISTEMA_ASISTENCIA_ID_{codigo_id}")
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        
        # Procesamiento de imagen para Streamlit
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        return img_buffer.getvalue()
    except Exception as e:
        st.error(f"Error generando QR para {codigo_id}: {e}")
        return None

# --- FUNCIONES DE ASISTENCIA Y LOGS (Líneas 151-200) ---
def registrar_log_asistencia(est_id):
    """Guarda el evento de escaneo en la base de datos."""
    conn = get_db_connection()
    if conn:
        try:
            now = datetime.datetime.now()
            fecha = now.strftime("%Y-%m-%d")
            hora = now.strftime("%H:%M:%S")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO registro_asistencia (estudiante_id, fecha, hora) VALUES (?, ?, ?)",
                (est_id, fecha, hora)
            )
            conn.commit()
            return True
        except Exception as e:
            st.error(f"No se pudo registrar la asistencia: {e}")
            return False
        finally:
            conn.close()
    return False

# --- COMPONENTES DE LA INTERFAZ (UI) (Líneas 201-280) ---
def render_dashboard(df):
    st.markdown("## 📊 Dashboard de Control")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Estudiantes", len(df))
    with c2:
        st.metric("Grados Registrados", df['grado'].nunique() if 'grado' in df.columns else 0)
    with c3:
        st.metric("Sede", "Timbío")

def render_galeria_qr(df):
    st.markdown("### 🖨️ Generador de Carnets")
    busqueda = st.text_input("🔍 Buscar estudiante por ID o Nombre:", "")
    
    # Lógica de filtrado dinámico
    if busqueda:
        df = df[df.astype(str).apply(lambda x: busqueda.lower() in x.str.lower().values, axis=1)]

    # Grid de visualización
    num_cols = 3
    rows = st.columns(num_cols)
    for index, row in df.iterrows():
        # Usamos estudiante_id de la imagen[cite: 1]
        id_actual = row['estudiante_id']
        nombre_actual = row['nombre_completo'] if 'nombre_completo' in df.columns else f"ID: {id_actual}"
        
        with rows[index % num_cols]:
            with st.container(border=True):
                st.markdown(f"**{nombre_actual}**")
                st.caption(f"Código Sistema: {id_actual}")
                
                # Generamos el QR único para cada iteración[cite: 1]
                qr_bytes = crear_qr_estudiante(id_actual)
                if qr_bytes:
                    st.image(qr_bytes, use_container_width=True)
                    st.download_button(
                        label=f"⬇️ PNG {id_actual}",
                        data=qr_bytes,
                        file_name=f"QR_EST_{id_actual}.png",
                        mime="image/png",
                        key=f"btn_{id_actual}_{index}"
                    )

# --- FUNCIÓN PRINCIPAL (MAIN) (Líneas 281-306) ---
def main():
    # Inicialización de la sesión
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = True # Bypass para desarrollo
    
    # Sidebar de Navegación
    with st.sidebar:
        st.markdown("<p class='sidebar-header'>eduasistencia-pro</p>", unsafe_allow_html=True)
        st.image("https://via.placeholder.com/100", caption="Institución San Antonio de Padua")
        st.divider()
        menu = st.radio("Módulos del Sistema:", 
                        ["🏠 Inicio", "🆔 Generar QRs", "📝 Registro de Asistencia", "📋 Reportes CSV"])
        st.divider()
        st.caption(f"Última actualización: {datetime.date.today()}")

    # Carga de datos
    df_principal = cargar_datos_estudiantes()

    if menu == "🏠 Inicio":
        render_dashboard(df_principal)
        st.image("https://via.placeholder.com/600x200", caption="Vista de la Institución")
        
    elif menu == "🆔 Generar QRs":
        render_galeria_qr(df_principal)
        
    elif menu == "📝 Registro de Asistencia":
        st.markdown("### Escaneo de Códigos")
        st.write("Conecte el lector de código de barras o escanee aquí:")
        lector = st.text_input("Esperando señal...", key="reader")
        if lector:
            if registrar_log_asistencia(lector):
                st.balloons()
                st.success(f"✅ Asistencia registrada para: {lector}")
        
    elif menu == "📋 Reportes CSV":
        st.markdown("### Descarga de Datos Migrados")
        st.dataframe(df_principal, use_container_width=True)
        csv = df_principal.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Descargar Excel/CSV", data=csv, file_name="estudiantes_padua.csv", mime='text/csv')

if __name__ == "__main__":
    main()
