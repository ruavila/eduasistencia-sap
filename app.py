import streamlit as st
import pandas as pd
import qrcode
import io
import os
import urllib.parse
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.units import cm
from streamlit_qrcode_scanner import qrcode_scanner

# --- IMPORTACIÓN DE MÓDULOS LOCALES ---
try:
    from modules.database import supabase, hash_password
except Exception as e:
    st.error(f"Error crítico de conexión: {e}")

# --- CONFIGURACIÓN DE IDENTIDAD ---
APP_NAME = "EduAsistencia Pro"
COLEGIO = "Institución Educativa San Antonio de Padua"
ESCUDO_PATH = "assets/escudo.png" 

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")

# --- ESTADOS DE SESIÓN ---
if 'logueado' not in st.session_state: 
    st.session_state.logueado = False
if 'captura_finalizada' not in st.session_state: 
    st.session_state.captura_finalizada = False

# --- BLOQUE DE AUTENTICACIÓN ---
if not st.session_state.logueado:
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        if os.path.exists(ESCUDO_PATH):
            st.image(ESCUDO_PATH, width=100)
        st.title(APP_NAME)
        st.subheader(COLEGIO)
        
        u = st.text_input("Usuario ID")
        p = st.text_input("Contraseña", type="password")
        if st.button("🚀 INGRESAR", use_container_width=True, type="primary"):
            res = supabase.table("usuarios").select("*").eq("usuario", u).eq("password", hash_password(p)).execute()
            if res.data:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res.data[0]['nombre']
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- CABECERA PRINCIPAL ---
col_esc, col_txt = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

menu = st.sidebar.radio("Menú Principal", ["📚 Cursos", "👥 Estudiantes", "📸 Scanner QR", "📊 Reportes"])

# --- 1. SECCIÓN CURSOS ---
if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos")
    with st.expander("➕ Añadir Nuevo Curso"):
        g_c = st.text_input("Grado (Ej: 805)")
        m_c = st.text_input("Asignatura")
        if st.button("Guardar Curso"):
            if g_c and m_c:
                supabase.table("cursos").insert({"grado": g_c, "materia": m_c, "profe_id": st.session_state.user}).execute()
                st.rerun()

    data_c = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if data_c:
        for c in data_c:
            col1, col2 = st.columns([5, 1])
            col1.info(f"**{c['grado']}** - {c['materia']}")
            if col2.button("🗑️", key=f"del_{c['id']}"):
                supabase.table("cursos").delete().eq("id", c['id']).execute()
                st.rerun()

