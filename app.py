import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import time
import re
import os

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="ScanAO", page_icon="🏗️", layout="wide")

# --- RÉCUPÉRATION CLÉ API ---
api_key = st.secrets.get("GEMINI_API_KEY")

# --- CSS : BLINDAGE TOTAL COULEURS & DESIGN ---
st.markdown("""
<style>
    /* Force le fond clair et texte noir sur toute l'application */
    .stApp, .stApp * {
        background-color: #f8f9fa !important;
        color: #1e293b !important;
    }
    
    #MainMenu, footer, header {visibility: hidden !important;}

    .main-title { font-size: 3rem; color: #0284c7 !important; font-weight: 700; background:none !important; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; background:none !important; margin-top:-10px; }

    /* ZONE D'UPLOAD PERSONNALISÉE */
    [data-testid='stFileUploader'] section {
        background-color: white !important;
        border: 2px dashed #0284c7 !important;
        padding: 40px !important;
        border-radius: 12px;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    
    /* Masquer les éléments anglais et le bouton noir */
    [data-testid='stFileUploader'] section > div { display: none !important; }
    [data-testid='stFileUploader'] section::before {
        content: "📂 Cliquez ou glissez vos fichiers PDF ici pour lancer l'analyse";
        color: #0284c7 !important;
        font-weight: bold; font-size: 1.2rem; text-align: center; display: block !important;
    }

    /* Bouton de scan */
    div.stButton > button {
        background-color: #0284c7 !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 15px !important;
        font-weight: 600 !important;
        width: 100% !important;
        border: none !important;
    }

    /* Cartes de résultats */
    .result-card {
        background-color: white !important;
        padding: 30px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CLASSE PDF : FIX LOGO PAGE 2 ---
class ScanAOPDF(FPDF):
    def header(self):
        # Affiche le logo seulement sur la page 1
        if self.page_no() == 1 and os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.set_text_color(2, 132, 199)
        self.cell(0, 10, 'Rapport d\'Analyse ScanAO', 0, 1, 'R')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(text_content, final_score, score_val):
    pdf = ScanAOPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(220, 252, 231) if score_val >= 7 else pdf.set_fill_color(255, 237, 213)
    pdf.cell(0, 12, f" SCORE GLOBAL : {final_score} ", 0, 1, 'C', fill=True)
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    for line in clean_text.split('\n'):
        if line.startswith("##"):
            pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", size=10)
        else:
            pdf.multi_cell(0, 6, line.replace("**", ""))
            
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIQUE ANALYSE (PROMPT COMPLET) ---
def analyze_document(api_key, text_content):
    # Méthode de connexion corrigée
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Tu es un Expert Analyse DCE BTP. Structure ton rapport ainsi :
    SCORE_IA: X/10
    ## 📝 DESCRIPTION DU PROJET
    ## 💶 1. FINANCES
    ## 🗓️ 2. PLANNING
    ## 🚨 3. TECHNIQUE
    
    Algorithme de notation : Base 10. Malus: Marché Public(-1), Réhabilitation(-1), Visite OBLIGATOIRE(-0.5), Pénalités retard > 1000€/jour (-1). Bonus: Avance > 10% (+0.5).
    """
    
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- INTERFACE ---
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=110)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation</div>', unsafe_allow_html=True)

if not api_key:
    st.error("Clé API manquante dans les Secrets de l'application.")
    st.stop()

uploaded_files = st.file_uploader("", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"LANCER L'ANALYSE ({len(uploaded_files)} fichiers) 🚀"):
        with st.spinner("Analyse sémantique en cours..."):
            all_text = ""
            for f in uploaded_files:
                reader = PdfReader(f)
                for page in reader.pages:
                    all_text += (page.extract_text() or "") + "\n"
            
            try:
                res_text = analyze_document(api_key, all_text)
                
                # Extraction score
                score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text)
                val = float(score_match.group(1).replace(',', '.')) if score_match else 0
                
                st.markdown(f'<div class="result-card">{res_text}</div>', unsafe_allow_html=True)
                
                st.markdown("---")
                pdf_data = create_pdf(res_text, f"{val}/10", val)
                st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF PRO", pdf_data, "Rapport_ScanAO.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")
