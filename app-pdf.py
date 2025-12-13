import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageColor
import os
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import uuid
import mercadopago

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Queselló! - Editor",
    page_icon="assets/logo.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CONFIGURACIÓN COMERCIAL ---
PRECIO_SELLO = 20500
MP_ACCESS_TOKEN = st.secrets["mercadopago"]["access_token"]
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- 3. ESTILOS CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        padding: 20px;
    }
    label, p, h1, h2, h3, div { color: #333333 !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        color: #212529 !important;
        background-color: #ffffff !important;
        border: 1px solid #ced4da;
    }
    [data-baseweb="select"] svg { fill: #212529 !important; }

    /* Botón Confirmar Diseño */
    button[kind="secondary"] {
        background-color: #000000 !important;
        color: white !important;
        font-weight: bold !important;
    }

    /* Botón Pagar */
    .btn-pagar {
        background-color: #009EE3 !important;
        color: white !important;
        font-weight: bold;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        text-decoration: none;
        display: block;
    }

    /* Botón Verificar */
    div[data-testid="stForm"] button {
        background-color: #28a745;
        color: white !important;
        font-weight: bold;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. CONFIGURACIÓN DEL DISEÑO (Valores del Calibrador)
# ==============================================================================
MODO_BLENDING = 'lighten'
OPACIDAD_TRAMA = 1.0
MARGEN_IZQ_TRAMA = 227
OFFSET_TRAMA_Y = 10

MARGEN_IZQ = 230
MARGEN_DER = 50
MIN_Y_FECHA = 110
POSICION_Y_SIDEBAR = 900

SIZE_TITULO = 65
SIZE_FECHA = 60
SIZE_CAT = 30
SIZE_INFO = 35
SIZE_SIDEBAR = 50

SALTO_CATEGORIA = 45
SALTO_TITULO_LINEA = 70
MARGIN_POST_TITULO = 15
SALTO_INFO = 45
SALTO_INFO_CUANDO = 35

CFG_COMFORT = {
    "ESPACIO_ENTRE_EVENTOS": 90, "DISTANCIA_LINEA_EVENTOS": 60, "DISTANCIA_FECHA_LINEA": 80,
    "MARGEN_INFERIOR_CANVAS": 100, "OFFSET_TRAMA": 10
}

CFG_COMPACT = {
    "ESPACIO_ENTRE_EVENTOS": 65, "DISTANCIA_LINEA_EVENTOS": 50, "DISTANCIA_FECHA_LINEA": 70,
    "MARGEN_INFERIOR_CANVAS": 85, "OFFSET_TRAMA": 125
}

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

FACTOR_PT_A_MM = 0.3527
ANCHO_REAL_MM = 36
ALTO_REAL_MM = 15
SCALE_PREVIEW = 20
SCALE_HD = 80

# --- 5. HELPERS Y MOTORES ---

def obtener_ascent_mm(ruta_fuente, size_pt):
    scale_calc = 100
    size_px = int(size_pt * FACTOR_PT_A_MM * scale_calc)
    try:
        if ruta_fuente == "Arial" or not os.path.exists(ruta_fuente): return (size_pt * FACTOR_PT_A_MM) * 0.8
        font = ImageFont.truetype(ruta_fuente, size_px)
        ascent, _ = font.getmetrics()
        return ascent / scale_calc
    except: return (size_pt * FACTOR_PT_A_MM) * 0.8

def renderizar_imagen(datos_lineas, scale, dibujar_borde=True, color_borde="black", mostrar_guias=False):
    w_px, h_px = int(ANCHO_REAL_MM * scale), int(ALTO_REAL_MM * scale)
    img = Image.new('RGB', (w_px, h_px), "white")
    draw = ImageDraw.Draw(img)
    if dibujar_borde:
        g = 4 if color_borde == "red" else max(2, int(scale/5))
        draw.rectangle([(0,0), (w_px-1, h_px-1)], outline=color_borde, width=g)

    total_h_px = sum([l['size'] * FACTOR_PT_A_MM * scale for l in datos_lineas])
    y_cursor = (h_px - total_h_px) / 2

    for i, l in enumerate(datos_lineas):
        try:
            if l['fuente'] == "Arial": font = ImageFont.load_default()
            else: font = ImageFont.truetype(l['fuente'], int(l['size'] * FACTOR_PT_A_MM * scale))
        except: font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), l['texto'], font=font)
        draw.text(((w_px - (bbox[2]-bbox[0]))/2, y_cursor + (l['offset_y']*scale)), l['texto'], font=font, fill="black")

        if mostrar_guias:
            ascent, _ = font.getmetrics()
            y_base_px = y_cursor + (l['offset_y']*scale) + ascent
            draw.line([(0, y_base_px), (w_px, y_base_px)], fill=(0, 150, 255), width=max(1, int(scale/20)))
            # Cota legible
            try: f_cota = ImageFont.truetype("assets/fonts/Roboto-Regular.ttf", int(scale * 1.2))
            except: f_cota = ImageFont.load_default()
            draw.text((scale, y_base_px - (scale*1.2)), f"L{i+1}:{y_base_px/scale:.1f}mm", font=f_cota, fill=(0,150,255))

        y_cursor += (l['size'] * FACTOR_PT_A_MM * scale)
    return img

