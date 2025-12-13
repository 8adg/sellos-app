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

# --- DATOS DE EJEMPLO ---
EJEMPLO_INICIAL = [
    {"texto": "Juan Pérez", "font_idx": 2, "size": 16, "offset": -1.5},      
    {"texto": "DISEÑADOR GRÁFICO", "font_idx": 5, "size": 8, "offset": 0.0}, 
    {"texto": "Matrícula N° 2040", "font_idx": 4, "size": 7, "offset": 0.0}  
]

# --- 🎨 ESTILOS CSS ---
st.markdown("""
<style>
    .stApp { background-color: #222; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border: 1px solid #ddd;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        padding: 15px;
    }
    [data-testid="stVerticalBlockBorderWrapper"] label, p, h1, h2, h3 {
        color: #212529 !important;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        color: #212529 !important;
        background-color: #DADADA !important;
        border-color: #666;
    }
    [data-baseweb="select"] svg { fill: #212529 !important; }
    div[data-testid="stForm"] button {
        background-color: #000000;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        border: 2px solid transparent;
        transition: 0.3s;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #333333;
        border-color: #000000;
        color: #ffffff;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
c_logo, c_title = st.columns([0.15, 1.95])
with c_logo:
    if os.path.exists("assets/logo.svg"): st.image("assets/logo.svg", width=80)
    elif os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=80)
with c_title:
    st.title("Editor de Sellos Automáticos")
    st.markdown("Diseña tu **Queselló!** en tiempo real. Tamaño: **36x15 mm**.")
st.write("---")

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
SCALE = 20 

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

# --- GENERADORES ---
def generar_preview_imagen(datos_lineas, color_borde="black"):
    w_px = int(ANCHO_REAL_MM * SCALE)
    h_px = int(ALTO_REAL_MM * SCALE)
    img = Image.new('RGB', (w_px, h_px), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0), (w_px-1, h_px-1)], outline=color_borde, width=4 if color_borde=="red" else 1)
    
    # Calcular altura total para centrado
    total_h_px = 0
    for linea in datos_lineas:
        size_pt = linea['size']
        size_px = size_pt * FACTOR_PT_A_MM * SCALE
        total_h_px += size_px

    y_cursor_base = (h_px - total_h_px) / 2

    for linea in datos_lineas:
        txt = linea['texto']
        f_path = linea['fuente']
        sz_pt = linea['size']
        offset_mm = linea['offset_y']
        
        sz_px = int(sz_pt * FACTOR_PT_A_MM * SCALE)
        offset_px = int(offset_mm * SCALE)
        
        try:
            if f_path == "Arial": raise Exception
            font = ImageFont.truetype(f_path, sz_px)
        except: font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), txt, font=font)
        text_w = bbox[2] - bbox[0]
        x_pos = (w_px - text_w) / 2 
        
        # En Pillow: Y es la parte SUPERIOR de la letra
        draw.text((x_pos, y_cursor_base + offset_px), txt, font=font, fill="black")
        
        y_cursor_base += sz_px
    return img

def generar_pdf_final(datos_lineas, cliente):
    # PDF Config
    pdf = FPDF(orientation='P', unit='mm', format=(ANCHO_REAL_MM, ALTO_REAL_MM))
    pdf.add_page()
    pdf.set_margins(0,0,0)
    pdf.set_auto_page_break(False, margin=0) # CRÍTICO: Desactivar salto de página automático
    
    # Cargar fuentes
    font_map = {} # Mapeo de Ruta -> NombreFamilia
    font_counter = 1
    
    for ruta in FUENTES_DISPONIBLES.values():
        if ruta != "Arial" and os.path.exists(ruta):
            # Usamos un nombre simple e interno para evitar líos con espacios
            family_name = f"CustomFont{font_counter}"
            try:
                pdf.add_font(family_name, "", ruta)
                font_map[ruta] = family_name
                font_counter += 1
            except: pass

    # Calcular posición Y inicial (Centrado)
    h_total_mm = sum([l['size'] * FACTOR_PT_A_MM for l in datos_lineas])
    y_base = (ALTO_REAL_MM - h_total_mm) / 2
    
    for l in datos_lineas:
        # Configurar fuente
        ruta = l['fuente']
        fam = font_map.get(ruta, "Arial")
        pdf.set_font(fam, size=l['size'])
        
        # Calcular posición Y del texto
        # En FPDF 'text()', la coordenada Y es la LÍNEA BASE.
        # En Pillow, la coordenada Y es la PARTE SUPERIOR.
        # Factor de corrección: ~0.78 del tamaño de la fuente suele ser la altura desde top a baseline.
        correction_baseline = (l['size'] * FACTOR_PT_A_MM) * 0.78
        
        # Posición Y final = Base + Offset Manual + Corrección Baseline
        y_final = y_base + l['offset_y'] + correction_baseline
        
        # Centrado Horizontal Manual
        # Calculamos ancho del texto
        txt_width = pdf.get_string_width(l['texto'])
        x_centered = (ANCHO_REAL_MM - txt_width) / 2
        
        try: txt_safe = l['texto'].encode('latin-1', 'replace').decode('latin-1')
        except: txt_safe = l['texto']
        
        # DIBUJO DIRECTO DE TEXTO (No usamos Cell para evitar saltos de página locos)
        pdf.text(x_centered, y_final, txt_safe)
        
        # Avanzamos el cursor base por la altura de esta línea
        y_base += (l['size'] * FACTOR_PT_A_MM)

    fname = f"{cliente.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}.pdf"
    return bytes(pdf.output()), fname

def enviar_email(pdf_bytes, nombre_pdf, cliente, email_cliente):
    try:
        remitente = st.secrets["email"]["usuario"]
        password = st.secrets["email"]["password"]
        destinatario = st.secrets["email"]["destinatario"]

        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = f"Pedido Quesello: {cliente}"
        cuerpo = f"Cliente: {cliente}\nEmail: {email_cliente}\nFecha: {datetime.now()}"
        msg.attach(MIMEText(cuerpo, 'plain'))

        part = MIMEBase('application', "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{nombre_pdf}"')
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error Email: {e}")
        return False

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
            with c4: offset = st.number_input(f"o{i}", -10.0, 10.0, value=def_off, step=0.5, key=f"oi{i}", label_visibility="collapsed")
            
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
es_valido_vertical = True 

# --- COLUMNA DERECHA ---
with col_der:
    st.subheader("👁️ Vista Previa")
    
    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Altura Texto", f"{altura_total_usada_mm:.1f} mm")
        m2.metric("Sello", f"{ALTO_REAL_MM} mm", delta_color="normal")

    img_preview = generar_preview_imagen(datos, "black")
    st.image(img_preview, use_container_width=True)
    
    st.caption("Usa **Pos. Y** para ajustar la altura manualmente.")
    st.write("---")
    
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
                pdf_bytes, f_name = generar_pdf_final(datos, nom)
                enviado = enviar_email(pdf_bytes, f_name, nom, mail)
                if enviado:
                    st.balloons()
                    st.success(f"¡Pedido de {nom} enviado!")