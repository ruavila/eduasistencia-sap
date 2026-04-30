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
            if os.path.exists(ESCUDO_PATH): st.image(ESCUDO_PATH, width=80)
        with c2:
            st.markdown(f"### {COLEGIO}\n# {APP_NAME}")
        
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

# --- 2. ESTUDIANTES Y CARNETS ---
elif menu == "👤 Estudiantes":
    st.subheader("Carga de Estudiantes y Carnetización")
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos])
        gs, ms = sel.split(" | ")
        f = st.file_uploader("Subir Excel", type=["xlsx"])
        if f and st.button("Procesar y Generar PDF"):
            df = pd.read_excel(f); df.columns = [str(c).strip().lower() for c in df.columns]
            pdf = io.BytesIO(); canv = canvas.Canvas(pdf, pagesize=landscape(legal))
            ancho_pg, alto_pg = landscape(legal)
            x, y, col = 1.5*cm, alto_pg-5*cm, 0
            for _, r in df.iterrows():
                e_id = str(r.get('estudiante_id', r.get('documento', ''))).split('.')[0]
                e_nm = str(r.get('nombre', '')).upper()
                e_ws = "".join(filter(str.isdigit, str(r.get('whatsapp', '')))).split('.')[0]
                
                supabase.table("estudiantes").upsert({
                    "documento": e_id, "nombre": e_nm, "whatsapp": e_ws, 
                    "grado": gs, "materia": ms, "profe_id": st.session_state.user
                }).execute()
                
                qr = qrcode.make(e_id); t_qr = io.BytesIO(); qr.save(t_qr, format='PNG'); t_qr.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_qr:
                    tmp_qr_path = tmp_qr.name
                    tmp_qr.write(t_qr.getvalue())

                canv.drawInlineImage(tmp_qr_path, x, y, 4*cm, 4*cm)
                canv.setFont("Helvetica-Bold", 7)
                canv.drawCentredString(x + 2*cm, y-0.4*cm, e_nm[:25])
                canv.setFont("Helvetica", 6)
                canv.drawCentredString(x + 2*cm, y-0.8*cm, f"Grado: {gs} - {IE_INITIALS}")
                
                col += 1
                if col >= 3: x, y, col = 1.5*cm, y-6.5*cm, 0
                else: x += 6.5*cm
                if y < 2*cm: canv.showPage(); x, y, col = 1.5*cm, alto_pg-5*cm, 0
                os.remove(tmp_qr_path)
            canv.save()
            st.download_button("📥 Descargar Carnets", pdf.getvalue(), f"QR_{gs}.pdf")

# --- 3. SCANNER QR ---
elif menu == "📷 Scanner QR":
    st.subheader("Captura de Asistencia")
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_as = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos])
        ga, ma = sel_as.split(" | ")
        tema = st.text_input("Tema de la clase:")
        if tema:
            if not st.session_state.captura_finalizada:
                if st.button("⏹️ Finalizar y Ver Ausentes", type="primary", use_container_width=True):
                    st.session_state.captura_finalizada = True; st.rerun()
                cod = qrcode_scanner(key=f"sc_{ga}")
                if cod:
                    id_cl = "".join(filter(str.isalnum, str(cod)))
                    res = supabase.table("estudiantes").select("documento, nombre").ilike("documento", f"%{id_cl}%").eq("grado", ga).eq("profe_id", st.session_state.user).execute().data
                    if res:
                        doc, nom = res[0]['documento'], res[0]['nombre']; hoy = datetime.now().strftime("%Y-%m-%d")
                        check = supabase.table("asistencia").select("id").eq("estudiante_id", doc).eq("fecha", hoy).eq("tema", tema).execute().data
                        if not check:
                            supabase.table("asistencia").insert({
                                "estudiante_id": doc, "fecha": hoy, "hora": datetime.now().strftime("%H:%M:%S"), 
                                "grado": ga, "materia": ma, "tema": tema, "profe_id": st.session_state.user
                            }).execute()
                            st.success(f"Registrado: {nom}")
            else:
                st.markdown("### 🔔 Estudiantes Ausentes")
                if st.button("🔄 Volver al Scanner"):
                    st.session_state.captura_finalizada = False; st.rerun()
                hoy = datetime.now().strftime("%Y-%m-%d")
                total_data = supabase.table("estudiantes").select("*").eq("grado", ga).eq("profe_id", st.session_state.user).execute().data
                pres_data = supabase.table("asistencia").select("estudiante_id").eq("fecha", hoy).eq("grado", ga).eq("tema", tema).execute().data
                total = pd.DataFrame(total_data) if total_data else pd.DataFrame()
                pres = pd.DataFrame(pres_data) if pres_data else pd.DataFrame()
                if not total.empty:
                    aus = total[~total['documento'].isin(pres['estudiante_id'])] if not pres.empty else total
                    for _, a in aus.iterrows():
                        c1, c2 = st.columns([3, 1])
                        c1.error(f"❌ {a['nombre']}")
                        if a.get('whatsapp'):
                            msg = urllib.parse.quote(f"Cordial saludo.\n\nLe informo que el estudiante {a['nombre']} NO asistió hoy ({hoy}) a la clase de {ma} ({tema}).\n\nAtentamente,\nProf. {st.session_state.profe_nom}\n{COLEGIO}")
                            c2.markdown(f'<a href="https://wa.me/57{a["whatsapp"]}?text={msg}" target="_blank"><button style="background:#25d366; color:white; border:none; padding:8px; border-radius:5px; width:100%; font-weight:bold; cursor:pointer;">📲 Notificar</button></a>', unsafe_allow_html=True)

