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

# --- URL LOGO ---
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/1150/1150626.png"

# --- CSS (INTERFACE WEB) ---
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

    /* FIX COULEUR NUCLÉAIRE */
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
    .result-card h2:first-child { margin-top: 0; }
    
    .result-card strong { color: #0f172a !important; font-weight: 800; }

    /* BADGE SCORE */
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
    """Génère un PDF PROPRE avec Logo, Badge Couleur et Nettoyage Markdown"""
    
    class PDF(FPDF):
        def header(self):
            # 1. Gestion du LOGO (Téléchargement temporaire pour compatibilité)
            try:
                response = requests.get(LOGO_URL)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        tmp_file.write(response.content)
                        tmp_path = tmp_file.name
                    # Affichage Logo (x=10, y=8, w=20)
                    self.image(tmp_path, 10, 8, 20)
                    os.unlink(tmp_path) # Nettoyage
            except:
                pass # Si échec logo, on continue sans planter

            # 2. Titre
            self.set_font('Arial', 'B', 20)
            self.set_text_color(2, 132, 199) # Bleu ScanAO
            self.cell(0, 10, 'Rapport ScanAO', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15) # Gestion automatique du saut de page

    # --- 3. BADGE GO/NOGO (Simulé par un rectangle coloré) ---
    pdf.set_font("Arial", 'B', 12)
    
    # Choix couleur (RGB)
    if score_val >= 7:
        r, g, b = 220, 252, 231 # Vert clair
        txt_r, txt_g, txt_b = 22, 101, 52 # Vert foncé
    elif score_val <= 4:
        r, g, b = 254, 226, 226 # Rouge clair
        txt_r, txt_g, txt_b = 153, 27, 27 # Rouge foncé
    else:
        r, g, b = 255, 237, 213 # Orange clair
        txt_r, txt_g, txt_b = 154, 52, 18 # Orange foncé

    # Dessin du badge
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(txt_r, txt_g, txt_b)
    pdf.cell(0, 12, f"  SCORE IA : {final_score}  ", 0, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0) # Retour au noir
    pdf.ln(10)

    # --- 4. NETTOYAGE DU CONTENU ---
    pdf.set_font("Arial", size=10)
    
    # On supprime les emojis
    emojis_to_remove = ["💶", "🗓️", "🚨", "🔴", "⚠️", "📝"]
    clean_text = text_content
    for icon in emojis_to_remove:
        clean_text = clean_text.replace(icon, "")

    # Traitement ligne par ligne
    for line in clean_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
            
        # Encodage sécurisé
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        
        # --- LOGIQUE DE RENDU AMÉLIORÉE (CORRECTION "PAVÉ") ---
        
        if safe_line.startswith("##"):
            # TITRES DE SECTIONS
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(2, 132, 199)
            title_clean = safe_line.replace("#", "").strip()
            pdf.cell(0, 10, title_clean, 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=10)
            
        elif safe_line.startswith("- **") or safe_line.startswith("-**"):
            # SOUS-TITRES (ex: - **Prix :**)
            clean_sub = safe_line.replace("**", "").replace("- ", "")
            
            if ":" in clean_sub:
                parts = clean_sub.split(":", 1)
                key = parts[0] + " :"
                val = parts[1]
                
                # CORRECTION ICI : Utilisation de write() successifs pour un flux naturel
                pdf.set_font("Arial", 'B', 10)
                pdf.write(5, "- " + key) # Gras
                pdf.set_font("Arial", size=10)
                pdf.write(5, val) # Normal (suite directe)
                pdf.ln(6) # Saut de ligne propre après le bloc
            else:
                pdf.set_font("Arial", 'B', 10)
                pdf.write(5, "- " + clean_sub)
                pdf.ln(6)
                
        elif "**" in safe_line:
            # Texte avec gras au milieu
            clean_sub = safe_line.replace("**", "")
            pdf.multi_cell(0, 5, clean_sub)
            
        else:
            # Texte standard (Description projet, etc.)
            pdf.multi_cell(0, 5, safe_line)
        
    return pdf.output(dest='S').encode('latin-1')

def analyze_document(api_key, text_content):
    genai.configure(api_key=api_key)
    # Temperature 0 pour être factuel
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0})
    
    # PROMPT V5.1 (Toujours le même, validé)
    prompt = """
    Tu es un Expert Analyse DCE (Dossier de Consultation des Entreprises) BTP.
    
    CONTEXTE D'ANALYSE :
    - Le texte est brut (PDF). Reconstitue le sens logique.
    - Ne te fie pas à l'ordre linéaire.

    MISSION 0 : SYNTHÈSE DU PROJET (VUE HÉLICOPTÈRE)
    - Trouve l'objet global du marché (souvent en page de garde ou Article 1).
    - Résume-le en 1 ou 2 phrases simples : Nature des travaux (Neuf/Réno) + Type de bâtiment (Ecole, Bureaux...) + Lieu (si dispo).
    - Ne parle PAS des contraintes ou des lots ici. Juste la description physique de l'opération.

    MISSION 1 : IDENTIFICATION DU LOT
    - Identifie le LOT principal du dossier.
    - Adapte toute ton analyse à ce métier.

    MISSION 2 : EXTRACTION RIGOUREUSE
    - MARQUES : Distingue FABRICANT (Nom Propre) de produit générique.
    - PÉNALITÉS : Financières contractuelles uniquement.
    - AVANCE : Cherche explicitement le %.

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
    [Résumé du projet global en 2 lignes max. Ex: Construction neuve d'un groupe scolaire de 15 classes à Bordeaux.]

    ## 💶 1. FINANCES
    - **Contexte Marché :** [Public ou Privé]
    - **Prix :** [Forfaitaire / Révisable (Index...)]
    - **Avance :** [% ou Montant trouvé / "Non précisé"]
    - **Pénalités Retard :** [Montant €/jour] (Plafond : [X]%)
    - **Pénalités Majeures (>500€) :** [Liste ou "Standards"]
    - **Retenue Garantie :** [5% ?]
    - **Compte Prorata :** [Oui/Non]
    - **Paiement :** [30 jours ?]
    - **Insertion Sociale :** [Nombre d'heures] h (Si rien : "Aucune")

    ## 🗓️ 2. PLANNING
    - **DLRO :** 🔴 **[DATE + HEURE]**
    - **Type de travaux :** [NEUF ou RÉHABILITATION]
    - **Visite :** [Obligatoire / Conseillée / Non requise] + [Date ou "Voir RC"]
    - **Durée :** [Durée globale]

    ## 🚨 3. TECHNIQUE
    - **Synthèse Travaux :** [Liste 4-5 mots clés techniques du lot]
    
    - **Marques Citées (ou équivalent) :**
      *Consigne : Crée 3 familles logiques pour ce lot. Liste jusqu'à 6 marques par famille. Nom du fabricant UNIQUEMENT. Ajoute "..." si la liste continue.*
      - **[Famille 1 adaptée] :** [Marques...]
      - **[Famille 2 adaptée] :** [Marques...]
      - **[Famille 3 adaptée] :** [Marques...]
      
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

# --- UI ---
with st.sidebar:
    st.image(LOGO_URL, width=60)
    st.markdown("### Configuration")
    api_key = st.text_input("Clé API", type="password")
    if api_key: st.success("Connecté")

col1, col2 = st.columns([1,5])
with col1: st.image(LOGO_URL, width=90)
with col2:
    st.markdown('<h1 class="main-title">ScanAO</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse instantanée Multi-Lots.</div>', unsafe_allow_html=True)

st.markdown('<div class="intro-box"><b>⚡ Mode Universel :</b> Analyse Sémantique, Scoring & <u>Export PDF Pro</u>.</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader("Dossier de consultation (PDF)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"SCANNER ({len(uploaded_files)} fichiers) 🚀"):
        if not api_key: st.error("Clé API manquante")
        else:
            progress_bar = st.progress(0, text="Démarrage...")
            
            full_text = ""
            total_files = len(uploaded_files)
            
            for i, pdf in enumerate(uploaded_files):
                time.sleep(0.5) 
                text = extract_text_from_pdf(pdf)
                full_text += f"\n--- DOC: {pdf.name} ---\n" + text
                
                percent = int((i + 1) / total_files * 40)
                progress_bar.progress(percent, text=f"Lecture : {pdf.name}")

            try:
                progress_bar.progress(50, text="🤖 Identification du lot et analyse technique...")
                res_text = analyze_document(api_key, full_text)
                
                progress_bar.progress(100, text="Terminé !")
                time.sleep(0.5)
                progress_bar.empty()
                
                st.success("Analyse terminée.")
                
                # --- TRAITEMENT DU SCORE ET AFFICHAGE ---
                score_match = re.search(r"SCORE_IA\s*[:]\s*([\d\.,]+)", res_text, re.IGNORECASE)
                final_score = "N/A"
                score_val = 0 # Valeur par défaut
                badge_html = ""
                
                clean_res = res_text
                
                if score_match:
                    score_str = score_match.group(1).replace(',', '.')
                    try:
                        score_val = float(score_str)
                        final_score = f"{score_val}/10"
                        
                        badge_class = "score-orange"
                        if score_val >= 7: badge_class = "score-green"
                        elif score_val <= 4: badge_class = "score-red"
                        
                        badge_html = f'<div class="score-badge {badge_class}">GO/NOGO : {final_score}</div>'
                        
                        clean_res = re.sub(r"SCORE_IA.*(\n|\r\n)?", "", res_text, count=1).strip()
                    except:
                        pass

                if badge_html:
                    st.markdown(badge_html, unsafe_allow_html=True)
                
                # --- AFFICHAGE RESULTAT ---
                with st.container():
                    st.markdown(f"""
                    <div class="result-card">
                    {clean_res}
                    </div>
                    """, unsafe_allow_html=True)
                
                # --- BOUTON EXPORT PDF ---
                st.markdown("---") 
                pdf_bytes = create_pdf(clean_res, final_score, score_val)
                
                file_name = f"Rapport_ScanAO_{time.strftime('%Y%m%d_%H%M')}.pdf"
                
                st.download_button(
                    label="📄 TÉLÉCHARGER LE RAPPORT (PDF PRO)",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf"
                )
                    
            except Exception as e: 
                st.error(f"Erreur technique : {e}")