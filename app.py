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

# Conexión desde tu database.py
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
                else:
                    st.warning("Faltan datos")

        with tab_rec:
            u_rec = st.text_input("Usuario a recuperar:")
            if u_rec:
                res_u = supabase.table("usuarios").select("*").eq("usuario", u_rec).execute()
                if res_u.data:
                    st.write(f"**Pregunta:** {res_u.data[0]['pregunta_seguridad']}")
                    r_int = st.text_input("Respuesta:", type="password")
                    np_rec = st.text_input("Nueva Contraseña:", type="password")
                    if st.button("🔓 CAMBIAR CLAVE"):
                        if r_int.strip().lower() == res_u.data[0]['respuesta_seguridad']:
                            supabase.table("usuarios").update({"password": hash_password(np_rec)}).eq("usuario", u_rec).execute()
                            st.success("Clave actualizada.")
                        else:
                            st.error("Respuesta incorrecta.")
    st.stop()

# --- CABECERA DE LA APP ---
col_esc, col_txt = st.columns([1, 5])
with col_esc:
    if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=90)
with col_txt:
    st.markdown(f"<h2 style='margin:0;'>{COLEGIO}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; color:#4F8BF9;'><b>{APP_NAME}</b> | Docente: {st.session_state.profe_nom}</p>", unsafe_allow_html=True)
st.divider()

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("Menú Principal", ["📚 Cursos", "👥 Estudiantes", "📸 Scanner QR", "📊 Reportes", "⚙️ Reinicio"])

# --- 1. SECCIÓN CURSOS (CON ELIMINACIÓN) ---
if menu == "📚 Cursos":
    st.subheader("Configuración de Cursos")
    with st.expander("➕ Añadir Nuevo Curso"):
        g_c = st.text_input("Grado (Ej: 801)")
        m_c = st.text_input("Asignatura")
        if st.button("Guardar Curso"):
            if g_c and m_c:
                supabase.table("cursos").insert({"grado": g_c, "materia": m_c, "profe_id": st.session_state.user}).execute()
                st.success("Curso añadido")
                st.rerun()

    st.write("### Mis Cursos Actuales")
    data_c = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if data_c:
        for c in data_c:
            col1, col2 = st.columns([5, 1])
            col1.info(f"**{c['grado']}** - {c['materia']}")
            if col2.button("🗑️", key=f"del_{c['id']}"):
                supabase.table("cursos").delete().eq("id", c['id']).execute()
                st.rerun()
    else:
        st.info("No tienes cursos creados.")

