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

# Importación de conexión y seguridad
from modules.database import supabase, hash_password

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
        
        tab_login, tab_reg, tab_rec = st.tabs(["🔐 Acceso", "📝 Registro", "🔑 Recuperar"])
        
        with tab_login:
            u = st.text_input("Usuario ID", key="l_u")
            p = st.text_input("Contraseña", type="password", key="l_p")
            if st.button("🚀 INGRESAR", use_container_width=True, type="primary"):
                res = supabase.table("usuarios").select("*").eq("usuario", u).eq("password", hash_password(p)).execute()
                if res.data:
                    st.session_state.logueado = True
                    st.session_state.user = u
                    st.session_state.profe_nom = res.data[0]['nombre']
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        
        with tab_reg:
            new_u = st.text_input("Crear Usuario ID")
            new_n = st.text_input("Nombre Completo")
            new_p = st.text_input("Crear Contraseña", type="password")
            preg = st.selectbox("Pregunta de Seguridad", ["¿Nombre de su mascota?", "¿Ciudad natal?", "¿Comida favorita?"])
            resp = st.text_input("Respuesta Secreta")
            if st.button("✨ REGISTRAR DOCENTE", use_container_width=True):
                if new_u and new_n and new_p and resp:
                    data = {
                        "usuario": new_u, "password": hash_password(new_p), 
                        "nombre": new_n, "pregunta_seguridad": preg, 
                        "respuesta_seguridad": resp.strip().lower()
                    }
                    supabase.table("usuarios").insert(data).execute()
                    st.success("¡Registrado! Ya puedes entrar.")
    st.stop()

# --- CABECERA PRINCIPAL ---
col_esc, col_txt = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

