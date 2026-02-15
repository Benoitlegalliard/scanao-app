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

# --- CSS : BLINDAGE TOTAL (COULEURS + SUPPRESSION BOUTON) ---
st.markdown("""
<style>
    /* 1. Force le mode clair absolu et le texte noir */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #f8f9fa !important;
        color: #1e293b !important;
    }

    /* 2. Suppression des menus techniques */
    #MainMenu, footer, header {visibility: hidden !important;}
    
    /* 3. Style des titres */
    .main-title { font-size: 3rem; color: #0284c7 !important; font-weight: 700; background: none !important; margin:0;}
    .subtitle { font-size: 1.2rem; color: #64748b !important; background: none !important; margin-top:-10px; margin-bottom:20px;}

    /* 4. ZONE D'UPLOAD : NETTOYAGE RADICAL */
    [data-testid='stFileUploader'] section {
        background-color: white !important;
        border: 2px dashed #0284c7 !important;
        padding: 50px !important;
        border-radius: 12px;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        min-height: 200px !important;
    }
    
    /* Cache TOUT l'interieur (Bouton Browse, Limit 200MB, Icone cloud) */
    [data-testid='stFileUploader'] section div {
        display: none !important;
    }

    /* Affiche uniquement notre texte personnalisé au centre */
    [data-testid='stFileUploader'] section::before {
        content: "📂 Cliquez ou glissez vos fichiers PDF ici pour lancer l'analyse";
        color: #0284c7 !important;
        font-weight: bold;
        font-size: 1.4rem;
        text-align: center;
        display: block !important;
        visibility: visible !important;
    }

    /* 5. BOUTON ANALYSE ET TEXTES RÉSULTATS */
    div.stButton > button {
        background-color: #0284c7 !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 15px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100% !important;
    }
    
    /* Force le texte des fichiers listés et du reste en noir */
    [data-testid='stMarkdownContainer'] p, li, span {
        color: #1e293b !important;
    }

    .result-card {
        background-color: white !important;
        padding: 30px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        color: #1e293b !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CLASSE PDF : FIX LOGO ET MARGES ---
class ScanAOPDF(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.set_text_color(2, 132, 199)
        self.cell(0, 10, 'RAPPORT D\'ANALYSE SCANAO', 0, 1, 'R')
        self.ln(25) # Gros espace pour que le texte ne touche jamais le logo 

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(text_content, final_score, score_val):
    pdf = ScanAOPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    # Header Score
    pdf.set_font("Arial", 'B', 12)
    if score_val >= 7: pdf.set_fill_color(220, 252, 231)
    elif score_val <= 4: pdf.set_fill_color(254, 226, 226)
    else: pdf.set_fill_color(255, 237, 213)
    
    pdf.cell(0, 12, f" SCORE GLOBAL : {final_score} ", 0, 1, 'C', fill=True)
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=11)
    
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2); continue
        if line.startswith("##"):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 13)
            pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=11)
        else:
            pdf.multi_cell(0, 7, line.replace("**", ""))
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIQUE D'ANALYSE (MOTEUR V5.1) ---
def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    # Utilisation du modèle flash stable 
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"temperature": 0})
    prompt = """Tu es un Expert Analyse DCE BTP. 
    MISSION : Analyser le lot détecté. Structure : SCORE_IA: X/10, DESCRIPTION DU PROJET, FINANCES, PLANNING, TECHNIQUE. 
    ALGORITHME SCORE : Base 10. Malus: Public(-1), Réno(-1), Visite Obligatoire(-0.5), Pénalités >1000/j(-1). Bonus: Avance >10%(+0.5)."""
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- INTERFACE ---
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=120)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation</div>', unsafe_allow_html=True)

if not api_key:
    st.error("Clé API manquante dans les secrets.")
    st.stop()

files = st.file_uploader("", type=["pdf"], accept_multiple_files=True)

if files:
    if st.button(f"LANCER L'ANALYSE ({len(files)} fichiers)"):
        with st.spinner("Analyse en cours..."):
            all_text = ""
            for f in files:
                reader = PdfReader(f)
                for page in reader.pages:
                    all_text += (page.extract_text() or "") + "\n"
            
            res_text = analyze_document(api_key, all_text)
            score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
            val = float(score_match.group(1).replace(',', '.')) if score_match else 0
            
            st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
            
            pdf_data = create_pdf(res_text, f"{val}/10", val)
            st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF PRO", pdf_data, "Rapport_ScanAO.pdf", "application/pdf")
