import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import time
import re
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="ScanAO", page_icon="🏗️", layout="wide")

# --- RÉCUPÉRATION CLÉ API ---
api_key = st.secrets.get("GEMINI_API_KEY")

# --- CSS (INTERFACE WEB BLINDÉE) ---
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp { background-color: #f8f9fa; }
    
    /* Force le texte noir partout */
    .stApp, .stApp p, .stApp span, .stApp label { color: #1e293b !important; }
    
    .main-title { font-size: 3rem; color: #0284c7 !important; margin: 0; font-weight: 700; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; margin-top: -5px; }

    /* ZONE UPLOAD ÉPURÉE */
    [data-testid='stFileUploader'] section {
        background-color: white !important;
        border: 2px dashed #0284c7 !important;
        padding: 40px !important;
        border-radius: 12px;
    }
    /* Masquer le bouton "Browse files" et les textes anglais */
    [data-testid='stFileUploader'] section > div { display: none !important; }
    [data-testid='stFileUploader'] section::before {
        content: "📂 Cliquez ou glissez vos fichiers PDF ici pour lancer l'analyse";
        color: #0284c7 !important;
        font-weight: bold; font-size: 1.2rem; display: block; text-align: center;
    }

    div.stButton > button {
        background-color: #0284c7; color: white !important; border-radius: 8px;
        padding: 15px; font-weight: 600; border: none; width: 100%;
    }

    .result-card {
        background-color: white; padding: 30px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); color: #1e293b !important;
    }
    
    .score-badge {
        display: inline-block; padding: 8px 16px; border-radius: 20px;
        font-weight: 800; font-size: 1.2rem; margin-bottom: 20px; border: 2px solid;
    }
    .score-green { background-color: #dcfce7; color: #166534; border-color: #166534; }
    .score-orange { background-color: #ffedd5; color: #9a3412; border-color: #9a3412; }
    .score-red { background-color: #fee2e2; color: #991b1b; border-color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS ---
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text
    except: return ""

def create_pdf(text_content, final_score, score_val):
    class PDF(FPDF):
        def header(self):
            # Logo uniquement sur la première page pour éviter le chevauchement
            if self.page_no() == 1 and os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 25)
            
            self.set_font('Arial', 'B', 15)
            self.set_text_color(2, 132, 199)
            self.cell(0, 10, 'Rapport d\'Analyse ScanAO', 0, 1, 'R')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Score Badge dans le PDF
    pdf.set_font("Arial", 'B', 12)
    if score_val >= 7: r, g, b = 220, 252, 231; tr, tg, tb = 22, 101, 52
    elif score_val <= 4: r, g, b = 254, 226, 226; tr, tg, tb = 153, 27, 27
    else: r, g, b = 255, 237, 213; tr, tg, tb = 154, 52, 18

    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(tr, tg, tb)
    pdf.cell(0, 12, f" SCORE IA : {final_score} ", 0, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Contenu
    pdf.set_font("Arial", size=10)
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')

    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2); continue
        if line.startswith("##"):
            pdf.ln(5); pdf.set_font("Arial", 'B', 13); pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", size=10)
        else:
            pdf.multi_cell(0, 6, line.replace("**", ""))
            
    return pdf.output(dest='S').encode('latin-1')

def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"temperature": 0})
    prompt = """
    Tu es un Expert Analyse DCE BTP. Structure ton rapport ainsi :
    SCORE_IA: X/10
    ## 📝 DESCRIPTION DU PROJET
    ## 💶 1. FINANCES
    ## 🗓️ 2. PLANNING
    ## 🚨 3. TECHNIQUE
    
    Algorithme Score : Base 10. Malus: Public(-1), Réno(-1), Visite Obligatoire(-0.5), Pénalités >1000/j(-1). Bonus: Avance >10%(+0.5).
    """
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- UI ---
col1, col2 = st.columns([1,5])
with col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=100)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation.</div>', unsafe_allow_html=True)

if not api_key:
    st.error("Clé API manquante dans les Secrets Streamlit.")
    st.stop()

uploaded_files = st.file_uploader("", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"SCANNER ({len(uploaded_files)} fichiers) 🚀"):
        progress_bar = st.progress(0, text="Lecture...")
        full_text = ""
        for i, pdf in enumerate(uploaded_files):
            full_text += f"\n--- DOC: {pdf.name} ---\n" + extract_text_from_pdf(pdf)
            progress_bar.progress(int((i + 1) / len(uploaded_files) * 50))

        try:
            progress_bar.progress(60, text="Analyse IA...")
            res_text = analyze_document(api_key, full_text)
            progress_bar.progress(100)
            time.sleep(0.5); progress_bar.empty()
            
            score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text, re.IGNORECASE)
            val = float(score_match.group(1).replace(',', '.')) if score_match else 0
            
            badge_class = "score-green" if val >= 7 else "score-red" if val <= 4 else "score-orange"
            st.markdown(f'<div class="score-badge {badge_class}">GO/NOGO : {val}/10</div>', unsafe_allow_html=True)
            
            st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            pdf_bytes = create_pdf(res_text, f"{val}/10", val)
            st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF PRO", pdf_bytes, f"Rapport_ScanAO.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Erreur : {e}")