menu = st.sidebar.radio("Menú Principal", ["📚 Cursos", "👥 Estudiantes", "📸 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

# --- 1. SECCIÓN CURSOS ---
if menu == "📚 Cursos":
    st.subheader("Gestión de Cursos")
    with st.expander("➕ Añadir Nuevo Curso"):
        g_c = st.text_input("Grado")
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
    st.subheader("Carga de Alumnos")
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
                    supabase.table("estudiantes").upsert({"documento": doc, "nombre": nom, "whatsapp": str(r.get('whatsapp', '')), "grado": g_s, "materia": m_s, "profe_id": st.session_state.user}).execute()
                    qr = qrcode.make(doc)
                    b = io.BytesIO(); qr.save(b, format='PNG')
                    canv.drawInlineImage(Image.open(b), x, y, 4*cm, 4*cm)
                    canv.setFont("Helvetica-Bold", 8); canv.drawString(x, y-0.5*cm, nom[:20])
                    x += 6.5*cm
                    if x > 30*cm: x, y = 1.5*cm, y-6.5*cm
                canv.save()
                st.success("Sincronizado."); st.download_button("📥 Descargar PDF", pdf.getvalue(), f"QR_{g_s}.pdf")

# --- 3. SECCIÓN SCANNER ---
elif menu == "📸 Scanner QR":
    st.subheader("Control de Asistencia")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de hoy:")
        if tema:
            if not st.session_state.captura_finalizada:
                if st.button("⏹️ Finalizar Sesión", type="primary"):
                    st.session_state.captura_finalizada = True; st.rerun()
                
                cod = qrcode_scanner(key="scanner")
                if cod:
                    est = supabase.table("estudiantes").select("*").eq("documento", cod).eq("grado", ga).execute().data
                    if est:
                        e = est[0]; hoy = datetime.now().strftime("%Y-%m-%d")
                        check = supabase.table("asistencia").select("*").eq("estudiante_id", cod).eq("fecha", hoy).eq("tema", tema).execute().data
                        if not check:
                            supabase.table("asistencia").insert({"estudiante_id": cod, "fecha": hoy, "hora": datetime.now().strftime("%H:%M:%S"), "grado": ga, "materia": ma, "tema": tema, "profe_id": st.session_state.user}).execute()
                            st.markdown(f"""<div style="background-color:#d4edda; color:#155724; padding:20px; border-radius:10px; text-align:center;">
                                <h1>✅ ASISTENCIA REGISTRADA</h1><p style="font-size:24px;"><b>{e['nombre']}</b></p></div>""", unsafe_allow_html=True)

# --- 4. SECCIÓN REPORTES (FORMATO MATRICIAL CON CUADRÍCULA) ---
elif menu == "📊 Reportes":
    st.subheader("Planillas Institucionales")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_r = st.selectbox("Reporte de:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        gr, mr = sel_r.split(" | ")
        estudiantes = supabase.table("estudiantes").select("documento, nombre").eq("grado", gr).eq("profe_id", st.session_state.user).order("nombre").execute().data
        asistencia = supabase.table("asistencia").select("estudiante_id, fecha, tema").eq("grado", gr).execute().data
        
        if estudiantes and asistencia:
            df = pd.DataFrame(estudiantes)
            temas = sorted(list(set([f"{a['tema']}\n{a['fecha']}" for a in asistencia])))
            for t in temas: df[t] = "X" # Por defecto Ausente
            for a in asistencia:
                col = f"{a['tema']}\n{a['fecha']}"
                df.loc[df['documento'] == a['estudiante_id'], col] = "✔" # Asistió
            
            df["Asist."] = df[temas].apply(lambda x: x.str.contains("✔").sum(), axis=1)
            df["Ausen."] = len(temas) - df["Asist."]
            st.dataframe(df.drop(columns=['documento']), use_container_width=True)

            if st.button("📥 Descargar Reporte PDF"):
                pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=landscape(legal)); w, h = landscape(legal)
                # Escudo sin fondo negro (transparente)
                if os.path.exists(ESCUDO_PATH): canv.drawInlineImage(Image.open(ESCUDO_PATH), 1.5*cm, h-2.5*cm, 1.8*cm, 1.8*cm, preserveAspectRatio=True, mask='auto')
                
                canv.setFont("Helvetica-Bold", 14); canv.drawString(4*cm, h-1.5*cm, COLEGIO)
                canv.setFont("Helvetica", 10); canv.drawString(4*cm, h-2.1*cm, f"Materia: {mr} | Grado: {gr} | Docente: {st.session_state.profe_nom}")
                
                # Dibujar Cuadrícula y Cabeceras
                y = h - 3.5*cm; canv.setFont("Helvetica-Bold", 8)
                canv.line(1.5*cm, y+0.5*cm, w-1.5*cm, y+0.5*cm) # Línea superior cabecera
                canv.drawString(1.7*cm, y, "ESTUDIANTE"); tx = 8.5*cm
                
                for t in temas:
                    canv.setFont("Helvetica-Bold", 7); canv.drawString(tx, y+0.2*cm, t.split("\n")[0][:12])
                    canv.setFont("Helvetica", 6); canv.drawString(tx, y, t.split("\n")[1])
                    canv.line(tx-0.2*cm, y+0.5*cm, tx-0.2*cm, y-0.5*cm) # Línea vertical tema
                    tx += 2.2*cm
                
                canv.drawString(tx, y, "Asist."); canv.drawString(tx+1.2*cm, y, "Ausen.")
                canv.line(1.5*cm, y-0.2*cm, w-1.5*cm, y-0.2*cm) # Línea inferior cabecera
                
                y -= 0.6*cm; canv.setFont("Helvetica", 8)
                for i, r in df.iterrows():
                    canv.drawString(1.7*cm, y, f"{i+1}. {r['nombre'][:35]}"); tx = 8.5*cm
                    for t in temas:
                        canv.drawCentredString(tx+0.5*cm, y, r[t])
                        canv.line(tx-0.2*cm, y+0.4*cm, tx-0.2*cm, y-0.2*cm) # Línea vertical celda
                        tx += 2.2*cm
                    
                    canv.drawCentredString(tx+0.3*cm, y, str(r["Asist."]))
                    canv.drawCentredString(tx+1.5*cm, y, str(r["Ausen."]))
                    canv.line(1.5*cm, y-0.1*cm, w-1.5*cm, y-0.1*cm) # Línea horizontal fila
                    y -= 0.5*cm
                    if y < 2*cm: canv.showPage(); y = h - 2*cm
                
                canv.save(); st.download_button("✅ Guardar PDF", pdf_io.getvalue(), f"Reporte_{gr}.pdf")

# --- 5. SECCIÓN REINICIO ---
elif menu == "⚙️ Reinicio":
    if st.button("🗑️ ELIMINAR DATOS"):
        supabase.table("asistencia").delete().eq("profe_id", st.session_state.user).execute()
        st.success("Registros eliminados."); st.rerun()

if st.sidebar.button("Salir"): st.session_state.logueado = False; st.rerun()
