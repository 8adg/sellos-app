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
import tempfile

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

# --- MOTOR GRÁFICO UNIFICADO (PILLOW) ---
def renderizar_imagen_sello(datos_lineas, scale_factor=20, dibujar_borde=True, color_borde="black"):
    """
    Genera la imagen del sello. 
    Usamos esta MISMA función para la preview (baja res) y para el PDF (alta res).
    """
    w_px = int(ANCHO_REAL_MM * scale_factor)
    h_px = int(ALTO_REAL_MM * scale_factor)
    
    # Fondo blanco (CMYK friendly si fuera necesario, pero RGB ok para esto)
    img = Image.new('RGB', (w_px, h_px), "white")
    draw = ImageDraw.Draw(img)
    
    if dibujar_borde:
        draw.rectangle([(0,0), (w_px-1, h_px-1)], outline=color_borde, width=int(scale_factor/5))
    
    # Calcular altura total para centrado
    total_h_px = 0
    for linea in datos_lineas:
        size_pt = linea['size']
        size_px = size_pt * FACTOR_PT_A_MM * scale_factor
        total_h_px += size_px

    y_cursor_base = (h_px - total_h_px) / 2

    for linea in datos_lineas:
        txt = linea['texto']
        f_path = linea['fuente']
        sz_pt = linea['size']
        offset_mm = linea['offset_y']
        
        sz_px = int(sz_pt * FACTOR_PT_A_MM * scale_factor)
        offset_px = int(offset_mm * scale_factor)
        
        try:
            if f_path == "Arial": raise Exception
            font = ImageFont.truetype(f_path, sz_px)
        except: font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), txt, font=font)
        text_w = bbox[2] - bbox[0]
        x_pos = (w_px - text_w) / 2
        
        # Dibujamos en: Posición Base + Offset Manual
        # Pillow dibuja desde Top-Left
        draw.text((x_pos, y_cursor_base + offset_px), txt, font=font, fill="black")
        
        y_cursor_base += sz_px
    
    return img

def generar_pdf_final(datos_lineas, cliente):
    # 1. Generamos la imagen a MUY ALTA resolución (Escala 40 = ~1000 DPI)
    # Sin borde para impresión
    img_alta_res = renderizar_imagen_sello(datos_lineas, scale_factor=40, dibujar_borde=False)
    
    # 2. Guardamos la imagen en un archivo temporal
    temp_img_path = f"temp_{datetime.now().strftime('%H%M%S%f')}.jpg"
    img_alta_res.save(temp_img_path, quality=100, subsampling=0)
    
    # 3. Creamos el PDF y pegamos la imagen ocupando todo el espacio
    pdf = FPDF(orientation='P', unit='mm', format=(ANCHO_REAL_MM, ALTO_REAL_MM))
    pdf.add_page()
    pdf.set_margins(0,0,0)
    pdf.set_auto_page_break(False, margin=0)
    
    # Pegar imagen en (0,0) con el ancho y alto total del sello
    pdf.image(temp_img_path, x=0, y=0, w=ANCHO_REAL_MM, h=ALTO_REAL_MM)
    
    # Limpieza
    try: os.remove(temp_img_path)
    except: pass

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

    # PREVIEW (Escala 20, con borde)
    img_preview = renderizar_imagen_sello(datos, scale_factor=20, dibujar_borde=True, color_borde="black")
    st.image(img_preview, use_container_width=True)
    
    st.caption("Usa **Pos. Y** para subir (-) o bajar (+) cada línea.")
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