import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import time
import re
import os

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="ScanAO", page_icon="🏗️", layout="wide")

# --- RÉCUPÉRATION DE LA CLÉ API ---
api_key = st.secrets.get("GEMINI_API_KEY")

# --- CSS : NETTOYAGE TOTAL INTERFACE ---
st.markdown("""
<style>
    /* Cache les éléments inutiles */
    #MainMenu, footer, header {visibility: hidden;}
    .stApp { background-color: #f8f9fa; }
    
    /* Titres */
    .main-title { font-size: 3rem; color: #0284c7 !important; margin-bottom: 0; font-weight: 700; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; margin-top: -10px; margin-bottom: 20px;}

    /* --- ZONE D'UPLOAD ÉPURÉE (SANS BOUTON ANGLAIS) --- */
    [data-testid='stFileUploader'] section {
        background-color: white !important;
        border: 2px dashed #0284c7 !important;
        padding: 50px !important;
        border-radius: 12px;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
    }
    
    /* Masque tout le contenu par défaut de Streamlit dans la zone */
    [data-testid='stFileUploader'] section > div {
        display: none !important;
    }

    /* Ajoute notre propre texte en Français au milieu */
    [data-testid='stFileUploader'] section::before {
        content: "📂 Cliquez ou glissez vos fichiers PDF ici pour lancer l'analyse";
        color: #0284c7 !important;
        font-weight: bold;
        font-size: 1.3rem;
        text-align: center;
        cursor: pointer;
    }

    /* Bouton Lancer l'analyse */
    div.stButton > button {
        background-color: #0284c7; color: white; border-radius: 8px;
        padding: 15px; font-weight: 600; border: none; width: 100%;
        transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #0369a1; transform: translateY(-1px); }

    /* Carte de résultat */
    .result-card {
        background-color: white; padding: 30px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); color: #1e293b;
    }
</style>
""", unsafe_allow_html=True)

# --- CLASSE PDF CORRIGÉE (LOGO + MARGES) ---
class ScanAOPDF(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            # Positionne le logo à gauche
            self.image("logo.png", 10, 8, 25)
        
        self.set_font('Arial', 'B', 16)
        self.set_text_color(2, 132, 199)
        self.cell(0, 10, 'RAPPORT D\'ANALYSE SCANAO', 0, 1, 'R')
        self.ln(15) # Espace crucial pour ne pas chevaucher le texte

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(text_content, final_score, score_val):
    pdf = ScanAOPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Affichage du Score en haut
    pdf.set_font("Arial", 'B', 12)
    if score_val >= 7:
        r, g, b = 220, 252, 231; tr, tg, tb = 22, 101, 52
    elif score_val <= 4:
        r, g, b = 254, 226, 226; tr, tg, tb = 153, 27, 27
    else:
        r, g, b = 255, 237, 213; tr, tg, tb = 154, 52, 18

    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(tr, tg, tb)
    pdf.cell(0, 12, f" SCORE GLOBAL : {final_score} ", 0, 1, 'C', fill=True)
    pdf.ln(5)

    # Contenu du rapport
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    
    # Nettoyage emojis pour éviter les bugs PDF
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    
    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
        
        if line.startswith("##"):
            pdf.ln(4)
            pdf.set_font("Arial", 'B', 12)
            pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=10)
        else:
            pdf.multi_cell(0, 6, line.replace("**", ""))
            
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIQUE D'ANALYSE ---
def analyze_document(text):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') # Version stable et rapide
    prompt = "Tu es un expert en BTP. Analyse ce DCE et structure ton rapport avec un score IA (SCORE_IA: X/10), une description du projet, les finances, le planning et les points techniques."
    response = model.generate_content(f"{prompt}\n\nCONTENU DU DOC :\n{text}")
    return response.text

# --- AFFICHAGE ---
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation</div>', unsafe_allow_html=True)

if not api_key:
    st.error("Configuration incomplète : Clé API manquante.")
    st.stop()

files = st.file_uploader("", type=["pdf"], accept_multiple_files=True)

if files:
    if st.button(f"LANCER L'ANALYSE DE {len(files)} FICHIER(S)"):
        with st.spinner("Analyse en cours..."):
            all_text = ""
            for f in files:
                reader = PdfReader(f)
                for page in reader.pages:
                    all_text += page.extract_text() + "\n"
            
            res_text = analyze_document(all_text)
            
            # Extraction score pour le design
            score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
            val = 0
            if score_match:
                val = float(score_match.group(1).replace(',', '.'))
            
            st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
            
            pdf_data = create_pdf(res_text, f"{val}/10", val)
            st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF PRO", pdf_data, "Rapport_ScanAO.pdf", "application/pdf")
