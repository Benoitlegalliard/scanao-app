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
st.set_page_config(page_title="ScanAO", page_icon="🏗️", layout="wide")

# --- RÉCUPÉRATION CLÉ API ---
api_key = st.secrets.get("GEMINI_API_KEY")

# --- CSS : DESIGN D'ORIGINE + FIX VISIBILITÉ ---
st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp { background-color: #f8f9fa; }
    
    /* FORCE LE NOIR SUR TOUTE L'APPLI POUR LA LISIBILITÉ */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp div { 
        color: #1e293b !important; 
    }
    
    .main-title { font-size: 3rem; color: #0284c7 !important; font-weight: 700; margin: 0; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; margin-top: -5px; }
    
    .intro-box {
        background-color: #e0f2fe; padding: 15px; border-radius: 8px;
        border-left: 5px solid #0284c7; color: #0369a1; margin-bottom: 20px;
    }

    div.stButton > button {
        background-color: #0284c7; color: white !important; border-radius: 8px;
        padding: 12px; font-weight: 600; border: none; width: 100%;
    }

    /* FIX SPECIFIQUE NOMS DE FICHIERS BLANCS */
    [data-testid="stFileUploaderFileName"] { 
        color: #1e293b !important; 
        font-weight: bold !important; 
    }

    .result-card {
        background-color: white !important;
        padding: 25px; border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0;
    }

    .score-badge {
        display: inline-block; padding: 8px 16px; border-radius: 20px;
        font-weight: 800; font-size: 1.2rem; margin-bottom: 20px; border: 2px solid;
    }
    .score-green { background-color: #dcfce7; color: #166534; border-color: #166534; }
    .score-orange { background-color: #ffedd5; color: #9a3412; border-color: #9a3412; }
    .score-red { background-color: #fee2e2; color: #991b1b; border-color: #991b1b; }

    [data-testid='stFileUploader'] { background-color: white; border: 2px dashed #cbd5e1; padding: 20px; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS PDF ---
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
            if os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 25)
            self.set_font('Arial', 'B', 15)
            self.set_text_color(2, 132, 199)
            self.cell(0, 10, 'Rapport ScanAO', 0, 1, 'R')
            self.ln(20)

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 12, f" SCORE IA : {final_score} ", 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_text.replace("**", ""))
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIQUE IA (VERSION 2.0/2.5 FLASH) ---
def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    # RESTAURATION DU MODELE FONCTIONNEL
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    prompt = """
    Tu es un Expert Analyse DCE BTP. 
    MISSION 0 : SYNTHÈSE DU PROJET (VUE HÉLICOPTÈRE)
    MISSION 1 : IDENTIFICATION DU LOT
    MISSION 2 : EXTRACTION RIGOUREUSE (MARQUES, PÉNALITÉS, AVANCE)
    ALGORITHME DE NOTATION (GO/NOGO) : Base 10.
    STRUCTURE : SCORE_IA: X/10, ## 📝 DESCRIPTION, ## 💶 1. FINANCES, ## 🗓️ 2. PLANNING, ## 🚨 3. TECHNIQUE.
    """
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- INTERFACE ---
col1, col2 = st.columns([1,5])
with col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=100)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation.</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader("", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"SCANNER ({len(uploaded_files)} fichiers) 🚀"):
        if not api_key: st.error("Clé API manquante")
        else:
            with st.spinner("Analyse approfondie en cours..."):
                full_text = ""
                for pdf in uploaded_files:
                    full_text += extract_text_from_pdf(pdf)
                try:
                    res_text = analyze_document(api_key, full_text)
                    score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
                    val = float(score_match.group(1).replace(',', '.')) if score_match else 0
                    
                    st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
                    pdf_bytes = create_pdf(res_text, f"{val}/10", val)
                    st.download_button("Télécharger le Rapport PDF", pdf_bytes, "Rapport_ScanAO.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Erreur : {e}")
