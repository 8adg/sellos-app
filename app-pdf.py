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
    {"texto": "Matrícula N° 2040", "font_idx": 8, "size": 7, "offset": 0.0}
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
        font-size: 0.75rem;
        font-weight: normal;
        text-align: center;
        padding: 6px;
        color: #555 !important;
        line-height: 1.2;
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
.mobile-sticky-header {display:none;}
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
             display:block;
        }
        .mobile-sticky-header img {
            max-width: 90%; height: auto;
            border: 1px solid #ddd; border-radius: 4px;
        }
        .block-container { padding-top: 40vh !important; }
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

        # Guías (para HD)
        if mostrar_guias:
            color_guia = (0, 150, 255)
            grosor_guia = max(1, int(scale / 20))
            tamano_fuente_cota = int(8 * scale / 6)
            try: ascent, descent = font.getmetrics()
            except: ascent = sz_px * 0.8
            y_base_guia = y_visual_px + ascent
            draw.line([(0, y_base_guia), (w_px, y_base_guia)], fill=color_guia, width=grosor_guia)

            try: font_small = ImageFont.truetype("assets/fonts/Roboto-Regular.ttf", tamano_fuente_cota)
            except: font_small = font
            pos_mm_real = y_base_guia / scale
            label = f"{pos_mm_real:.1f}"

            draw.text((scale * 0.5, y_base_guia - tamano_fuente_cota), label, font=font_small, fill=color_guia)
            draw.rectangle([x_pos, y_visual_px, x_pos + text_w, y_visual_px + sz_px], outline=(200,200,200), width=0)

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
inputs_disabled = st.session_state.step != 'diseño'

# --- COLUMNA IZQUIERDA: CONFIGURACIÓN ---
with col_izq:
    st.subheader("🛠️ Configuración")

    cant = st.selectbox("Cantidad de líneas", [1,2,3,4], index=2, disabled=inputs_disabled)
    st.write("")

    datos = []

    for i in range(cant):
        # 1. Defaults
        key_offset = f"offset_state_{i}"
        if key_offset not in st.session_state:
            val_default = 0.0
            if i < len(EJEMPLO_INICIAL): val_default = float(EJEMPLO_INICIAL[i].get("offset", 0.0))
            st.session_state[key_offset] = val_default

        def_txt = ""; def_idx = 0; def_sz = 9
        if i < len(EJEMPLO_INICIAL):
            def_txt = EJEMPLO_INICIAL[i]["texto"]
            def_idx = EJEMPLO_INICIAL[i]["font_idx"]
            def_sz = max(8, EJEMPLO_INICIAL[i]["size"])

        # INICIO CARD
        with st.container(border=True):

            # FILA 1: Texto | Fuente
            c_top1, c_top2 = st.columns([0.65, 0.35])
            with c_top1:
                t = st.text_input(f"t{i}", value=def_txt, key=f"ti{i}", placeholder=f"Línea {i+1}", label_visibility="collapsed", disabled=inputs_disabled)
            with c_top2:
                f_key = st.selectbox(f"f{i}", list(FUENTES_DISPONIBLES.keys()), index=def_idx, key=f"fi{i}", label_visibility="collapsed", disabled=inputs_disabled)

            # FILA 2: Icono Sz | Stepper Sz | Icono Pos | BtnUp | BtnDown
            c_icon1, c_slid1, c_icon2, c_btn1, c_btn2 = st.columns([0.15, 0.35, 0.15, 0.17, 0.18], gap="small")

            with c_icon1: st.markdown('<div class="icon-label"><strong> Aᴀ </strong>TAMAÑO DE LETRA</div>', unsafe_allow_html=True)
            with c_slid1:
                slider_val = st.number_input(f"s{i}", min_value=8, max_value=26, value=def_sz, key=f"si{i}", label_visibility="collapsed", disabled=inputs_disabled)

            with c_icon2: st.markdown('<div class="icon-label"><strong> ↕ </strong> AJUSTE DE LINEA</div>', unsafe_allow_html=True)
            with c_btn1:
                st.button("▲", key=f"up_{i}", on_click=mover_arriba, args=(key_offset,), disabled=inputs_disabled, use_container_width=True)
            with c_btn2:
                st.button("▼", key=f"down_{i}", on_click=mover_abajo, args=(key_offset,), disabled=inputs_disabled, use_container_width=True)

            offset_actual = st.session_state[key_offset]
            ruta_fuente = FUENTES_DISPONIBLES[f_key]
            ancho_mm = calcular_ancho_texto_mm(t, ruta_fuente, slider_val)
            size_final = slider_val
            if ancho_mm > ANCHO_REAL_MM:
                size_final = int((slider_val * (ANCHO_REAL_MM / ancho_mm)) - 0.5)
                if size_final < 8: size_final = 8
                st.caption(f"⚠️ Ajustado a {size_final}pt")

            datos.append({"texto": t, "fuente": ruta_fuente, "size": size_final, "offset_y": offset_actual})