# --- 4. REPORTES (CON SOLUCIÓN DE ESCUDO TRANSPARENTE) ---
elif menu == "📊 Reportes":
    st.subheader("Reportes Detallados")
    cursos = supabase.table("cursos").select("grado, materia").eq("profe_id", st.session_state.user).execute().data
    if cursos:
        sel_r = st.selectbox("Curso:", [f"{r['grado']} | {r['materia']}" for r in cursos])
        gr, mr = sel_r.split(" | ")
        if st.button("📄 Generar Planilla PDF", type="primary", use_container_width=True):
            ests_db = supabase.table("estudiantes").select("documento, nombre").eq("grado", gr).eq("profe_id", st.session_state.user).order("nombre").execute().data
            asist_db = supabase.table("asistencia").select("estudiante_id, fecha, tema").eq("grado", gr).eq("profe_id", st.session_state.user).execute().data
            ests = pd.DataFrame(ests_db) if ests_db else pd.DataFrame()
            asist = pd.DataFrame(asist_db) if asist_db else pd.DataFrame()
            
            if not ests.empty:
                clases = asist[['fecha', 'tema']].drop_duplicates().sort_values(by='fecha').values.tolist() if not asist.empty else []
                pdf_io = io.BytesIO(); canv = canvas.Canvas(pdf_io, pagesize=landscape(legal))
                ancho, alto = landscape(legal); mrg = 1.0*cm
                
                # --- LÓGICA DE ESCUDO CON MÁSCARA DE TRANSPARENCIA ---
                if os.path.exists(ESCUDO_PATH):
                    try:
                        img_pil = Image.open(ESCUDO_PATH).convert("RGBA")
                        r, g, b, a = img_pil.split()
                        img_rgb = Image.merge("RGB", (r, g, b))
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f_rgb:
                            img_rgb.save(f_rgb.name, format="PNG")
                            path_rgb = f_rgb.name
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f_a:
                            a.save(f_a.name, format="PNG")
                            path_a = f_a.name
                        canv.drawImage(path_rgb, mrg, alto-2.5*cm, width=2.2*cm, height=2.2*cm, mask=path_a)
                        os.remove(path_rgb); os.remove(path_a)
                    except:
                        pass
                
                canv.setFont("Helvetica-Bold", 14); canv.drawCentredString(ancho/2, alto-1.2*cm, COLEGIO)
                canv.setFont("Helvetica", 9); canv.drawString(mrg+2.5*cm, alto-1.7*cm, f"Materia: {mr} | Grado: {gr} | Docente: {st.session_state.profe_nom}")
                w_nom, n_cl = 7.5*cm, len(clases)
                w_col = min(max((ancho - (mrg*2) - w_nom - 3.2*cm) / n_cl, 1.5*cm), 3.5*cm) if n_cl > 0 else 1.5*cm
                y_f = alto-4.2*cm
                canv.rect(mrg, y_f, w_nom, 1.2*cm); canv.setFont("Helvetica-Bold", 8); canv.drawCentredString(mrg+w_nom/2, y_f+0.5*cm, "ESTUDIANTE")
                x_h = mrg+w_nom
                for f, t in clases:
                    canv.rect(x_h, y_f, w_col, 1.2*cm); canv.setFont("Helvetica-Bold", 6)
                    canv.drawCentredString(x_h+w_col/2, y_f+0.85*cm, f"{str(t)[:15]}")
                    canv.setFont("Helvetica", 6); canv.drawCentredString(x_h+w_col/2, y_f+0.25*cm, f"{f}")
                    x_h += w_col
                canv.rect(x_h, y_f, 1.6*cm, 1.2*cm); canv.drawCentredString(x_h+0.8*cm, y_f+0.5*cm, "Asist.")
                canv.rect(x_h+1.6*cm, y_f, 1.6*cm, 1.2*cm); canv.drawCentredString(x_h+2.4*cm, y_f+0.5*cm, "Ausen.")
                
                y_f -= 0.55*cm
                for i, est in ests.iterrows():
                    if y_f < 2*cm: canv.showPage(); y_f = alto-3.5*cm
                    canv.rect(mrg, y_f, w_nom, 0.55*cm); canv.setFont("Helvetica", 7)
                    canv.drawString(mrg+0.1*cm, y_f+0.15*cm, f"{i+1}. {est['nombre'][:40]}")
                    x_f, t_as, t_au = mrg+w_nom, 0, 0
                    for f, t in clases:
                        canv.rect(x_f, y_f, w_col, 0.55*cm)
                        presencia = not asist[(asist['estudiante_id'].astype(str)==str(est['documento'])) & (asist['fecha']==f) & (asist['tema']==t)].empty if not asist.empty else False
                        if presencia:
                            canv.setFont("ZapfDingbats", 8); canv.drawCentredString(x_f+w_col/2, y_f+0.15*cm, u"\u2714")
                            t_as += 1
                        else:
                            canv.setFont("Helvetica-Bold", 8); canv.drawCentredString(x_f+w_col/2, y_f+0.15*cm, "X")
                            t_au += 1
                        x_f += w_col
                    canv.setFont("Helvetica-Bold", 7); canv.rect(x_f, y_f, 1.6*cm, 0.55*cm); canv.drawCentredString(x_f+0.8*cm, y_f+0.15*cm, str(t_as))
                    canv.rect(x_f+1.6*cm, y_f, 1.6*cm, 0.55*cm); canv.drawCentredString(x_f+2.4*cm, y_f+0.15*cm, str(t_au))
                    y_f -= 0.55*cm
                canv.save(); st.download_button("📥 Descargar Reporte", pdf_io.getvalue(), f"Reporte_{gr}.pdf", use_container_width=True)

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

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logueado = False; st.rerun()
