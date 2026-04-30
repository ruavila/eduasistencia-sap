# ==============================================================================
# PROYECTO: eduasistencia-pro (Versión Evolucionada)
# INSTITUCIÓN: Institución Educativa San Antonio de Padua - Sede Timbío
# AUTOR: Sistema de Gestión de Asistencia Estudiantil
# ARCHIVO: app.py
# ==============================================================================

import streamlit as st
import sqlite3
import qrcode
import pandas as pd
import datetime
import os
import base64
from io import BytesIO
from PIL import Image

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA INTERFAZ DE USUARIO (Líneas 1-50)
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="eduasistencia-pro | San Antonio de Padua",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS embebidos para mantener la estética profesional original
def cargar_estilos():
    st.markdown("""
        <style>
        .stApp { background-color: #f4f7f6; }
        .estudiante-card { 
            border: 1px solid #d1d5db; 
            border-radius: 15px; 
            padding: 20px; 
            background-color: white; 
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
            text-align: center;
        }
        .header-text { color: #1e3a8a; font-family: 'Arial'; font-weight: bold; }
        .sidebar-brand { font-size: 24px; font-weight: bold; color: #1e40af; text-align: center; }
        </style>
    """, unsafe_allow_html=True)

cargar_estilos()

# ------------------------------------------------------------------------------
# 2. GESTIÓN DE DATOS Y CONECTIVIDAD (Líneas 51-120)
# ------------------------------------------------------------------------------
def obtener_conexion():
    """Establece conexión segura con la base de datos migrada."""
    try:
        # Asegúrate de que el archivo asistencia.db esté en la raíz
        conn = sqlite3.connect('asistencia.db', check_same_thread=False)
        return conn
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {e}")
        return None

def validar_estructura_db(conn):
    """Verifica la existencia de 'estudiante_id' según image_c92259.png."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(estudiantes)")
    columnas = [info[1] for info in cursor.fetchall()]
    return "estudiante_id" in columnas[cite: 1]

@st.cache_data(ttl=600)
def cargar_estudiantes_migrados():
    """Carga los datos asegurando compatibilidad con la nueva estructura."""
    conn = obtener_conexion()
    if conn:
        try:
            # Consulta ajustada a la columna de tu imagen image_c92259.png
            if validar_estructura_db(conn):
                query = "SELECT id, estudiante_id, nombre_completo, grado FROM estudiantes"
            else:
                query = "SELECT id, estudiante_id FROM estudiantes"[cite: 1]
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"Error al leer tabla estudiantes: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# ------------------------------------------------------------------------------
# 3. LÓGICA DE GENERACIÓN DE IDENTIFICADORES QR (Líneas 121-180)
# ------------------------------------------------------------------------------
def generar_identificador_qr(codigo_valor):
    """
    Crea el código QR con margen de seguridad (border=4) para lectura óptica.
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4  # INDISPENSABLE: Soluciona el error de lectura anterior
        )
        # El contenido usa el 'estudiante_id' único de la base de datos[cite: 1]
        qr.add_data(f"ID:{codigo_valor}")
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        
        # Conversión de imagen para visualización en Streamlit
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return buffered.getvalue()
    except Exception as e:
        st.error(f"Error al generar QR: {e}")
        return None

# ------------------------------------------------------------------------------
# 4. MÓDULOS DE REGISTRO Y ASISTENCIA (Líneas 181-240)
# ------------------------------------------------------------------------------
def registrar_asistencia_db(estudiante_id):
    """Inserta el registro de entrada en la tabla de logs."""
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d")
            hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
            cursor.execute(
                "INSERT INTO registro_asistencia (estudiante_id, fecha, hora) VALUES (?, ?, ?)",
                (estudiante_id, fecha_actual, hora_actual)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error al registrar asistencia: {e}")
            return False
    return False

# ------------------------------------------------------------------------------
# 5. CONSTRUCCIÓN DE LA INTERFAZ DE USUARIO (Líneas 241-306)
# ------------------------------------------------------------------------------
def main():
    # Barra lateral de navegación
    with st.sidebar:
        st.markdown("<div class='sidebar-brand'>eduasistencia-pro</div>", unsafe_allow_html=True)
        st.divider()
        menu = st.selectbox("Módulo del Sistema", 
                            ["Dashboard", "Generar Carnets QR", "Toma de Asistencia", "Reportes"])
        st.divider()
        st.info("Conectado a: Institución San Antonio de Padua")
        st.caption(f"Fecha: {datetime.date.today()}")

    df_data = cargar_estudiantes_migrados()

    if menu == "Dashboard":
        st.markdown("<h1 class='header-text'>Panel de Control Estudiantil</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Estudiantes", len(df_data))
        col2.metric("Sede", "Timbío")
        col3.metric("Estado DB", "Sincronizado" if not df_data.empty else "Error")
        
        if not df_data.empty and 'grado' in df_data.columns:
            st.bar_chart(df_data['grado'].value_counts())

    elif menu == "Generar Carnets QR":
        st.markdown("<h2 class='header-text'>Generador de Códigos Únicos</h2>", unsafe_allow_html=True)
        busqueda = st.text_input("Filtrar por Nombre o Código Estudiante...")
        
        if busqueda:
            df_data = df_data[df_data.astype(str).apply(lambda x: busqueda.lower() in x.str.lower().values, axis=1)]

        # Visualización en Grid dinámico
        columnas = st.columns(4)
        for i, (index, row) in enumerate(df_data.iterrows()):
            # Usamos 'estudiante_id' de image_c92259.png[cite: 1]
            cod_est = row['estudiante_id']
            nombre_est = row['nombre_completo'] if 'nombre_completo' in df_data.columns else f"Código: {cod_est}"
            
            with columnas[i % 4]:
                with st.container():
                    st.markdown(f"**{nombre_est}**")
                    # Generamos el QR pasando el valor único de la fila[cite: 1]
                    qr_img = generar_identificador_qr(cod_est)
                    if qr_img:
                        st.image(qr_img, width=150)
                        st.download_button(
                            label="Descargar PNG",
                            data=qr_img,
                            file_name=f"QR_{cod_est}.png",
                            mime="image/png",
                            key=f"btn_{cod_est}_{i}"
                        )

    elif menu == "Toma de Asistencia":
        st.markdown("<h2 class='header-text'>Registro por Escáner</h2>", unsafe_allow_html=True)
        codigo_leido = st.text_input("Esperando lectura de QR...", placeholder="Escanee aquí...")
        if codigo_leido:
            if registrar_asistencia_db(codigo_leido):
                st.success(f"Asistencia confirmada para ID: {codigo_leido}")
                st.balloons()

    elif menu == "Reportes":
        st.markdown("<h2 class='header-text'>Exportación de Datos</h2>", unsafe_allow_html=True)
        st.dataframe(df_data, use_container_width=True)
        csv = df_data.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar Reporte Completo", data=csv, file_name="reporte_estudiantes.csv")

if __name__ == "__main__":
    main()
