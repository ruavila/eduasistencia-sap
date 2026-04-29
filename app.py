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

# Importamos la conexión desde tu nuevo archivo database.py
from modules.database import supabase, hash_password

# --- CONFIGURACIÓN VISUAL ---
APP_NAME = "EduAsistencia Pro"
COLEGIO = "Institución Educativa San Antonio de Padua"
ESCUDO_PATH = "assets/escudo.png" # Asegúrate de que esta carpeta y archivo existan

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")

# --- ESTADOS DE SESIÓN ---
if 'logueado' not in st.session_state: 
    st.session_state.logueado = False
if 'captura_finalizada' not in st.session_state: 
    st.session_state.captura_finalizada = False

# --- BLOQUE DE LOGIN Y REGISTRO ---
if not st.session_state.logueado:
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        if os.path.exists(ESCUDO_PATH):
            st.image(ESCUDO_PATH, width=100)
        st.title(APP_NAME)
        st.subheader(COLEGIO)
        
        tab_login, tab_reg, tab_rec = st.tabs(["🔐 Acceso", "📝 Registro", "🔑 Recuperar"])
        
        with tab_login:
            u = st.text_input("Usuario ID", key="user_login")
            p = st.text_input("Contraseña", type="password", key="pass_login")
            if st.button("🚀 INGRESAR", use_container_width=True, type="primary"):
                # Consulta a Supabase
                res = supabase.table("usuarios").select("*").eq("usuario", u).eq("password", hash_password(p)).execute()
                if res.data:
                    st.session_state.logueado = True
                    st.session_state.user = u
                    st.session_state.profe_nom = res.data[0]['nombre']
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
        
        with tab_reg:
            new_u = st.text_input("Crear Usuario ID")
            new_n = st.text_input("Nombre Completo")
            new_p = st.text_input("Crear Contraseña", type="password")
            p_seg = st.selectbox("Pregunta de Seguridad", ["¿Ciudad de nacimiento?", "¿Mascota?", "¿Comida favorita?"])
            r_seg = st.text_input("Respuesta")
            
            if st.button("✅ REGISTRARME", use_container_width=True):
                if new_u and new_n and new_p and r_seg:
                    data = {
                        "usuario": new_u, 
                        "password": hash_password(new_p), 
                        "nombre": new_n,
                        "pregunta_seguridad": p_seg,
                        "respuesta_seguridad": r_seg.strip().lower()
                    }
                    supabase.table("usuarios").insert(data).execute()
                    st.success("¡Registro exitoso! Ya puedes ingresar.")
                else:
                    st.warning("Completa todos los campos")

        with tab_rec:
            u_rec = st.text_input("Usuario a recuperar")
            if u_rec:
                res_rec = supabase.table("usuarios").select("*").eq("usuario", u_rec).execute()
                if res_rec.data:
                    st.info(f"Pregunta: {res_rec.data[0]['pregunta_seguridad']}")
                    ans = st.text_input("Tu respuesta", type="password")
                    new_pass = st.text_input("Nueva Contraseña", type="password")
                    if st.button("🔓 Cambiar Contraseña"):
                        if ans.strip().lower() == res_rec.data[0]['respuesta_seguridad']:
                            supabase.table("usuarios").update({"password": hash_password(new_pass)}).eq("usuario", u_rec).execute()
                            st.success("Contraseña actualizada.")
                        else:
                            st.error("Respuesta incorrecta.")
    st.stop()

# --- INTERFAZ PRINCIPAL (LOGUEADO) ---
st.sidebar.title(f"Bienvenido/a")
st.sidebar.write(f"👤 {st.session_state.profe_nom}")
opcion = st.sidebar.radio("Menú", ["📚 Cursos", "👥 Estudiantes", "📸 Scanner QR", "📊 Reportes", "⚙️ Ajustes"])

# --- SECCIÓN: CURSOS ---
if opcion == "📚 Cursos":
    st.header("Gestión de Cursos")
    with st.form("nuevo_curso"):
        grad = st.text_input("Grado (Ej: 8-1)")
        mat = st.text_input("Materia")
        if st.form_submit_button("Añadir Curso"):
            supabase.table("cursos").insert({"grado": grad, "materia": mat, "profe_id": st.session_state.user}).execute()
            st.rerun()
    
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        df_c = pd.DataFrame(cursos)
        st.table(df_c[['grado', 'materia']])

