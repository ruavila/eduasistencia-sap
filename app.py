import streamlit as st
import pandas as pd
import qrcode
import io
import os
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.units import cm
from streamlit_qrcode_scanner import qrcode_scanner

# --- CONEXIÓN ---
try:
    from modules.database import supabase, hash_password
except Exception as e:
    st.error(f"Error de conexión: {e}")

# --- CONFIGURACIÓN ---
APP_NAME = "EduAsistencia Pro"
COLEGIO = "Institución Educativa San Antonio de Padua"
ESCUDO_PATH = "assets/escudo.png" 

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")

if 'logueado' not in st.session_state: 
    st.session_state.logueado = False

# --- LOGIN ---
if not st.session_state.logueado:
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=100)
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

# --- CABECERA ---
col_esc, col_txt = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

menu = st.sidebar.radio("Menú", ["📚 Cursos", "👥 Estudiantes", "📸 Scanner QR", "📊 Reportes", "🔄 Reiniciar Datos"])

# --- 1. CURSOS ---
if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos")
    g_c = st.text_input("Grado (Ej: 805)")
    m_c = st.text_input("Asignatura")
    if st.button("Guardar Curso"):
        if g_c and m_c:
            supabase.table("cursos").insert({"grado": g_c, "materia": m_c, "profe_id": st.session_state.user}).execute()
            st.rerun()

# --- 2. ESTUDIANTES ---
elif menu == "👥 Estudiantes":
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_c = st.selectbox("Curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        g_s, m_s = sel_c.split(" | ")
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        if f and st.button("Generar Carnets"):
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
                st.download_button("📥 Descargar Carnets", pdf.getvalue(), f"QR_{g_s}.pdf")

# --- 3. SCANNER ---
elif menu == "📸 Scanner QR":
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la clase:")
        if tema:
            cod = qrcode_scanner(key="scanner")
            if cod:
                hoy = datetime.now().strftime("%Y-%m-%d")
                est = supabase.table("estudiantes").select("nombre").eq("documento", cod).eq("grado", ga).execute().data
                if est:
                    supabase.table("asistencia").upsert({"estudiante_id": cod, "fecha": hoy, "tema": tema, "grado": ga, "materia": ma, "profe_id": st.session_state.user}).execute()
                    st.success(f"REGISTRADO: {est[0]['nombre']}")

# --- 4. REPORTES (CON TOTALES Y FORMATO PDF) ---
elif menu == "📊 Reportes":
    st.subheader("Planilla de Asistencia")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_r = st.selectbox("Seleccione Curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        gr, mr = sel_r.split(" | ")
        estudiantes = supabase.table("estudiantes").select("documento, nombre").eq("grado", gr).eq("profe_id", st.session_state.user).order("nombre").execute().data
        asistencia = supabase.table("asistencia").select("estudiante_id, fecha, tema").eq("grado", gr).execute().data
        
        if estudiantes and asistencia:
            # Procesamiento de datos para totales
            df = pd.DataFrame(estudiantes)
            temas_lista = sorted(list(set([f"{a['tema']}\n\n\n{a['fecha']}" for a in asistencia])))
            
            pdf_io = io.BytesIO()
            canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
            w, h = landscape(legal)
            
            # Encabezado Institucional
            if os.path.exists(ESCUDO_PATH):
                canv.drawInlineImage(Image.open(ESCUDO_PATH).convert("RGBA"), 1.5*cm, h-2.5*cm, width=1.8*cm, height=1.8*cm)
            
            canv.setFont("Helvetica-Bold", 14); canv.drawString(4*cm, h-1.5*cm, COLEGIO)
            canv.setFont("Helvetica", 10); canv.drawString(4*cm, h-2.1*cm, f"Materia: {mr} | Grado: {gr} | Docente: {st.session_state.profe_nom}")
            
            # Cabecera de Tabla
            y = h - 3.5*cm
            canv.line(1.5*cm, y+1.1*cm, w-1.5*cm, y+1.1*cm) # Línea superior
            canv.setFont("Helvetica-Bold", 8); canv.drawString(1.7*cm, y, "ESTUDIANTE")
            
            tx = 9.5*cm
            for t in temas_lista:
                canv.line(tx-0.2*cm, y+1.1*cm, tx-0.2*cm, y-0.4*cm)
                canv.setFont("Helvetica-Bold", 6)
                parts = t.split("\n\n\n")
                canv.drawString(tx, y+0.7*cm, parts[0][:12]) # Tema
                canv.setFont("Helvetica", 5)
                canv.drawString(tx, y, parts[1]) # Fecha
                tx += 2.2*cm
            
            canv.setFont("Helvetica-Bold", 7)
            canv.drawString(tx, y, "Asist"); canv.drawString(tx+1.2*cm, y, "Ausen.")
            canv.line(1.5*cm, y-0.4*cm, w-1.5*cm, y-0.4*cm) # Línea división cabecera
            
            # Filas y Totales 
            y -= 0.8*cm
            for i, r in df.iterrows():
                canv.setFont("Helvetica", 8); canv.drawString(1.7*cm, y, f"{i+1}. {r['nombre']}")
                cx = 9.5*cm
                a_count = 0
                for t in temas_lista:
                    asistio = any(a['estudiante_id'] == r['documento'] and f"{a['tema']}\n\n\n{a['fecha']}" == t for a in asistencia)
                    marca = " " if asistio else "X" # X para ausencia según reporte
                    if asistio: a_count += 1
                    canv.drawCentredString(cx+0.8*cm, y, marca)
                    canv.line(cx-0.2*cm, y+0.4*cm, cx-0.2*cm, y-0.2*cm)
                    cx += 2.2*cm
                
                # Columnas de Total 
                canv.drawCentredString(cx+0.4*cm, y, str(a_count))
                canv.drawCentredString(cx+1.6*cm, y, str(len(temas_lista)-a_count))
                canv.line(1.5*cm, y-0.2*cm, w-1.5*cm, y-0.2*cm)
                y -= 0.5*cm
                if y < 2*cm: canv.showPage(); y = h - 2*cm
                
            canv.save()
            st.download_button("📥 DESCARGAR PLANILLA PDF", pdf_io.getvalue(), f"Reporte_{gr}.pdf", use_container_width=True)

# --- 5. REINICIAR DATOS (RESTAURADO) ---
elif menu == "🔄 Reiniciar Datos":
    st.subheader("Zona de Peligro")
    st.warning("Esta acción eliminará todos los registros de asistencia del sistema.")
    confirm = st.text_input("Escriba 'ELIMINAR' para confirmar:")
    if st.button("BORRAR TODA LA ASISTENCIA"):
        if confirm == "ELIMINAR":
            supabase.table("asistencia").delete().neq("id", 0).execute()
            st.success("Historial de asistencia borrado.")
            st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