def generar_pdf_hibrido(datos_lineas, cliente, incluir_guias=False):
    pdf = FPDF('P', 'mm', (ANCHO_REAL_MM, ALTO_REAL_MM))
    # Pag 1: Vector
    pdf.add_page(); pdf.set_margins(0,0,0); pdf.set_auto_page_break(False, 0)
    font_map = {}; cnt = 1
    for r in FUENTES_DISPONIBLES.values():
        if r != "Arial" and os.path.exists(r):
            fam = f"F{cnt}"; pdf.add_font(fam, "", r); font_map[r] = fam; cnt += 1

    h_total = sum([l['size'] * FACTOR_PT_A_MM for l in datos_lineas])
    y_base = (ALTO_REAL_MM - h_total) / 2
    for l in datos_lineas:
        pdf.set_font(font_map.get(l['fuente'], "Arial"), size=l['size'])
        txt_w = pdf.get_string_width(l['texto'])
        y_final = y_base + l['offset_y'] + obtener_ascent_mm(l['fuente'], l['size'])
        try: t = l['texto'].encode('latin-1', 'replace').decode('latin-1')
        except: t = l['texto']
        pdf.text((ANCHO_REAL_MM - txt_w)/2, y_final, t)
        y_base += (l['size'] * FACTOR_PT_A_MM)

    # Pag 2: HD
    pdf.add_page()
    img = renderizar_imagen(datos_lineas, SCALE_HD, False, mostrar_guias=incluir_guias)
    tmp = f"temp_{uuid.uuid4()}.jpg"
    img.save(tmp, quality=100); pdf.image(tmp, 0, 0, ANCHO_REAL_MM, ALTO_REAL_MM)
    if os.path.exists(tmp): os.remove(tmp)
    return bytes(pdf.output()), f"{cliente.replace(' ','_')}_{datetime.now().strftime('%H%M')}.pdf"

def enviar_email(pdf_bytes, nombre_pdf, cliente, whatsapp, id_pago):
    try:
        remitente = st.secrets["email"]["usuario"]
        destinatario = st.secrets["email"]["destinatario"]
        msg = MIMEMultipart()
        msg['From'] = remitente; msg['To'] = destinatario; msg['Subject'] = f"PAGADO - Pedido Quesello: {cliente}"
        cuerpo = f"Nuevo pedido de sello pagado.\n\nCliente: {cliente}\nWhatsApp: {whatsapp}\nID Pago: {id_pago}"
        msg.attach(MIMEText(cuerpo, 'plain'))
        part = MIMEBase('application', "octet-stream")
        part.set_payload(pdf_bytes); encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{nombre_pdf}"')
        msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(); server.login(remitente, st.secrets["email"]["password"])
        server.sendmail(remitente, destinatario, msg.as_string()); server.quit()
        return True
    except Exception as e: st.error(f"Error Email: {e}"); return False

# --- 6. MERCADO PAGO ---
def crear_preferencia(nom, ref):
    pref = {"items": [{"title": f"Sello Quesello - {nom}", "quantity": 1, "unit_price": PRECIO_SELLO, "currency_id": "ARS"}],
            "external_reference": ref, "auto_return": "approved", "back_urls": {"success": "https://www.google.com"}}
    try: return mp_sdk.preference().create(pref)["response"]["init_point"]
    except: return None

def verificar_pago(ref):
    try:
        res = mp_sdk.payment().search({"external_reference": ref, "status": "approved"})
        return res["response"]["results"][0]["id"] if res["response"]["results"] else None
    except: return None

# --- 7. INTERFAZ ---

# Inicializar estados si no existen
if 'pedido_id' not in st.session_state: st.session_state.pedido_id = str(uuid.uuid4())
if 'paso' not in st.session_state: st.session_state.paso = 1
if 'form_visible' not in st.session_state: st.session_state.form_visible = False

col_izq, _, col_der = st.columns([1, 0.05, 1])