# --- 2. SECCIÓN ESTUDIANTES ---
elif menu == "👥 Estudiantes":
    st.subheader("Carga y Carnetización")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_c = st.selectbox("Seleccione el curso para cargar alumnos:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        g_s, m_s = sel_c.split(" | ")
        f = st.file_uploader("Subir archivo Excel de alumnos", type=["xlsx"])
        
        if f and st.button("Generar Carnets y Sincronizar"):
            df = pd.read_excel(f)
            df.columns = [str(c).lower().strip() for c in df.columns]
            col_doc = next((p for p in ['documento', 'codigo', 'cedula', 'id'] if p in df.columns), None)
            col_nom = next((p for p in ['nombre', 'estudiante', 'alumno'] if p in df.columns), None)

            if col_doc and col_nom:
                pdf = io.BytesIO()
                canv = canvas.Canvas(pdf, pagesize=landscape(legal))
                x, y = 1.5*cm, 15*cm
                for _, r in df.iterrows():
                    doc, nom = str(r[col_doc]), str(r[col_nom]).upper()
                    supabase.table("estudiantes").upsert({"documento": doc, "nombre": nom, "grado": g_s, "materia": m_s, "profe_id": st.session_state.user}).execute()
                    qr = qrcode.make(doc)
                    b = io.BytesIO(); qr.save(b, format='PNG')
                    canv.drawInlineImage(Image.open(b), x, y, 4*cm, 4*cm)
                    canv.setFont("Helvetica-Bold", 8); canv.drawString(x, y-0.5*cm, nom[:20])
                    x += 6.5*cm
                    if x > 30*cm: x, y = 1.5*cm, y-6.5*cm
                canv.save()
                st.success("Estudiantes cargados correctamente."); st.download_button("📥 Descargar Carnets QR", pdf.getvalue(), f"QR_{g_s}.pdf")
            else:
                st.error("El Excel debe tener columnas llamadas 'codigo' (o documento) y 'nombre'.")

# --- 3. SECCIÓN SCANNER ---
elif menu == "📸 Scanner QR":
    st.subheader("Control de Asistencia en Tiempo Real")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso actual:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la sesión:")
        if tema:
            cod = qrcode_scanner(key="scanner")
            if cod:
                hoy = datetime.now().strftime("%Y-%m-%d")
                est = supabase.table("estudiantes").select("nombre").eq("documento", cod).eq("grado", ga).execute().data
                if est:
                    check = supabase.table("asistencia").select("*").eq("estudiante_id", cod).eq("fecha", hoy).eq("tema", tema).execute().data
                    if not check:
                        supabase.table("asistencia").insert({"estudiante_id": cod, "fecha": hoy, "hora": datetime.now().strftime("%H:%M:%S"), "grado": ga, "materia": ma, "tema": tema, "profe_id": st.session_state.user}).execute()
                        st.markdown(f"""<div style="background-color:#d4edda; color:#155724; padding:20px; border-radius:10px; text-align:center; border:2px solid #c3e6cb;">
                            <h1 style="margin:0;">✅ ASISTENCIA REGISTRADA</h1>
                            <p style="font-size:28px; margin:10px 0 0 0;"><b>{est[0]['nombre']}</b></p>
                        </div>""", unsafe_allow_html=True)

# --- 4. SECCIÓN REPORTES (SÓLO BOTÓN DE DESCARGA + CUADRÍCULA) ---
elif menu == "📊 Reportes":
    st.subheader("Generación de Planillas PDF")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_r = st.selectbox("Seleccione el curso para exportar:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        gr, mr = sel_r.split(" | ")
        
        # Procesar datos en segundo plano
        estudiantes = supabase.table("estudiantes").select("documento, nombre").eq("grado", gr).eq("profe_id", st.session_state.user).order("nombre").execute().data
        asistencia = supabase.table("asistencia").select("estudiante_id, fecha, tema").eq("grado", gr).execute().data
        
        if estudiantes and asistencia:
            st.info(f"Presione el botón para generar la planilla de {gr} con el formato institucional.")
            
            # Lógica del PDF
            pdf_io = io.BytesIO()
            canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
            w, h = landscape(legal)
            
            # Escudo transparente
            if os.path.exists(ESCUDO_PATH):
                canv.drawInlineImage(Image.open(ESCUDO_PATH), 1.5*cm, h-2.6*cm, width=1.8*cm, height=1.8*cm, preserveAspectRatio=True, mask='auto')
            
            canv.setFont("Helvetica-Bold", 14); canv.drawString(4*cm, h-1.5*cm, COLEGIO)
            canv.setFont("Helvetica", 10); canv.drawString(4*cm, h-2.2*cm, f"Materia: {mr} | Grado: {gr} | Docente: {st.session_state.profe_nom}")
            
            # Preparar Matriz
            df = pd.DataFrame(estudiantes)
            temas_lista = sorted(list(set([f"{a['tema']}\n{a['fecha']}" for a in asistencia])))
            for t in temas_lista: df[t] = "X"
            for a in asistencia:
                df.loc[df['documento'] == a['estudiante_id'], f"{a['tema']}\n{a['fecha']}"] = "✔"
            
            # Dibujar Encabezado de Tabla y Cuadrícula
            y_start = h - 3.8*cm
            canv.line(1.5*cm, y_start + 0.6*cm, w-1.5*cm, y_start + 0.6*cm) # Línea superior
            canv.setFont("Helvetica-Bold", 8); canv.drawString(1.7*cm, y_start, "NOMBRES Y APELLIDOS")
            
            tx = 10*cm
            for t in temas_lista:
                canv.line(tx - 0.2*cm, y_start + 0.6*cm, tx - 0.2*cm, y_start - 0.4*cm) # Línea vertical tema
                canv.setFont("Helvetica-Bold", 6); canv.drawString(tx, y_start + 0.2*cm, t.split("\n")[0][:15])
                canv.setFont("Helvetica", 5); canv.drawString(tx, y_start - 0.1*cm, t.split("\n")[1])
                tx += 2.2*cm
            
            canv.drawString(tx, y_start, "ASIST."); canv.drawString(tx + 1.5*cm, y_start, "AUSEN.")
            canv.line(1.5*cm, y_start - 0.4*cm, w-1.5*cm, y_start - 0.4*cm) # Línea división cabecera
            
            # Filas de la cuadrícula
            y = y_start - 0.9*cm
            for i, r in df.iterrows():
                canv.setFont("Helvetica", 8); canv.drawString(1.7*cm, y, f"{i+1}. {r['nombre']}")
                
                cx = 10*cm
                asist_count = 0
                for t in temas_lista:
                    mark = r[t]
                    canv.drawCentredString(cx + 0.8*cm, y, mark)
                    canv.line(cx - 0.2*cm, y + 0.5*cm, cx - 0.2*cm, y - 0.2*cm) # Verticales celdas
                    if mark == "✔": asist_count += 1
                    cx += 2.2*cm
                
                canv.drawCentredString(cx + 0.4*cm, y, str(asist_count))
                canv.drawCentredString(cx + 1.8*cm, y, str(len(temas_lista) - asist_count))
                canv.line(1.5*cm, y - 0.2*cm, w-1.5*cm, y - 0.2*cm) # Horizontal inferior de la fila
                
                y -= 0.6*cm
                if y < 2*cm:
                    canv.showPage(); y = h - 2*cm
            
            canv.save()
            st.download_button(label="✅ DESCARGAR PLANILLA PDF", data=pdf_io.getvalue(), file_name=f"Planilla_{gr}_{mr}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.warning("No hay datos suficientes (estudiantes o asistencia) para generar el reporte.")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
