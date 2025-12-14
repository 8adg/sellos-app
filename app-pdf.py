import streamlit as st
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import uuid
import mercadopago
import base64
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Queselló! - Editor",
    page_icon="assets/logo.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CONFIGURACIÓN COMERCIAL ---
PRECIO_SELLO = 20500
try:
    MP_ACCESS_TOKEN = st.secrets["mercadopago"]["access_token"]
    mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    MP_ACCESS_TOKEN = None

# --- 1. CONFIGURACIÓN ---
FUENTES_DISPONIBLES = {
    "Aleo Regular": "assets/fonts/Aleo-Regular.ttf",
    "Aleo Italic": "assets/fonts/Aleo-Italic.ttf",
    "Amaze (Manuscrita)": "assets/fonts/amaze.ttf",
    "Great Vibes": "assets/fonts/GreatVibes-Regular.ttf",
    "Montserrat Regular": "assets/fonts/Montserrat-Regular.ttf",
    "Montserrat SemiBold": "assets/fonts/Montserrat-SemiBold.ttf",
    "Mukta Mahee": "assets/fonts/MuktaMahee-Regular.ttf",
    "Mukta Mahee SemiBold": "assets/fonts/MuktaMahee-SemiBold.ttf",
    "Playwrite": "assets/fonts/Playwrite-Regular.ttf",
    "Roboto Regular": "assets/fonts/Roboto-Regular.ttf",
    "Roboto Medium": "assets/fonts/Roboto-Medium.ttf",
    "Arial (Sistema)": "Arial"
}

# --- CONSTANTES ---
FACTOR_PT_A_MM = 0.3527
ANCHO_REAL_MM = 36
ALTO_REAL_MM = 15
SCALE_PREVIEW = 20
SCALE_HD = 80

# --- DATOS DE EJEMPLO ---
EJEMPLO_INICIAL = [
    {"texto": "Juan Pérez", "font_idx": 2, "size": 16, "offset": -1.5},
    {"texto": "DISEÑADOR GRÁFICO", "font_idx": 5, "size": 8, "offset": 0.0},
    {"texto": "Matrícula N° 2040", "font_idx": 4, "size": 7, "offset": 0.0}
]

# --- 🎨 ESTILOS CSS (DARK MODE FIX + MOBILE ROW FIX) ---
st.markdown("""
<style>
    .stApp { background-color: #fafafa; }

    /* Card Styling */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        padding: 12px;
        margin-bottom: 8px;
    }

    /* Textos oscuros siempre (Override Dark Mode) */
    label, p, h1, h2, h3, div, span, .stMarkdown { color: #333333 !important; }

    /* Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        color: #212529 !important;
        background-color: #ffffff !important;
        border: 1px solid #ced4da;
    }

    /* Iconos de las flechas select */
    [data-baseweb="select"] svg { fill: #212529 !important; }

    /* Estilo para los Iconos de Tamaño/Posición */
    .icon-label {
        font-size: 1.1rem;
        font-weight: bold;
        text-align: center;
        padding-top: 10px;
        color: #555 !important;
        line-height: 1;
    }

    /* --- ARREGLO BOTONES EN DARK MODE --- */
    /* Apuntamos a los botones secundarios (Flechas y Steppers) */
    button[kind="secondary"], .stNumberInput button {
        background-color: #f0f2f6 !important;
        color: #333333 !important; /* Texto oscuro forzado */
        border: 1px solid #ced4da !important;
    }
    button[kind="secondary"]:hover, .stNumberInput button:hover {
        border-color: #a3a8b4 !important;
        color: #000000 !important;
        background-color: #e2e6ea !important;
    }

    /* Botones de Acción (Confirmar/Pagar) */
    div[data-testid="stForm"] button, .stButton button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        font-weight: bold;
        border: none;
    }

    /* --- MOBILE OPTIMIZATION --- */
    @media (max-width: 768px) {

        /* 1. Header Sticky */
        .mobile-sticky-header {
            position: fixed;
            top: 50px;
            left: 0; right: 0;
            z-index: 9999;
            background-color: #ffffff;
            padding: 5px;
            border-bottom: 2px solid #28a745;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        .mobile-sticky-header img {
            max-width: 90%; height: auto;
            border: 1px solid #ddd; border-radius: 4px;
        }
        .block-container { padding-top: 200px !important; }
        .desktop-only-col { display: none; }

        /* 2. FORZAR FILA HORIZONTAL (NO STACKING) */
        /* Esto obliga a las columnas dentro de la card a quedarse en una sola línea */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            gap: 5px !important;
        }

        /* Ajustar anchos para que entren */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"] {
            min-width: 0 !important;
            width: auto !important;
            flex: 1 !important;
            padding: 0 2px !important;
        }

        /* Ajuste fino para botones */
        div[data-testid="column"] button {
             padding: 0px !important;
        }
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- UTILS IMAGEN HTML ---
def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- HEADER ---
mobile_preview_placeholder = st.empty()

c_logo, c_title = st.columns([0.15, 0.85])
with c_logo:
    if os.path.exists("assets/logo.svg"): st.image("assets/logo.svg", width=90)
    elif os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=90)
with c_title:
    st.title("Editor de Sellos Automáticos")
    if PRECIO_SELLO > 0:
        st.markdown(f"Diseña tu **Queselló!**. Precio: **${PRECIO_SELLO}**")
st.write("---")

# --- HELPERS ---
def calcular_ancho_texto_mm(texto, ruta_fuente, size_pt):
    if not texto: return 0
    scale_measure = 10
    size_px = int(size_pt * FACTOR_PT_A_MM * scale_measure)
    try:
        if ruta_fuente == "Arial": raise Exception
        font = ImageFont.truetype(ruta_fuente, size_px)
    except: font = ImageFont.load_default()
    width_px = font.getlength(texto)
    return width_px / scale_measure

def get_font_metrics_mm(ruta_fuente, size_pt):
    try:
        scale = 100
        size_px = int(size_pt * FACTOR_PT_A_MM * scale)
        if ruta_fuente == "Arial" or not os.path.exists(ruta_fuente):
            ascent = size_px * 0.8
        else:
            font = ImageFont.truetype(ruta_fuente, size_px)
            ascent, descent = font.getmetrics()
        return ascent / scale
    except:
        return (size_pt * FACTOR_PT_A_MM) * 0.78

# --- CALLBACKS ---
def mover_arriba(key):
    st.session_state[key] = max(-10.0, st.session_state[key] - 0.5)
def mover_abajo(key):
    st.session_state[key] = min(10.0, st.session_state[key] + 0.5)

# --- MOTOR GRÁFICO ---
def renderizar_imagen(datos_lineas, scale, dibujar_borde=True, color_borde="black", mostrar_guias=False):
    w_px = int(ANCHO_REAL_MM * scale)
    h_px = int(ALTO_REAL_MM * scale)
    img = Image.new('RGB', (w_px, h_px), "white")
    draw = ImageDraw.Draw(img)

    if dibujar_borde:
        grosor = 4 if color_borde == "red" else max(2, int(scale/5))
        draw.rectangle([(0,0), (w_px-1, h_px-1)], outline=color_borde, width=grosor)

    total_h_px = 0
    for linea in datos_lineas:
        size_pt = linea['size']
        size_px = size_pt * FACTOR_PT_A_MM * scale
        total_h_px += size_px

    y_cursor_base = (h_px - total_h_px) / 2

    for i, linea in enumerate(datos_lineas):
        txt = linea['texto']
        f_path = linea['fuente']
        sz_pt = linea['size']
        offset_mm