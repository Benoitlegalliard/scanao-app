import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import time
import re
import requests
import tempfile
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="ScanAO", page_icon="🔍", layout="wide")

# --- LOGO LOCAL ---
# On utilise le fichier logo.png présent sur ton Mac/GitHub
LOGO_PATH = "logo.png"

# --- CSS (INTERFACE WEB D'ORIGINE) ---
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0f172a !important; font-family: 'Inter', sans-serif; }
    .main-title { font-size: 3rem; color: #0284c7 !important; margin: 0; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; margin-top: -5px; }
    
    .intro-box {
        background-color: #e0f2fe; padding: 15px; border-radius: 8px;
        border-left: 5px solid #0284c7; color: #0369a1; margin-bottom: 20px;
    }

    div.stButton > button {
        background-color: #0284c7; color: white; border-radius: 8px;
        padding: 12px; font-weight: 600; border: none; width: 100%;
        transition: 0.2s;
    }
    div.stButton > button:hover { background-color: #0369a1; }

    .result-card, .result-card * {
        color: #1e293b !important; 
        line-height: 1.6;
    }

    .result-card h2 {
        color: #0284c7 !important;
        font-size: 1.4rem; 
        border-bottom: 2px solid #f1f5f9;
        padding-bottom: 10px; margin-top: 30px;
    }
    
    .result-card strong { color: #0f172a !important; font-weight: 800; }

    .score-badge {
        display: inline-block; padding: 8px 16px; border-radius: 20px;
        font-weight: 800; font-size: 1.2rem; margin-bottom: 20px; border: 2px solid;
    }
    .score-green { background-color: #dcfce7; color: #166534; border-color: #166534; }
    .score-orange { background-color: #ffedd5; color: #9a3412; border-color: #9a3412; }
    .score-red { background-color: #fee2e2; color: #991b1b; border-color: #991b1b; }

    [data-testid='stFileUploader'] { background-color: white; border: 2px dashed #cbd5e1; padding: 20px; }
    [data-testid='stFileUploader'] div { color: #475569 !important; }
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
            if os.path.exists(LOGO_PATH):
                self.image(LOGO_PATH, 10, 8, 20)
            self.set_font('Arial', 'B', 20)
            self.set_text_color(2, 132, 199)
            self.cell(0, 10, 'Rapport ScanAO', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 12)
    
    if score_val >= 7: r, g, b = 220, 252, 231; tr, tg, tb = 22, 101, 52
    elif score_val <= 4: r, g, b = 254, 226, 226; tr, tg, tb = 153, 27, 27
    else: r, g, b = 255, 237, 213; tr, tg, tb = 154, 52, 18

    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(tr, tg, tb)
    pdf.cell(0, 12, f"  SCORE IA : {final_score}  ", 0, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    for line in clean_text.split('\n'):
        line = line.strip()
        if not line: pdf.ln(2); continue
        if line.startswith("##"):
            pdf.ln(5); pdf.set_font("Arial", 'B', 14); pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", size=10)
        else:
            pdf.multi_cell(0, 5, line.replace("**", ""))
    return pdf.output(dest='S').encode('latin-1')

def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    # On remet le modèle 2.5-flash comme tu l'as demandé
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0})
    prompt = """
    Tu es un Expert Analyse DCE BTP. 
    Mission : Analyse complète (Synthese, Lot, Finances, Planning, Technique).
    Algorithme Score : Base 10. Malus: Public(-1), Réno(-1), Visite(-0.5). Bonus: Avance(+0.5).
    """
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- UI ---
col1, col2 = st.columns([1,5])
with col1:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=90)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation.</div>', unsafe_allow_html=True)

api_key = st.secrets.get("GEMINI_API_KEY")

uploaded_files = st.file_uploader("Dossier de consultation (PDF)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"SCANNER ({len(uploaded_files)} fichiers) 🚀"):
        if not api_key: st.error("Clé API manquante")
        else:
            with st.spinner("Analyse en cours..."):
                full_text = ""
                for pdf in uploaded_files:
                    full_text += extract_text_from_pdf(pdf)
                try:
                    res_text = analyze_document(api_key, full_text)
                    score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
                    val = float(score_match.group(1).replace(',', '.')) if score_match else 0
                    
                    st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
                    pdf_bytes = create_pdf(res_text, f"{val}/10", val)
                    st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF", pdf_bytes, "Rapport_ScanAO.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Erreur : {e}")
