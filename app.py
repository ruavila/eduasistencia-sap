import sys
import os
import streamlit as st
import pandas as pd
from PIL import Image
import qrcode
import io

# Librerías para el PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm

# Asegurar que encuentre la carpeta 'modules'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from modules.database import init_db, get_connection
from modules.config import APP_NAME, APP_SUBTITLE, CREADOR, COLEGIO, ESCUDO_PATH
from modules.auth import check_login, registrar_usuario

st.set_page_config(page_title=APP_NAME, layout="wide")
init_db()

# --- (Omitimos bloque de login/acceso para ir directo a la lógica de alumnos) ---
# ... (Mantener código de sesión igual que antes) ...

menu = st.sidebar.selectbox("Menú", ["Mis Cursos", "Gestionar Estudiantes", "Escanear Asistencia", "Reportes"])
conn = get_connection()

if menu == "Gestionar Estudiantes":
    st.header("👤 Carga Masiva y Generación de PDF con QR")
    
    # 1. Selección de Curso
    df_c = pd.read_sql("SELECT id, grado, materia FROM cursos WHERE profesor_id=?", 
                       conn, params=(st.session_state.usuario_logueado,))
    
    if df_c.empty:
        st.warning("Debe registrar un curso primero.")
    else:
        opciones = {f"{row['grado']} - {row['materia']}": row['grado'] for idx, row in df_c.iterrows()}
        seleccion = st.selectbox("Curso destino:", opciones.keys())
        grado_sel = opciones[seleccion]
        materia_sel = seleccion.split(" - ")[1]

        uploaded_file = st.file_uploader("Subir Excel/CSV (columnas: nombre, documento)", type=["xlsx", "csv"])
        
        if uploaded_file:
            df_alumnos = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.success(f"Se cargaron {len(df_alumnos)} estudiantes.")

            if st.button("Generar PDF de Carnets QR"):
                # Crear buffer para el PDF
                pdf_buffer = io.BytesIO()
                c = canvas.Canvas(pdf_buffer, pagesize=letter)
                width, height = letter # Tamaño carta

                # Configuración de cuadrícula para el PDF
                margin_x = 1.5 * cm
                margin_y = 2 * cm
                qr_size = 4 * cm
                gap = 0.5 * cm # Espacio entre QRs
                
                x_actual = margin_x
                y_actual = height - margin_y - qr_size

                with st.spinner("Generando PDF..."):
                    for _, row in df_alumnos.iterrows():
                        nombre_full = str(row['nombre']).upper()
                        doc = str(row['documento'])
                        
                        # --- Lógica de Nombre: Iniciales + Nombre Completo ---
                        partes = nombre_full.split()
                        iniciales = "".join([p[0] for p in partes])
                        nombre_formateado = f"{iniciales} - {nombre_full}"

                        # Guardar en base de datos
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO estudiantes (nombre, documento, grado, profesor_id) VALUES (?, ?, ?, ?)",
                                (nombre_full, doc, grado_sel, st.session_state.usuario_logueado)
                            )
                            conn.commit()
                        except: pass

                        # --- Generar Imagen QR ---
                        qr = qrcode.make(doc)
                        img_buffer = io.BytesIO()
                        qr.save(img_buffer, format="PNG")
                        img_buffer.seek(0)

                        # --- Dibujar en PDF ---
                        # Insertar QR
                        c.drawInlineImage(img_buffer, x_actual, y_actual, width=qr_size, height=qr_size)
                        
                        # Dibujar Texto debajo del QR (ajustado a los 4cm)
                        c.setFont("Helvetica-Bold", 7)
                        c.drawCentredString(x_actual + (qr_size/2), y_actual - 0.3*cm, nombre_formateado)
                        c.setFont("Helvetica", 6)
                        c.drawCentredString(x_actual + (qr_size/2), y_actual - 0.6*cm, f"{grado_sel} | {materia_sel}")

                        # Lógica de posición (columnas y filas)
                        x_actual += qr_size + gap
                        if x_actual + qr_size > width - margin_x: # ¿Se acabó la fila?
                            x_actual = margin_x
                            y_actual -= qr_size + 1.5 * cm # Salto de fila (incluye espacio para texto)
                        
                        if y_actual < margin_y: # ¿Se acabó la hoja?
                            c.showPage()
                            x_actual = margin_x
                            y_actual = height - margin_y - qr_size

                    c.save()
                    pdf_buffer.seek(0)
                    
                    st.success("✅ PDF Generado con éxito.")
                    st.download_button(
                        label="📥 Descargar PDF para Imprimir",
                        data=pdf_buffer,
                        file_name=f"QRs_{grado_sel}_{materia_sel}.pdf",
                        mime="application/pdf"
                    )

elif menu == "Escanear Asistencia":
    # (Mantener código de cámara igual)
    st.header("📷 Escáner QR")
    st.camera_input("Capturar QR")