# --- 2. SECCIÓN ESTUDIANTES ---
elif menu == "👥 Estudiantes":
    st.subheader("Carga y Carnetización")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if not cursos:
        st.warning("Debes crear un curso primero.")
    else:
        sel_c = st.selectbox("Seleccione el curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        g_s, m_s = sel_c.split(" | ")
        f = st.file_uploader("Subir listado Excel (.xlsx)", type=["xlsx"])
        if f and st.button("Generar Carnets QR"):
            df = pd.read_excel(f)
            pdf = io.BytesIO()
            canv = canvas.Canvas(pdf, pagesize=landscape(legal))
            x, y = 1.5*cm, 15*cm
            for _, r in df.iterrows():
                doc, nom = str(r['documento']), str(r['nombre']).upper()
                tel = str(r.get('whatsapp', ''))
                supabase.table("estudiantes").upsert({
                    "documento": doc, "nombre": nom, "whatsapp": tel,
                    "grado": g_s, "materia": m_s, "profe_id": st.session_state.user
                }).execute()
                qr = qrcode.make(doc)
                b = io.BytesIO(); qr.save(b, format='PNG')
                canv.drawInlineImage(Image.open(b), x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 8); canv.drawString(x, y-0.5*cm, nom[:20])
                x += 6.5*cm
                if x > 30*cm: x, y = 1.5*cm, y-6.5*cm
            canv.save()
            st.success("Estudiantes sincronizados con la nube.")
            st.download_button("📥 Descargar PDF", pdf.getvalue(), f"Carnets_{g_s}.pdf")

# --- 3. SECCIÓN SCANNER ---
elif menu == "📸 Scanner QR":
    st.subheader("Control de Asistencia Real")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la clase:")
        if tema:
            if not st.session_state.captura_finalizada:
                if st.button("⏹️ Finalizar y Ver Ausentes", type="primary"):
                    st.session_state.captura_finalizada = True; st.rerun()
                cod = qrcode_scanner(key="scanner")
                if cod:
                    est = supabase.table("estudiantes").select("*").eq("documento", cod).eq("grado", ga).execute().data
                    if est:
                        e = est[0]; hoy = datetime.now().strftime("%Y-%m-%d")
                        check = supabase.table("asistencia").select("*").eq("estudiante_id", cod).eq("fecha", hoy).eq("tema", tema).execute().data
                        if not check:
                            supabase.table("asistencia").insert({
                                "estudiante_id": cod, "fecha": hoy, "hora": datetime.now().strftime("%H:%M:%S"),
                                "grado": ga, "materia": ma, "tema": tema, "profe_id": st.session_state.user
                            }).execute()
                            st.success(f"✅ REGISTRADO: {e['nombre']}")
            else:
                st.subheader("🔔 Reporte de Ausencia")
                if st.button("🔄 Seguir Escaneando"):
                    st.session_state.captura_finalizada = False; st.rerun()
                total = pd.DataFrame(supabase.table("estudiantes").select("*").eq("grado", ga).eq("profe_id", st.session_state.user).execute().data)
                hoy = datetime.now().strftime("%Y-%m-%d")
                pres = [p['estudiante_id'] for p in supabase.table("asistencia").select("estudiante_id").eq("fecha", hoy).eq("tema", tema).execute().data]
                aus = total[~total['documento'].isin(pres)]
                for _, a in aus.iterrows():
                    c1, c2 = st.columns([3, 1])
                    c1.error(f"❌ {a['nombre']}")
                    if a['whatsapp']:
                        msg = urllib.parse.quote(f"Cordial saludo. El estudiante {a['nombre']} no asistió hoy a la clase de {ma}. Atentamente, Prof. {st.session_state.profe_nom}.")
                        c2.markdown(f'<a href="https://wa.me/57{a["whatsapp"]}?text={msg}" target="_blank"><button style="background:#25d366; color:white; border:none; border-radius:5px; padding:5px; width:100%;">📲 Avisar</button></a>', unsafe_allow_html=True)

# --- 4. SECCIÓN REPORTES ---
elif menu == "📊 Reportes":
    st.subheader("Planillas de Asistencia")
    cursos = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_r = st.selectbox("Ver curso:", [f"{c['grado']} | {c['materia']}" for c in cursos])
        gr, mr = sel_r.split(" | ")
        asist_data = supabase.table("asistencia").select("*, estudiantes(nombre)").eq("grado", gr).eq("profe_id", st.session_state.user).execute().data
        if asist_data:
            df_asist = []
            for d in asist_data:
                df_asist.append({"Fecha": d['fecha'], "Hora": d['hora'], "Estudiante": d['estudiantes']['nombre'], "Tema": d['tema']})
            st.dataframe(pd.DataFrame(df_asist))
        else:
            st.info("No hay registros de asistencia para este curso.")

# --- 5. SECCIÓN REINICIO ---
elif menu == "⚙️ Reinicio":
    st.error("### ⚠️ Zona de Peligro")
    st.write("Esta acción borrará permanentemente tus cursos y estudiantes de la nube.")
    if st.button("🗑️ ELIMINAR TODOS MIS DATOS"):
        supabase.table("asistencia").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("estudiantes").delete().eq("profe_id", st.session_state.user).execute()
        supabase.table("cursos").delete().eq("profe_id", st.session_state.user).execute()
        st.success("Datos eliminados correctamente.")
        st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()
