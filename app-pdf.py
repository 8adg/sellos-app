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

# --- 🎨 ESTILOS CSS (RESPONSIVE PRO) ---
st.markdown("""
<style>
    .stApp { background-color: #fafafa; }

    /* Card Styling */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        padding: 15px;
        margin-bottom: 10px;
    }

    /* Textos oscuros */
    label, p, h1, h2, h3, div, span { color: #333333 !important; }

    /* Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
        color: #212529 !important;
        background-color: #ffffff !important;
        border: 1px solid #ced4da;
    }

    /* Iconos de las flechas select */
    [data-baseweb="select"] svg { fill: #212529 !important; }

    /* Estilo para los Iconos de Tamaño/Posición */
    .icon-label {
        font-size: 1.2rem;
        font-weight: bold;
        text-align: center;
        padding-top: 15px;
        color: #555;
    }

    /* Botones */
    .stButton button {
        border-radius: 8px;
        font-weight: bold;
        width: 100%;
        transition: all 0.2s;
    }
    div[data-testid="stForm"] button {
        background-color: #28a745 !important;
        color: white !important;
        border: none;
    }

    /* --- MOBILE ONLY CSS --- */
    @media (max-width: 768px) {
        /* 1. Contenedor Sticky para la imagen en el tope */
        .mobile-sticky-header {
            position: fixed;
            top: 120px;
            z-index: 9999;
            background-color: #ffffff;
            padding: 10px;
            border-bottom: 2px solid #28a745;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
            margin-left: -1rem;
            margin-right: -1rem;
            margin-top: -4rem; /* Subir para tapar header default si molesta */
        }

        .mobile-sticky-header img {
            max-width: 90%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }

        /* 2. Ocultar la columna derecha original en mobile (para no duplicar imagen) */
        .desktop-only-col {
            display: none;
        }

        /* Ajuste de padding para inputs */
        .block-container {
            padding-top: 0rem;
        }
    }

    /* --- DESKTOP ONLY CSS --- */
    @media (min-width: 769px) {
        .mobile-sticky-header {
            display: none;
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
# Usamos un contenedor vacío aquí que llenaremos al final con la imagen sticky para mobile
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
        offset_mm = linea['offset_y']

        sz_px = int(sz_pt * FACTOR_PT_A_MM * scale)
        offset_px = int(offset_mm * scale)

        try:
            if f_path == "Arial": raise Exception
            font = ImageFont.truetype(f_path, sz_px)
        except: font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), txt, font=font)
        text_w = bbox[2] - bbox[0]
        x_pos = (w_px - text_w) / 2
        y_visual_px = y_cursor_base + offset_px

        draw.text((x_pos, y_visual_px), txt, font=font, fill="black")

        if mostrar_guias:
            color_guia = (0, 150, 255)
            grosor_guia = max(1, int(scale / 20))
            tamano_fuente_cota = int(8 * scale / 6)
            try: ascent, descent = font.getmetrics()
            except: ascent = sz_px * 0.8
            y_base_guia = y_visual_px + ascent
            draw.line([(0, y_base_guia), (w_px, y_base_guia)], fill=color_guia, width=grosor_guia)

            # Cota
            try: font_small = ImageFont.truetype("assets/fonts/Roboto-Regular.ttf", tamano_fuente_cota)
            except: font_small = ImageFont.load_default()
            # No dibujamos texto en preview mobile pequeña para no ensuciar

            draw.rectangle([x_pos, y_visual_px, x_pos + text_w, y_visual_px + sz_px], outline=(220,220,220), width=1)

        y_cursor_base += sz_px
    return img

# --- GENERADOR PDF ---
def generar_pdf_hibrido(datos_lineas, cliente, incluir_guias_hd=False):
    pdf = FPDF(orientation='P', unit='mm', format=(ANCHO_REAL_MM, ALTO_REAL_MM))

    # PÁG 1: Vectorial
    pdf.add_page(); pdf.set_margins(0,0,0); pdf.set_auto_page_break(False, margin=0)
    font_map = {}; font_counter = 1
    for ruta in FUENTES_DISPONIBLES.values():
        if ruta != "Arial" and os.path.exists(ruta):
            family_name = f"F{font_counter}"
            try: pdf.add_font(family_name, "", ruta); font_map[ruta] = family_name; font_counter += 1
            except: pass

    h_total_mm = sum([l['size'] * FACTOR_PT_A_MM for l in datos_lineas])
    y_base = (ALTO_REAL_MM - h_total_mm) / 2

    for l in datos_lineas:
        ruta = l['fuente']
        fam = font_map.get(ruta, "Arial")
        pdf.set_font(fam, size=l['size'])
        try: txt = l['texto'].encode('latin-1', 'replace').decode('latin-1')
        except: txt = l['texto']
        txt_width = pdf.get_string_width(txt)
        x_centered = (ANCHO_REAL_MM - txt_width) / 2

        ascent_mm = get_font_metrics_mm(ruta, l['size'])
        y_final_baseline = y_base + l['offset_y'] + ascent_mm

        pdf.text(x_centered, y_final_baseline, txt)
        y_base += (l['size'] * FACTOR_PT_A_MM)

    # PÁG 2: Imagen HD
    pdf.add_page()
    img_hd = renderizar_imagen(datos_lineas, scale=SCALE_HD, dibujar_borde=False, mostrar_guias=incluir_guias_hd)
    temp_path = f"temp_{datetime.now().strftime('%f')}.jpg"
    img_hd.save(temp_path, quality=100, subsampling=0)
    pdf.image(temp_path, x=0, y=0, w=ANCHO_REAL_MM, h=ALTO_REAL_MM)
    if os.path.exists(temp_path): os.remove(temp_path)

    fname = f"{cliente.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}.pdf"
    return bytes(pdf.output()), fname

# --- EMAIL ---
def enviar_email(pdf_bytes, nombre_pdf, cliente, wpp_cliente, id_pago):
    try:
        remitente = st.secrets["email"]["usuario"]
        password = st.secrets["email"]["password"]
        destinatario = st.secrets["email"]["destinatario"]

        msg = MIMEMultipart()
        msg['From'] = remitente; msg['To'] = destinatario; msg['Subject'] = f"Pedido PAGADO: {cliente}"
        cuerpo = f"""
        NUEVO PEDIDO CONFIRMADO
        -----------------------
        Cliente: {cliente}
        WhatsApp: {wpp_cliente}
        ID Pago MP: {id_pago}
        Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        """
        msg.attach(MIMEText(cuerpo, 'plain'))
        part = MIMEBase('application', "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{nombre_pdf}"')
        msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(); server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e: st.error(f"Error Email: {e}"); return False

# --- MP UTILS ---
def crear_preferencia_pago(nombre_cliente, ref_id):
    if not MP_ACCESS_TOKEN: return "https://www.mercadopago.com.ar"
    preference_data = {
        "items": [{"title": f"Sello - {nombre_cliente}", "quantity": 1, "unit_price": PRECIO_SELLO, "currency_id": "ARS"}],
        "external_reference": ref_id,
        "back_urls": {"success": "https://www.google.com", "failure": "https://www.google.com", "pending": "https://www.google.com"},
        "auto_return": "approved"
    }
    try:
        res = mp_sdk.preference().create(preference_data)
        return res["response"]["init_point"]
    except Exception as e: st.error(f"Error MP: {e}"); return None

def verificar_pago_mp(ref_id):
    if not MP_ACCESS_TOKEN: return "SIMULADO_123"
    filters = {"external_reference": ref_id, "status": "approved"}
    try:
        res = mp_sdk.payment().search(filters)
        if res["response"]["results"]: return res["response"]["results"][0]["id"]
        return None
    except: return None

# --- ESTADO DE SESIÓN ---
if 'pedido_id' not in st.session_state: st.session_state.pedido_id = str(uuid.uuid4())
if 'step' not in st.session_state: st.session_state.step = 'diseño'

# --- INTERFAZ PRINCIPAL ---

col_izq, col_espacio, col_der = st.columns([1, 0.1, 1])

# BLOQUEO DE EDICIÓN
inputs_disabled = st.session_state.step != 'diseño'

# --- COLUMNA IZQUIERDA: CONFIGURACIÓN ---
with col_izq:
    st.subheader("🛠️ Configuración")

    cant = st.selectbox("Cantidad de líneas", [1,2,3,4], index=2, disabled=inputs_disabled)
    st.write("")

    datos = []

    for i in range(cant):
        if i < len(EJEMPLO_INICIAL):
            def_txt = EJEMPLO_INICIAL[i]["texto"]
            def_idx = EJEMPLO_INICIAL[i]["font_idx"]
            def_sz = EJEMPLO_INICIAL[i]["size"]
            def_off = EJEMPLO_INICIAL[i].get("offset", 0.0)
        else:
            def_txt = ""; def_idx = 0; def_sz = 9; def_off = 0.0

        # INICIO CARD
        with st.container(border=True):
            # FILA 1: Texto (Ancho) y Fuente (Angosto)
            c_top1, c_top2 = st.columns([0.65, 0.35])
            with c_top1:
                t = st.text_input(f"t{i}", value=def_txt, key=f"ti{i}", placeholder=f"Línea {i+1}", label_visibility="collapsed", disabled=inputs_disabled)
            with c_top2:
                f_key = st.selectbox(f"f{i}", list(FUENTES_DISPONIBLES.keys()), index=def_idx, key=f"fi{i}", label_visibility="collapsed", disabled=inputs_disabled)

            # FILA 2: Icono Sz | Slider Sz | Icono Pos | Slider Pos
            c_icon1, c_slid1, c_icon2, c_slid2 = st.columns([0.1, 0.4, 0.1, 0.4])

            with c_icon1: st.markdown('<div class="icon-label">Aᴀ</div>', unsafe_allow_html=True)
            with c_slid1: slider_val = st.slider(f"s{i}", 6, 26, value=def_sz, key=f"si{i}", label_visibility="collapsed", disabled=inputs_disabled)

            with c_icon2: st.markdown('<div class="icon-label">↕</div>', unsafe_allow_html=True)
            with c_slid2: offset = st.slider(f"o{i}", -10.0, 10.0, value=float(def_off), step=0.5, key=f"oi{i}", label_visibility="collapsed", disabled=inputs_disabled)

            # Validación Ancho
            ruta_fuente = FUENTES_DISPONIBLES[f_key]
            ancho_actual_mm = calcular_ancho_texto_mm(t, ruta_fuente, slider_val)
            size_final = slider_val
            if ancho_actual_mm > ANCHO_REAL_MM:
                size_ajustado = (slider_val * (ANCHO_REAL_MM / ancho_actual_mm)) - 0.5
                size_final = int(size_ajustado)
                st.caption(f"⚠️ Ajustado a {size_final}pt")

            datos.append({"texto": t, "fuente": ruta_fuente, "size": size_final, "offset_y": offset})

# --- CÁLCULO VERTICAL ---
altura_total_usada_mm = sum([d['size'] * FACTOR_PT_A_MM for d in datos])
es_valido_vertical = (ALTO_REAL_MM - altura_total_usada_mm) >= -1.0

# --- RENDERIZAR IMAGEN PREVIEW ---
if not es_valido_vertical:
    color_borde = "red"
else:
    color_borde = "black"

# Generamos la imagen con Pillow
img_pil = renderizar_imagen(datos, scale=SCALE_PREVIEW, color_borde=color_borde, mostrar_guias=False)

# Convertimos a HTML Base64 para el Sticky Header en Mobile
img_b64 = pil_to_base64(img_pil)

# --- INYECTAR HEADER STICKY (SOLO MOBILE VIA CSS) ---
st.markdown(f"""
<div class="mobile-sticky-header">
    <div style="font-size:0.9rem; font-weight:bold; margin-bottom:5px;">Vista Previa</div>
    <img src="data:image/png;base64,{img_b64}" />
    <div style="font-size: 0.8rem; margin-top: 5px; color: {'red' if not es_valido_vertical else 'green'}">
        {altura_total_usada_mm:.1f}mm / 15mm
    </div>
</div>
""", unsafe_allow_html=True)


# --- COLUMNA DERECHA (DESKTOP) ---
with col_der:
    # Usamos clase desktop-only-col para ocultar esto en mobile via CSS y no duplicar
    st.markdown('<div class="desktop-only-col">', unsafe_allow_html=True)

    st.subheader("👁️ Vista Previa")
    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Altura Texto", f"{altura_total_usada_mm:.1f} mm")
        m2.metric("Sello", f"{ANCHO_REAL_MM} mm", delta_color="normal")
        mostrar_guias = st.checkbox("📏 Guías Técnicas", value=False, disabled=inputs_disabled)

    if not es_valido_vertical: st.error("⛔ EXCESO DE ALTURA")

    # Imagen Desktop
    st.image(renderizar_imagen(datos, scale=SCALE_PREVIEW, color_borde=color_borde, mostrar_guias=mostrar_guias), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True) # Fin desktop only

    st.write("---")

    # --- FLUJO DE PASOS ---

    if es_valido_vertical:
        # PASO 1: DISEÑO
        if st.session_state.step == 'diseño':
            if st.button("✅ CONFIRMAR DISEÑO", use_container_width=True, type="primary"):
                st.session_state.step = 'datos'
                st.rerun()

        # PASO 2: DATOS
        elif st.session_state.step == 'datos':
            st.info("🔒 Diseño bloqueado.")
            with st.form("form_datos"):
                st.write("Tus Datos:")
                c_nom, c_wpp = st.columns(2)
                with c_nom: nom = st.text_input("Nombre Completo")
                with c_wpp: wpp = st.text_input("WhatsApp (con cód. área)")
                ir_pago = st.form_submit_button("💳 IR A PAGAR")

            if st.button("⬅️ Editar Diseño"):
                st.session_state.step = 'diseño'
                st.rerun()

            if ir_pago:
                if not nom or not wpp: st.toast("Completa todos los datos", icon="⚠️")
                else:
                    st.session_state.cliente_nombre = nom
                    st.session_state.cliente_wpp = wpp
                    link = crear_preferencia_pago(nom, st.session_state.pedido_id)
                    if link:
                        st.session_state.link_pago = link
                        st.session_state.step = 'pago'
                        st.rerun()

        # PASO 3: PAGO
        elif st.session_state.step == 'pago':
            st.success(f"¡Hola {st.session_state.cliente_nombre}!")
            st.markdown(f"**Total a pagar: ${PRECIO_SELLO}**")
            st.link_button("👉 PAGAR EN MERCADO PAGO", st.session_state.link_pago, type="primary", use_container_width=True)

            st.write("")
            st.caption("Una vez realizado el pago, presiona el botón de abajo:")

            if st.button("🔄 VERIFICAR PAGO Y ENVIAR", use_container_width=True):
                with st.spinner("Verificando..."):
                    pago_id = verificar_pago_mp(st.session_state.pedido_id)
                    if pago_id:
                        st.success("✅ ¡Pago Confirmado!")
                        pdf_bytes, f_name = generar_pdf_hibrido(datos, st.session_state.cliente_nombre, incluir_guias_hd=mostrar_guias)
                        ok = enviar_email(pdf_bytes, f_name, st.session_state.cliente_nombre, st.session_state.cliente_wpp, pago_id)
                        if ok:
                            st.balloons()
                            st.success("📩 ¡Enviado!")
                            if st.button("Hacer otro pedido"):
                                st.session_state.step = 'diseño'
                                st.session_state.pedido_id = str(uuid.uuid4())
                                st.rerun()
                    else: st.error("❌ Pago no encontrado.")

            if st.button("⬅️ Atrás"):
                st.session_state.step = 'datos'
                st.rerun()