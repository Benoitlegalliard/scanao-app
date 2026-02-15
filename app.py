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

# --- CSS : FORCE LE DESIGN (BLINDAGE) ---
st.markdown("""
<style>
    /* 1. Force le thème clair et l'écriture noire partout */
    .stApp, .stApp * {
        background-color: #f8f9fa !important;
        color: #1e293b !important;
    }

    /* 2. Cache les éléments techniques */
    #MainMenu, footer, header {visibility: hidden !important;}
    
    /* 3. Titres en Bleu */
    .main-title { font-size: 3rem; color: #0284c7 !important; font-weight: 700; background: none !important;}
    .subtitle { font-size: 1.2rem; color: #64748b !important; background: none !important;}

    /* 4. ZONE D'UPLOAD : SUPPRESSION TOTALE DU BOUTON ET DES TEXTES ANGLAIS */
    [data-testid='stFileUploader'] section {
        background-color: white !important;
        border: 2px dashed #0284c7 !important;
        padding: 60px !important;
        border-radius: 12px;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        min-height: 200px;
    }
    
    /* Cache absolument tout ce qui est à l'intérieur de la zone par défaut */
    [data-testid='stFileUploader'] section div {
        display: none !important;
    }

    /* Affiche notre texte en Français à la place */
    [data-testid='stFileUploader'] section::before {
        content: "📂 Cliquez ou glissez vos fichiers PDF ici pour lancer l'analyse";
        color: #0284c7 !important;
        font-weight: bold;
        font-size: 1.4rem;
        text-align: center;
        display: block;
    }

    /* 5. BOUTON ANALYSE */
    div.stButton > button {
        background-color: #0284c7 !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 15px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100% !important;
    }

    /* 6. CARTE DE RÉSULTAT */
    .result-card {
        background-color: white !important;
        padding: 30px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CLASSE PDF : FIX DE LA DEUXIÈME PAGE ---
class ScanAOPDF(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.set_text_color(2, 132, 199)
        self.cell(0, 10, 'RAPPORT D\'ANALYSE SCANAO', 0, 1, 'R')
        self.ln(20) # Espace augmenté pour éviter le chevauchement sur page 2

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(text_content, final_score, score_val):
    pdf = ScanAOPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25) # Marge de sécurité
    
    # Score Global
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(220, 252, 231) if score_val >= 7 else pdf.set_fill_color(255, 237, 213)
    pdf.cell(0, 12, f" SCORE GLOBAL : {final_score} ", 0, 1, 'C', fill=True)
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=11)
    
    # Encodage sécurisé pour les accents
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    
    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
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

# --- LOGIQUE ANALYSE ---
def analyze_document(text):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = "Analyse ce DCE BTP et structure en : SCORE_IA: X/10, DESCRIPTION DU PROJET, FINANCES, PLANNING, TECHNIQUE."
    response = model.generate_content(f"{prompt}\n\nDOCS:\n{text}")
    return response.text

# --- INTERFACE ---
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
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
                    all_text += page.extract_text() + "\n"
            
            res_text = analyze_document(all_text)
            score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
            val = float(score_match.group(1).replace(',', '.')) if score_match else 0
            
            st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
            
            pdf_data = create_pdf(res_text, f"{val}/10", val)
            st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF", pdf_data, "Rapport_ScanAO.pdf", "application/pdf")
