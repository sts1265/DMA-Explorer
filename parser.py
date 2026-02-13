import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# More robust trigger list (regex-friendly)
TRIGGERS = [
    r"HAVE ADOPTED THIS REGULATION", 
    r"HAS ADOPTED THIS REGULATION", 
    r"HABEN FOLGENDE VERORDNUNG ERLASSEN", 
    r"ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"
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

    # FIX: Process ALL tags that might contain text, but focus on the "deepest" ones
    # to avoid the double-text issue.
    for el in soup.find_all(['p', 'tr', 'span', 'div']):
        # Ignore container elements that have children (to avoid double-counting)
        if el.name in ['div', 'tr'] and (el.find('p') or el.find('span')):
            continue
            
        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. TRIGGER: Check for boundary between Recitals and Articles
        if not passed_toc:
            if any(re.search(marker, text.upper()) for marker in TRIGGERS):
                passed_toc = True
                print(f"   >>> Trigger found in {lang_code}!")
                continue

        # 2. DETECT ANNEX
        if "ANNEX" in text.upper() and len(text) < 25:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            continue

        # 3. RECITALS (Only before trigger)
        if not passed_toc and not parsing_annex:
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 
                             'Label': f'Recital ({rec_match.group(1)})', 'Text': text})
            continue

        # 4. ARTICLE HEADINGS (Only after trigger)
        if passed_toc and not parsing_annex:
            # Matches "Article 1", "Artikel 1", etc.
            if any(text.startswith(w) for w in ["Article", "Artikel", "Artigo", "Articolo"]) and len(text) < 40:
                num_match = re.search(r'\d+', text)
                if num_match:
                    current_art_num = f"Article_{num_match.group(0)}"
                    get_title_next = True 
                    continue
                elif "premier" in text.lower(): # French specific
                    current_art_num = "Article_1"
                    get_title_next = True
                    continue
            
            if get_title_next:
                current_art_title = text
                get_title_next = False
                continue

        # 5. CONTENT CAPTURE
        if current_art_num:
            # Special Granularity for Art 5 & 6
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            if current_art_num in ["Article_5", "Article_6"] and para_match:
                row_id = f"{current_art_num}_{para_match.group(1)}"
                row_label = f"{current_art_num.replace('_', ' ')}({para_match.group(1)})"
            else:
                row_id = current_art_num
                row_label = "Annex" if parsing_annex else current_art_num.replace('_', ' ')

            data.append({
                'ID': row_id,
                'Type': 'Article Paragraph' if not parsing_annex else 'Annex',
                'Title': current_art_title,
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # Final clean: Remove duplicates and merge text chunks
        df = df.groupby(['ID', 'Type', 'Label'], sort=False).agg({
            'Title': 'first',
            'Text': lambda x: '<br><br>'.join(dict.fromkeys(x))
        }).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False, encoding='utf-8')
        print(f"   Success: {len(df)} rows saved.")