with col_izq:
    st.subheader("🛠️ Configuración")
    bloqueado = st.session_state.paso == 2
    cant = st.selectbox("Líneas", [1,2,3,4], index=2, disabled=bloqueado)
    st.write("")

    c_h = st.columns([3, 2, 1.5, 1.5])
    c_h[0].caption("Texto"); c_h[1].caption("Fuente"); c_h[2].caption("Tamaño"); c_h[3].caption("Pos. Y")

    datos_live = []
    for i in range(cant):
        def_t = EJEMPLO_INICIAL[i]["texto"] if i < len(EJEMPLO_INICIAL) else ""
        def_f = EJEMPLO_INICIAL[i]["font_idx"] if i < len(EJEMPLO_INICIAL) else 0
        def_s = EJEMPLO_INICIAL[i]["size"] if i < len(EJEMPLO_INICIAL) else 9
        def_o = EJEMPLO_INICIAL[i].get("offset", 0.0) if i < len(EJEMPLO_INICIAL) else 0.0

        with st.container(border=True):
            c = st.columns([3, 2, 1.5, 1.5])
            t = c[0].text_input(f"t{i}", value=def_t, key=f"ti{i}", label_visibility="collapsed", disabled=bloqueado)
            f_k = c[1].selectbox(f"f{i}", list(FUENTES_DISPONIBLES.keys()), index=def_f, key=f"fi{i}", label_visibility="collapsed", disabled=bloqueado)
            sz_s = c[2].slider(f"s{i}", 6, 26, value=def_s, key=f"si{i}", label_visibility="collapsed", disabled=bloqueado)
            off_s = c[3].slider(f"o{i}", -10.0, 10.0, value=float(def_o), step=0.5, key=f"oi{i}", label_visibility="collapsed", disabled=bloqueado)

            datos_live.append({"texto": t, "fuente": FUENTES_DISPONIBLES[f_k], "size": sz_s, "offset_y": off_s})

with col_der:
    st.subheader("👁️ Vista Previa")
    h_usada = sum([d['size'] * FACTOR_PT_A_MM for d in datos_live])
    valido = (ALTO_REAL_MM - h_usada) >= -1.0

    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Altura", f"{h_usada:.1f}mm")
        m2.metric("Límite", "15.0mm")
        guias = st.checkbox("📏 Mostrar Guías", value=False, disabled=bloqueado)

    if not valido: st.error("⛔ EXCESO DE ALTURA")

    img = renderizar_imagen(datos_live, SCALE_PREVIEW, color_borde="black" if valido else "red", mostrar_guias=guias)
    st.image(img, use_container_width=True)
    st.write("---")

    if valido:
        if st.session_state.paso == 1:
            # --- NUEVA LÓGICA DE BOTÓN DESPLEGABLE ---
            if not st.session_state.form_visible:
                if st.button("✅ CONFIRMAR DISEÑO", use_container_width=True):
                    st.session_state.form_visible = True
                    st.rerun()
            else:
                st.markdown("### 👤 Datos de contacto")
                with st.form("datos"):
                    nom = st.text_input("Nombre y Apellido")
                    wpp = st.text_input("WhatsApp (ej: 2235203360)")
                    if st.form_submit_button("💳 IR A PAGAR"):
                        if not nom or not wpp: st.error("Completa los datos")
                        else:
                            st.session_state.nom = nom; st.session_state.wpp = wpp
                            link = crear_preferencia(nom, st.session_state.pedido_id)
                            if link:
                                st.session_state.link = link
                                st.session_state.paso = 2
                                st.rerun()
                if st.button("⬅️ Cancelar"):
                    st.session_state.form_visible = False
                    st.rerun()

        elif st.session_state.paso == 2:
            st.markdown(f"### 💳 2. Pago de ${PRECIO_SELLO}")
            st.link_button("👉 PAGAR EN MERCADO PAGO", st.session_state.link)
            st.write("---")
            if st.button("🔄 VERIFICAR PAGO Y ENVIAR", type="primary"):
                p_id = verificar_pago(st.session_state.pedido_id)
                if p_id:
                    st.success("✅ Pago Aprobado!")
                    pdf, name = generar_pdf_hibrido(datos_live, st.session_state.nom, guias)
                    if enviar_email(pdf, name, st.session_state.nom, st.session_state.wpp, p_id):
                        st.balloons(); st.success("📩 Pedido enviado!")
                else: st.error("❌ Pago no detectado todavía.")
            if st.button("⬅️ Volver a editar"):
                st.session_state.paso = 1; st.session_state.form_visible = False
                st.rerun()