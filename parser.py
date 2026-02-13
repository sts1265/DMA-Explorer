import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Supported language adoption triggers
TRIGGERS = [
    "HAVE ADOPTED THIS REGULATION", "HAS ADOPTED THIS REGULATION", 
    "HABEN FOLGENDE VERORDNUNG ERLASSEN", 
    "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT", "ONT ARRÊTÉ LE PRÉSENT RÈGLEMENT"
]

html_files = glob.glob(f"{SOURCE_FOLDER}/*.html")

for file_path in html_files:
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    print(f"Processing: {lang_code}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []
    current_art_num = ""
    current_art_title = ""
    parsing_annex = False
    passed_toc = False 
    get_title_next = False

    # We process all elements but filter strictly to avoid double-counting
    for el in soup.find_all(['p', 'tr', 'div']):
        # Ignore deep-nested elements that cause double-text
        if el.name == 'p' and (el.find_parent('table') or el.find_parent('p')):
            continue
        if el.name == 'div' and (el.find('p') or el.find('tr')):
            continue

        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. TRIGGER: Check if we passed the Table of Contents
        if any(marker in text.upper() for marker in TRIGGERS):
            passed_toc = True
            continue

        # 2. DETECT ANNEX
        if "ANNEX" in text.upper() and len(text) < 20:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            continue

        # 3. RECITALS (Only before Articles)
        if not passed_toc and not parsing_annex:
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 
                             'Label': f'Recital ({rec_match.group(1)})', 'Text': text})
            continue

        # 4. ARTICLE HEADINGS (e.g., "Article 1" or "Artikel 1")
        if not parsing_annex and passed_toc:
            if any(text.startswith(w) for w in ["Article", "Artikel", "Artigo", "Articolo"]) and len(text) < 35:
                num_match = re.search(r'\d+', text)
                if num_match:
                    current_art_num = f"Article_{num_match.group(0)}"
                    get_title_next = True 
                    continue
                elif "premier" in text.lower():
                    current_art_num = "Article_1"
                    get_title_next = True
                    continue
            
            # The very next line after "Article X" is the official Title
            if get_title_next:
                current_art_title = text
                get_title_next = False
                continue

        # 5. CAPTURE PROVISION CONTENT
        if current_art_num:
            # Granularity for Art 5 & 6
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            if current_art_num in ["Article_5", "Article_6"] and para_match:
                row_id = f"{current_art_num}_{para_match.group(1)}"
                row_label = f"{current_art_num.replace('_', ' ')}({para_match.group(1)})"
            else:
                row_id = current_art_num
                row_label = "Annex" if parsing_annex else current_art_num.replace('_', ' ')

            data.append({
                'ID': row_id,
                'Type': 'Annex' if parsing_annex else 'Article Paragraph',
                'Title': current_art_title,
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # Deduplicate and join paragraphs
        df = df.groupby(['ID', 'Type', 'Label'], sort=False).agg({
            'Title': 'first',
            'Text': lambda x: '<br><br>'.join(dict.fromkeys(x))
        }).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False, encoding='utf-8')
        print(f"-> Saved {len(df)} rows.")
