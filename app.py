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

# Importación desde el módulo database
from modules.database import supabase, hash_password

# --- CONFIGURACIÓN ---
APP_NAME = "EduAsistencia Pro"
COLEGIO = "I.E. San Antonio de Padua"

st.set_page_config(page_title=APP_NAME, layout="wide")

if 'logueado' not in st.session_state:
    st.session_state.logueado = False

# --- LOGIN ---
if not st.session_state.logueado:
    st.title(APP_NAME)
    t1, t2 = st.tabs(["Acceso", "Registro"])
    
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            res = supabase.table("usuarios").select("*").eq("usuario", u).eq("password", hash_password(p)).execute()
            if res.data:
                st.session_state.logueado = True
                st.session_state.user = u
                st.session_state.profe_nom = res.data[0]['nombre']
                st.rerun()
            else:
                st.error("Error de acceso")
    
    with t2:
        nu = st.text_input("Nuevo Usuario")
        nn = st.text_input("Nombre Real")
        np = st.text_input("Nueva Clave", type="password")
        if st.button("Registrar"):
            supabase.table("usuarios").insert({"usuario": nu, "password": hash_password(np), "nombre": nn}).execute()
            st.success("Registrado")
    st.stop()

# --- CUERPO ---
st.write(f"Bienvenido, Prof. {st.session_state.profe_nom}")
if st.button("Cerrar Sesión"):
    st.session_state.logueado = False
    st.rerun()

menu = st.sidebar.radio("Ir a:", ["Cursos", "Scanner"])

if menu == "Cursos":
    st.subheader("Mis Cursos")
    g = st.text_input("Grado")
    m = st.text_input("Materia")
    if st.button("Guardar"):
        supabase.table("cursos").insert({"grado": g, "materia": m, "profe_id": st.session_state.user}).execute()
        st.rerun()
    
    c_data = supabase.table("cursos").select("*").eq("profe_id", st.session_state.user).execute()
    if c_data.data:
        st.table(pd.DataFrame(c_data.data)[['grado', 'materia']])