# CALCULO Y RENDER
altura_total_usada_mm = sum([d['size'] * FACTOR_PT_A_MM for d in datos])
es_valido_vertical = (ALTO_REAL_MM - altura_total_usada_mm) >= -1.0
color_borde = "red" if not es_valido_vertical else "black"

img_pil = renderizar_imagen(datos, scale=SCALE_PREVIEW, color_borde=color_borde, mostrar_guias=False)
img_b64 = pil_to_base64(img_pil)

# STICKY HEADER MOBILE
st.markdown(f"""
<div class="mobile-sticky-header">
    <div style="font-size:0.9rem; font-weight:bold; margin-bottom:5px;">Vista Previa</div>
    <img src="data:image/png;base64,{img_b64}" />
    <div style="font-size: 0.8rem; margin-top: 5px; color: {'red' if not es_valido_vertical else 'green'}">
        {altura_total_usada_mm:.1f}mm / 36mm
    </div>
</div>
""", unsafe_allow_html=True)

with col_der:
    st.markdown('<div class="desktop-only-col">', unsafe_allow_html=True)
    st.subheader("👁️ Vista Previa")
    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Altura Texto", f"{altura_total_usada_mm:.1f} mm")
        m2.metric("Sello", f"{ANCHO_REAL_MM} mm")
        mostrar_guias = st.checkbox("📏 Guías Técnicas", value=False, disabled=inputs_disabled)

    if not es_valido_vertical: st.error("⛔ EXCESO DE ALTURA")
    st.image(renderizar_imagen(datos, SCALE_PREVIEW, color_borde, mostrar_guias), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("---")

    if es_valido_vertical:
        if st.session_state.step == 'diseño':
            if st.button("✅ CONFIRMAR DISEÑO", use_container_width=True, type="primary"):
                st.session_state.step = 'datos'; st.rerun()

        elif st.session_state.step == 'datos':
            st.info("🔒 Diseño confirmado.Completá los datos y realizá el pago")
            with st.form("form_datos"):
                st.write("Tus Datos:")
                c_nom, c_wpp = st.columns(2)
                with c_nom: nom = st.text_input("Nombre Completo")
                with c_wpp: wpp = st.text_input("WhatsApp")
                ir_pago = st.form_submit_button("💳 IR A PAGAR")
            if st.button("⬅️ Editar"): st.session_state.step = 'diseño'; st.rerun()
            if ir_pago:
                if not nom or not wpp: st.toast("Faltan datos", icon="⚠️")
                else:
                    st.session_state.cliente_nombre = nom; st.session_state.cliente_wpp = wpp
                    link = crear_preferencia_pago(nom, st.session_state.pedido_id)
                    if link: st.session_state.link_pago = link; st.session_state.step = 'pago'; st.rerun()

        elif st.session_state.step == 'pago':
            st.success(f"Hola {st.session_state.cliente_nombre}!")
            st.link_button("👉 PAGAR EN MERCADO PAGO", st.session_state.link_pago, type="primary", use_container_width=True)
            st.write(""); st.caption("Una vez realizado el pago:")
            if st.button("🔄 VERIFICAR PAGO", use_container_width=True):
                with st.spinner("Verificando..."):
                    pid = verificar_pago_mp(st.session_state.pedido_id)
                    if pid:
                        st.success("✅ Pago Confirmado")
                        pdf, fname = generar_pdf_hibrido(datos, st.session_state.cliente_nombre, incluir_guias_hd=mostrar_guias)
                        if enviar_email(pdf, fname, st.session_state.cliente_nombre, st.session_state.cliente_wpp, pid):
                            st.balloons(); st.success("📩 ¡Enviado!")
                            if st.button("Nuevo"): st.session_state.step = 'diseño'; st.session_state.pedido_id = str(uuid.uuid4()); st.rerun()
                    else: st.error("Pago no encontrado")
            if st.button("⬅️ Atrás"): st.session_state.step = 'datos'; st.rerun()