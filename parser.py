import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

ADOPTION_TRIGGERS = [r"HAVE ADOPTED THIS REGULATION", r"HAS ADOPTED THIS REGULATION", r"HABEN FOLGENDE VERORDNUNG ERLASSEN", r"ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"]
ARTICLE_ONE_PATTERNS = [r"^Article\s+1\b", r"^Artikel\s+1\b", r"^Article\s+premier\b"]

# Chapter keywords in multiple languages
CHAPTER_KEYWORDS = ["CHAPTER", "KAPITEL", "CHAPITRE"]

def parse_dma():
    html_files = glob.glob(f"{SOURCE_FOLDER}/*.html")
    for file_path in html_files:
        lang_code = os.path.basename(file_path).split('_')[-1].split('.')[0].lower()
        print(f"Processing: {lang_code}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        data = []
        current_art_num = ""
        current_art_title = ""
        parsing_annex = False
        passed_preamble = False 
        get_title_next = False

        elements = soup.find_all(['p', 'tr', 'h1', 'h2', 'h3'])
        
        for el in elements:
            if el.name == 'p' and el.find_parent('tr'): continue
            text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
            if not text or len(text) < 2: continue

            # Clean residual noise: If text is just "CHAPTER II GATEKEEPERS", skip it
            if any(text.upper().startswith(k) for k in CHAPTER_KEYWORDS) and len(text) < 60:
                # Add it as a special "Chapter" type for the sidebar
                data.append({'ID': f'CH_HEAD_{len(data)}', 'Type': 'Chapter', 'Label': text, 'Title': '', 'Text': ''})
                continue

            # Trigger Preamble -> Body
            if not passed_preamble:
                if any(re.search(m, text.upper()) for m in ADOPTION_TRIGGERS) or any(re.search(p, text, re.IGNORECASE) for p in ARTICLE_ONE_PATTERNS):
                    passed_preamble = True

            # Annex detection
            if "ANNEX" in text.upper() and len(text) < 15:
                parsing_annex = True
                current_art_num = "ANNEX_MAIN"
                continue

            # Recitals
            if not passed_preamble and not parsing_annex:
                rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
                if rec_match:
                    data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 'Label': f'Recital ({rec_match.group(1)})', 'Title': '', 'Text': text})
                continue

            # Articles
            if passed_preamble and not parsing_annex:
                is_art_head = any(text.startswith(w) for w in ["Article", "Artikel", "Artigo", "Articolo", "Artículo"]) and len(text) < 50
                if is_art_head:
                    num_match = re.search(r'\d+', text)
                    if num_match:
                        current_art_num = f"Article_{num_match.group(0)}"
                        get_title_next = True
                        continue
                
                if get_title_next:
                    current_art_title = text
                    get_title_next = False
                    continue

            # Capture Content
            if current_art_num:
                row_id = current_art_num
                row_label = current_art_num.replace('_', ' ')
                
                if current_art_num in ["Article_5", "Article_6"]:
                    para_match = re.match(r'^(\d+)\.\s+|^\((\d+)\)\s+', text)
                    if para_match:
                        p_num = para_match.group(1) or para_match.group(2)
                        row_id = f"{current_art_num}_{p_num}"
                        row_label = f"{current_art_num.replace('_', ' ')}({p_num})"

                data.append({
                    'ID': row_id, 'Type': 'Article Paragraph' if not parsing_annex else 'Annex',
                    'Label': "Annex" if parsing_annex else row_label,
                    'Title': "Annex" if parsing_annex else current_art_title,
                    'Text': text
                })

        if data:
            df = pd.DataFrame(data)
            # Grouping but preserving Chapter headers
            res = []
            for name, group in df.groupby(['ID', 'Type', 'Label'], sort=False):
                res.append({
                    'ID': name[0], 'Type': name[1], 'Label': name[2],
                    'Title': group['Title'].iloc[0],
                    'Text': '<br><br>'.join(dict.fromkeys(group['Text']))
                })
            pd.DataFrame(res).to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False, encoding='utf-8')

if __name__ == "__main__":
    parse_dma()