# --- SECCIÓN: ESTUDIANTES ---
elif opcion == "👥 Estudiantes":
    st.header("Carga de Estudiantes")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if not cursos:
        st.warning("Primero crea un curso.")
    else:
        opciones_c = [f"{c['grado']} - {c['materia']}" for c in cursos]
        sel_c = st.selectbox("Seleccione el curso para cargar alumnos:", opciones_c)
        g_sel, m_sel = sel_c.split(" - ")
        
        archivo = st.file_uploader("Subir Excel (.xlsx)", type=["xlsx"])
        if archivo:
            df = pd.read_excel(archivo)
            st.write("Vista previa:")
            st.dataframe(df.head())
            
            if st.button("Guardar Estudiantes y Generar Carnets"):
                pdf_buffer = io.BytesIO()
                canv = canvas.Canvas(pdf_buffer, pagesize=landscape(legal))
                x, y = 1.5*cm, 15*cm
                
                for _, fila in df.iterrows():
                    doc = str(fila['documento'])
                    nom = str(fila['nombre']).upper()
                    tel = str(fila.get('whatsapp', ''))
                    
                    # Guardar en Supabase
                    supabase.table("estudiantes").upsert({
                        "documento": doc, "nombre": nom, "whatsapp": tel,
                        "grado": g_sel, "materia": m_sel, "profe_id": st.session_state.user
                    }).execute()
                    
                    # Generar QR para el PDF
                    img_qr = qrcode.make(doc)
                    img_byte = io.BytesIO()
                    img_qr.save(img_byte, format='PNG')
                    canv.drawInlineImage(Image.open(img_byte), x, y, 4*cm, 4*cm)
                    canv.drawString(x, y-0.5*cm, nom[:20])
                    x += 6*cm
                    if x > 30*cm: x, y = 1.5*cm, y-6*cm
                
                canv.save()
                st.success("Estudiantes guardados en la nube.")
                st.download_button("📥 Descargar Carnets PDF", pdf_buffer.getvalue(), f"Carnets_{g_sel}.pdf")

# --- SECCIÓN: SCANNER QR ---
elif opcion == "📸 Scanner QR":
    st.header("Control de Asistencia")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso:", [f"{c['grado']} - {c['materia']}" for c in cursos])
        ga, ma = sel_as.split(" - ")
        tema = st.text_input("Tema de la clase")
        
        if tema:
            col1, col2 = st.columns(2)
            with col1:
                st.info("Coloque el código QR frente a la cámara")
                codigo = qrcode_scanner(key="scanner")
            
            if codigo:
                # Buscar estudiante
                est = supabase.table("estudiantes").select("*").eq("documento", codigo).eq("grado", ga).execute().data
                if est:
                    e = est[0]
                    # Registrar asistencia
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    hora = datetime.now().strftime("%H:%M:%S")
                    
                    # Verificar si ya marcó hoy
                    check = supabase.table("asistencia").select("*").eq("estudiante_id", e['documento']).eq("fecha", hoy).eq("tema", tema).execute().data
                    if not check:
                        supabase.table("asistencia").insert({
                            "estudiante_id": e['documento'], "fecha": hoy, "hora": hora,
                            "grado": ga, "materia": ma, "tema": tema, "profe_id": st.session_state.user
                        }).execute()
                        st.success(f"✅ ASISTENCIA REGISTRADA: {e['nombre']}")
                    else:
                        st.warning(f"El estudiante {e['nombre']} ya fue registrado.")
                else:
                    st.error("Código no reconocido para este curso.")

# --- SECCIÓN: REPORTES ---
elif opcion == "📊 Reportes":
    st.header("Planillas de Asistencia")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_rep = st.selectbox("Curso para reporte:", [f"{c['grado']} - {c['materia']}" for c in cursos])
        gr, mr = sel_rep.split(" - ")
        
        if st.button("Ver Reporte de Hoy"):
            hoy = datetime.now().strftime("%Y-%m-%d")
            data = supabase.table("asistencia").select("estudiante_id, hora, estudiantes(nombre)").eq("fecha", hoy).eq("grado", gr).execute().data
            if data:
                # Procesar datos para mostrar nombre del estudiante
                reporte = []
                for d in data:
                    reporte.append({"Hora": d['hora'], "Nombre": d['estudiantes']['nombre']})
                st.table(pd.DataFrame(reporte))
            else:
                st.write("No hay registros hoy.")

# --- SECCIÓN: AJUSTES ---
elif opcion == "⚙️ Ajustes":
    if st.button("Cerrar Sesión"):
        st.session_state.logueado = False
        st.rerun()
    st.write("---")
    st.write("EduAsistencia Pro v2.0 - Conexión Cloud Supabase")
