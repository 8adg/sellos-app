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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Queselló! - Editor",
    page_icon="assets/logo.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

# --- DATOS DE EJEMPLO ---
EJEMPLO_INICIAL = [
    {"texto": "Juan Pérez", "font_idx": 2, "size": 16, "offset": -1.5},
    {"texto": "DISEÑADOR GRÁFICO", "font_idx": 5, "size": 8, "offset": 0.0},
    {"texto": "Matrícula N° 2040", "font_idx": 4, "size": 7, "offset": 0.0}
]

# --- CONSTANTES ---
FACTOR_PT_A_MM = 0.3527
ANCHO_REAL_MM = 36
ALTO_REAL_MM = 15
SCALE_PREVIEW = 20
SCALE_HD = 80

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stApp { background-color: #fafafa; }
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
    div[data-testid="stForm"] button {
        background-color: #28a745;
        color: white !important;
        font-weight: bold;
        border: none;
        border-radius: 6px;
        padding: 10px;
        transition: all 0.3s ease;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #218838;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(40, 167, 69, 0.3);
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
c_logo, c_title = st.columns([0.15, 0.85])
with c_logo:
    if os.path.exists("assets/logo.svg"): st.image("assets/logo.svg", width=90)
    elif os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=90)
with c_title:
    st.title("Editor de Sellos Automáticos")
    st.markdown("Diseña tu **Queselló!** en tiempo real. Área de impresión: **36x15 mm**.")
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

# --- MOTOR GRÁFICO (CON CORRECCIÓN DE LÍNEA BASE) ---
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

        # Posición Y final (Top-Left visual)
        y_final_px = y_cursor_base + offset_px

        # Dibujar Texto
        draw.text((x_pos, y_final_px), txt, font=font, fill="black")

        # --- DIBUJAR GUÍAS TÉCNICAS (CORREGIDAS) ---
        if mostrar_guias:
            color_guia = (0, 150, 255)
            grosor_guia = max(1, int(scale / 10))
            tamano_fuente_guia = int(8 * scale / 5)

            # --- CORRECCIÓN CLAVE ---
            # Obtenemos el "Ascent" (altura desde el techo hasta la línea base)
            ascent, descent = font.getmetrics()

            # La línea base REAL está en: Posición Y (Techo) + Ascent
            y_base_real = y_final_px + ascent

            # 1. Línea Base (Cyan) - AHORA SÍ EXACTA
            draw.line([(0, y_base_real), (w_px, y_base_real)], fill=color_guia, width=grosor_guia)

            # 2. Cota
            try: font_small = ImageFont.truetype("Arial", tamano_fuente_guia)
            except: font_small = ImageFont.load_default()

            pos_mm_real = y_base_real / scale
            label = f"L{i+1}: {pos_mm_real:.1f}mm"

            draw.text((grosor_guia * 2, y_base_real - tamano_fuente_guia), label, font=font_small, fill=color_guia)

            # 3. Caja delimitadora (Gris suave)
            # Esto muestra el área total de la fuente (incluyendo acentos y colas)
            draw.rectangle([x_pos, y_final_px, x_pos + text_w, y_final_px + sz_px], outline=(200,200,200), width=grosor_guia)

        # Avanzar cursor
        y_cursor_base += sz_px

    return img

# --- GENERADOR PDF HÍBRIDO ---
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

        altura_linea = l['size'] * FACTOR_PT_A_MM
        correction_baseline = altura_linea * 0.78
        y_final = y_base + l['offset_y'] + correction_baseline

        pdf.text(x_centered, y_final, txt)
        y_base += altura_linea

    # PÁG 2: IMAGEN HD
    pdf.add_page()
    img_hd = renderizar_imagen(datos_lineas, scale=SCALE_HD, dibujar_borde=False, mostrar_guias=incluir_guias_hd)
    temp_path = f"temp_{datetime.now().strftime('%f')}.jpg"
    img_hd.save(temp_path, quality=100, subsampling=0)
    pdf.image(temp_path, x=0, y=0, w=ANCHO_REAL_MM, h=ALTO_REAL_MM)
    if os.path.exists(temp_path): os.remove(temp_path)

    fname = f"{cliente.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}.pdf"
    return bytes(pdf.output()), fname

# --- EMAIL ---
def enviar_email(pdf_bytes, nombre_pdf, cliente, email_cliente):
    try:
        remitente = st.secrets["email"]["usuario"]
        password = st.secrets["email"]["password"]
        destinatario = st.secrets["email"]["destinatario"]

        msg = MIMEMultipart()
        msg['From'] = remitente; msg['To'] = destinatario; msg['Subject'] = f"Pedido Quesello: {cliente}"
        cuerpo = f"Cliente: {cliente}\nEmail: {email_cliente}\nFecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nAdjunto PDF Híbrido."
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

# --- INTERFAZ ---
col_izq, col_espacio, col_der = st.columns([1, 0.1, 1])

# --- COLUMNA IZQUIERDA ---
with col_izq:
    st.subheader("🛠️ Configuración")
    with st.container(border=True):
        cant = st.selectbox("Cantidad de líneas", [1,2,3,4], index=2)
    st.write("")

    c_h1, c_h2, c_h3, c_h4 = st.columns([3, 2, 1.5, 1.5])
    c_h1.markdown("**Texto**")
    c_h2.markdown("**Fuente**")
    c_h3.markdown("**Tamaño**")
    c_h4.markdown("**Pos. Y**")

    datos = []
    for i in range(cant):
        if i < len(EJEMPLO_INICIAL):
            def_txt = EJEMPLO_INICIAL[i]["texto"]
            def_idx = EJEMPLO_INICIAL[i]["font_idx"]
            def_sz = EJEMPLO_INICIAL[i]["size"]
            def_off = EJEMPLO_INICIAL[i].get("offset", 0.0)
        else:
            def_txt = ""; def_idx = 0; def_sz = 9; def_off = 0.0

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
            with c1: t = st.text_input(f"t{i}", value=def_txt, key=f"ti{i}", placeholder=f"Línea {i+1}", label_visibility="collapsed")
            with c2: f_key = st.selectbox(f"f{i}", list(FUENTES_DISPONIBLES.keys()), index=def_idx, key=f"fi{i}", label_visibility="collapsed")
            with c3: slider_val = st.slider(f"s{i}", 6, 26, value=def_sz, key=f"si{i}", label_visibility="collapsed")
            with c4: offset = st.slider(f"o{i}", -10.0, 10.0, value=float(def_off), step=0.5, key=f"oi{i}", label_visibility="collapsed")

            ruta_fuente = FUENTES_DISPONIBLES[f_key]
            ancho_actual_mm = calcular_ancho_texto_mm(t, ruta_fuente, slider_val)
            size_final = slider_val
            if ancho_actual_mm > ANCHO_REAL_MM:
                size_ajustado = (slider_val * (ANCHO_REAL_MM / ancho_actual_mm)) - 0.5
                size_final = int(size_ajustado)
                st.warning(f"Ajustado a {size_final}pt")

            datos.append({"texto": t, "fuente": ruta_fuente, "size": size_final, "offset_y": offset})

# --- CÁLCULO VERTICAL ---
altura_total_usada_mm = sum([d['size'] * FACTOR_PT_A_MM for d in datos])
es_valido_vertical = (ALTO_REAL_MM - altura_total_usada_mm) >= -1.0

# --- COLUMNA DERECHA ---
with col_der:
    st.subheader("👁️ Vista Previa")

    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Altura Texto", f"{altura_total_usada_mm:.1f} mm")
        m2.metric("Sello", f"{ALTO_REAL_MM} mm", delta_color="normal")
        mostrar_guias = st.checkbox("📏 Mostrar Guías Técnicas", value=False)

    if not es_valido_vertical:
        st.error("⛔ EXCESO DE ALTURA")
        color_borde = "red"
    else:
        color_borde = "black"

    img_preview = renderizar_imagen(datos, scale=SCALE_PREVIEW, color_borde=color_borde, mostrar_guias=mostrar_guias)
    st.image(img_preview, use_container_width=True)

    st.caption("Usa **Pos. Y** para mover verticalmente.")
    st.write("---")

    if es_valido_vertical:
        st.markdown("### ✅ Finalizar Pedido")
        with st.form("form_pedido", border=True):
            st.write("Datos de contacto:")
            c_nom, c_mail = st.columns(2)
            with c_nom: nom = st.text_input("Nombre")
            with c_mail: mail = st.text_input("Email")
            submitted = st.form_submit_button("💾 CONFIRMAR PEDIDO")

        if submitted:
            if not nom: st.toast("Falta nombre", icon="⚠️")
            else:
                with st.spinner("Procesando..."):
                    # Pasamos el estado de las guías al PDF
                    pdf_bytes, f_name = generar_pdf_hibrido(datos, nom, incluir_guias_hd=mostrar_guias)
                    enviado = enviar_email(pdf_bytes, f_name, nom, mail)
                    if enviado:
                        st.balloons()
                        st.success(f"¡Pedido de {nom} enviado!")