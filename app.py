import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import time
import re
import requests
import tempfile
import os

# --- CONFIGURATION PAGE & THEME ---
st.set_page_config(page_title="ScanAO", page_icon="🏗️", layout="wide")

# --- GESTION DES SECRETS (CLÉ API) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    try:
        api_key = st.secrets["GEMINI_API_KEY"] # Fallback local
    except:
        api_key = None

# --- CSS PRO (DESIGN & TRADUCTION VISUELLE) ---
st.markdown("""
<style>
    /* Masquer les menus techniques */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Force le fond général en clair (au cas où) */
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0f172a !important; font-family: 'Helvetica', sans-serif; }
    
    /* --- DESIGN UPLOAD PRO --- */
    /* Cible la zone de dépôt précise */
    [data-testid='stFileUploader'] section {
        background-color: white !important; /* Force le fond blanc */
        border: 2px dashed #0284c7 !important; /* Bordure bleue */
        padding: 30px;
        border-radius: 10px;
    }
    
    /* Force TOUS les textes dans la zone de dépôt à être noirs/gris foncé */
    [data-testid='stFileUploader'] div, 
    [data-testid='stFileUploader'] span, 
    [data-testid='stFileUploader'] small,
    [data-testid='stFileUploader'] button {
        color: #1e293b !important;
    }

    /* ASTUCE TRADUCTION : Masquer le texte "Drag and drop files here" */
    [data-testid='stFileUploader'] section > div > div > span {
        display: none;
    }
    
    /* ASTUCE TRADUCTION : Ajouter le texte Français */
    [data-testid='stFileUploader'] section > div > div::before {
        content: "📂 Glissez vos fichiers PDF ici (ou cliquez sur Browse)";
        color: #0284c7 !important;
        font-weight: bold;
        font-size: 1.1rem;
        display: block;
        margin-bottom: 10px;
    }

    /* --- RESTE DU DESIGN --- */
    .main-title { font-size: 3rem; color: #0284c7 !important; margin-bottom: 0; font-weight: 700; }
    .subtitle { font-size: 1.2rem; color: #64748b !important; margin-top: -10px; margin-bottom: 20px;}
    
    div.stButton > button {
        background-color: #0284c7; color: white; border-radius: 8px;
        padding: 12px 24px; font-weight: 600; border: none; width: 100%;
        transition: 0.2s; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div.stButton > button:hover { background-color: #0369a1; }

    .result-card {
        background-color: white; padding: 25px; border-radius: 12px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1); margin-top: 20px;
        color: #1e293b !important; line-height: 1.6;
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
            if os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 20)
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
    if score_val >= 7:
        r, g, b = 220, 252, 231; txt_r, txt_g, txt_b = 22, 101, 52
    elif score_val <= 4:
        r, g, b = 254, 226, 226; txt_r, txt_g, txt_b = 153, 27, 27
    else:
        r, g, b = 255, 237, 213; txt_r, txt_g, txt_b = 154, 52, 18

    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(txt_r, txt_g, txt_b)
    pdf.cell(0, 12, f"  SCORE IA : {final_score}  ", 0, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    pdf.set_font("Arial", size=10)
    emojis_to_remove = ["💶", "🗓️", "🚨", "🔴", "⚠️", "📝"]
    clean_text = text_content
    for icon in emojis_to_remove:
        clean_text = clean_text.replace(icon, "")

    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2); continue
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        if safe_line.startswith("##"):
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(2, 132, 199)
            pdf.cell(0, 10, safe_line.replace("#", "").strip(), 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=10)
        elif safe_line.startswith("- **") or safe_line.startswith("-**"):
            clean_sub = safe_line.replace("**", "").replace("- ", "")
            if ":" in clean_sub:
                parts = clean_sub.split(":", 1)
                pdf.set_font("Arial", 'B', 10)
                pdf.write(5, "- " + parts[0] + " :")
                pdf.set_font("Arial", size=10)
                pdf.write(5, parts[1])
                pdf.ln(6)
            else:
                pdf.set_font("Arial", 'B', 10)
                pdf.write(5, "- " + clean_sub); pdf.ln(6)
        elif "**" in safe_line:
            pdf.multi_cell(0, 5, safe_line.replace("**", ""))
        else:
            pdf.multi_cell(0, 5, safe_line)
        
    return pdf.output(dest='S').encode('latin-1')

def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0})
    prompt = """
    Tu es un Expert Analyse DCE BTP.
    MISSION 0 : SYNTHÈSE DU PROJET (VUE HÉLICOPTÈRE)
    - Résume l'objet global du marché en 1 ou 2 phrases simples.
    MISSION 1 : IDENTIFICATION DU LOT
    - Identifie le LOT principal.
    MISSION 2 : EXTRACTION RIGOUREUSE
    - MARQUES : Distingue FABRICANT (Nom Propre) de produit générique.
    - PÉNALITÉS : Financières contractuelles uniquement.
    - AVANCE : Cherche le %.
    ALGORITHME DE NOTATION (GO/NOGO) :
    - Base : 10/10.
    - Malus : Marché Public (-1), Réhabilitation (-1), Visite OBLIGATOIRE (-0.5), Pénalités retard > 1000€/jour (-1), Plafond illimité (-1), Site Occupé (-1), Délai < 6 mois (-0.5).
    - Bonus : Avance > 10% (+0.5), > 20% (+1).
    CONSIGNE FORMATAGE (A RESPECTER STRICTEMENT) :
    1. Ligne 1 : "SCORE_IA: [Note]" (ex: 7.5).
    2. Ligne 2 : "Voici l'analyse du lot : [Nom du Lot détecté]".
    3. SUITE : Respecte la structure ci-dessous.
    --- STRUCTURE DU RAPPORT ---
    ## 📝 DESCRIPTION DU PROJET
    [Résumé du projet global]
    ## 💶 1. FINANCES
    - **Contexte Marché :** [Public ou Privé]
    - **Prix :** [Forfaitaire / Révisable]
    - **Avance :** [% ou Montant]
    - **Pénalités Retard :** [Montant €/jour] (Plafond : [X]%)
    - **Pénalités Majeures (>500€) :** [Liste ou "Standards"]
    - **Retenue Garantie :** [5% ?]
    - **Compte Prorata :** [Oui/Non]
    - **Paiement :** [30 jours ?]
    - **Insertion Sociale :** [Nombre d'heures]
    ## 🗓️ 2. PLANNING
    - **DLRO :** 🔴 **[DATE + HEURE]**
    - **Type de travaux :** [NEUF ou RÉHABILITATION]
    - **Visite :** [Obligatoire / Conseillée / Non requise] + [Date ou "Voir RC"]
    - **Durée :** [Durée globale]
    ## 🚨 3. TECHNIQUE
    - **Synthèse Travaux :** [Liste 4-5 mots clés]
    - **Marques Citées (ou équivalent) :**
      *Consigne : Crée 3 familles logiques. Liste 6 marques max par famille. Ajoute "..." si la liste continue.*
      - **[Famille 1] :** [Marques...]
      - **[Famille 2] :** [Marques...]
      - **[Famille 3] :** [Marques...]
    - **⚠️ Marques STRICTEMENT IMPOSÉES (Pas d'équivalent) :**
      - [Liste ou "Aucune"]
    - **Points de Vigilance (Top 5) :**
      - [Point 1]
      - [Point 2]
      - [Point 3]
      - [Point 4]
      - [Point 5]
    """
    response = model.generate_content(prompt + "\n\nDOCUMENTS :\n" + text_content)
    return response.text

# --- LAYOUT PRINCIPAL ---
col1, col2 = st.columns([1, 6])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    else:
        st.write("LOGO")
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée de Dossier de Consultation</div>', unsafe_allow_html=True)

# Clé API manquante ?
if not api_key:
    st.error("⚠️ Clé API non configurée. Vérifiez 'st.secrets'.")
    st.stop()

# Zone de dépôt avec label vide (géré par CSS)
uploaded_files = st.file_uploader(" ", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"LANCER L'ANALYSE ({len(uploaded_files)} fichiers)"):
        progress_bar = st.progress(0, text="Lecture des fichiers...")
        full_text = ""
        for i, pdf in enumerate(uploaded_files):
            full_text += f"\n--- DOC: {pdf.name} ---\n" + extract_text_from_pdf(pdf)
            progress_bar.progress(int((i + 1) / len(uploaded_files) * 40))

        try:
            progress_bar.progress(50, text="🧠 Analyse IA en cours...")
            res_text = analyze_document(api_key, full_text)
            progress_bar.progress(100, text="Terminé !")
            time.sleep(0.5); progress_bar.empty()

            score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text, re.IGNORECASE)
            final_score = "N/A"; score_val = 0; badge_html = ""
            clean_res = res_text

            if score_match:
                try:
                    score_val = float(score_match.group(1).replace(',', '.'))
                    final_score = f"{score_val}/10"
                    badge_class = "score-green" if score_val >= 7 else "score-red" if score_val <= 4 else "score-orange"
                    badge_html = f'<div class="score-badge {badge_class}">GO/NOGO : {final_score}</div>'
                    clean_res = re.sub(r"SCORE_IA.*(\n|\r\n)?", "", res_text, count=1).strip()
                except: pass

            if badge_html: st.markdown(badge_html, unsafe_allow_html=True)
            st.markdown(f'<div class="result-card">{clean_res}</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            pdf_bytes = create_pdf(clean_res, final_score, score_val)
            st.download_button("📄 TÉLÉCHARGER LE RAPPORT PDF", data=pdf_bytes, file_name=f"Rapport_ScanAO_{time.strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf")
                
        except Exception as e:
            st.error(f"Erreur : {e}")
