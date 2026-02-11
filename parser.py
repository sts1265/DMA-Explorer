import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

html_files = glob.glob(f"{SOURCE_FOLDER}/*.html")

for file_path in html_files:
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    print(f"Processing: {lang_code}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []
    current_art_num = ""
    parsing_annex = False
    passed_toc = False 

    # We only look for <p> tags for text and <tr> for Annex tables
    for el in soup.find_all(['p', 'tr']):
        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. TRIGGER: Start of actual content (ignores Table of Contents)
        if "HAS ADOPTED THIS REGULATION" in text.upper() or "HAT FOLGENDE VERORDNUNG ERLASSEN" in text.upper():
            passed_toc = True
            continue

        # 2. DETECT ANNEX START
        if "ANNEX" in text.upper() and len(text) < 15:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            continue

        # 3. DETECT RECITALS (Only before Articles)
        if not passed_toc and not parsing_annex:
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 'Label': f'Recital ({rec_match.group(1)})', 'Text': text})
            continue

        # 4. DETECT ARTICLE HEADINGS
        if not parsing_annex and passed_toc:
            if (text.startswith("Article") or text.startswith("Artikel")) and len(text) < 25:
                art_num_match = re.search(r'\d+', text)
                if art_num_match:
                    current_art_num = f"Article_{art_num_match.group(0)}"
                continue
        
        # 5. HANDLE ANNEX TABLE ROWS
        if parsing_annex and el.name == 'tr':
            cells = el.find_all(['td', 'th'])
            if len(cells) >= 2:
                def_title = cells[0].get_text(strip=True)
                def_text = cells[1].get_text(" ", strip=True)
                if len(def_title) > 2:
                    data.append({
                        'ID': f'ANNEX_{def_title.replace(" ", "_")[:20]}',
                        'Type': 'Annex Item',
                        'Label': f'Annex: {def_title}',
                        'Text': def_text
                    })
            continue

        # 6. CAPTURE CONTENT
        if current_art_num:
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            
            # Use Mixed Granularity for Articles 5 & 6
            if current_art_num in ["Article_5", "Article_6"] and para_match:
                para_id = f"{current_art_num}_{para_match.group(1)}"
                label = f"{current_art_num.replace('_', ' ')}({para_match.group(1)})"
            else:
                para_id = current_art_num
                label = "Annex" if parsing_annex else current_art_num.replace('_', ' ')

            data.append({
                'ID': para_id,
                'Type': 'Annex' if parsing_annex else 'Article Paragraph',
                'Label': label,
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # Merge text by ID to prevent duplication
        df = df.groupby(['ID', 'Type', 'Label'], sort=False)['Text'].apply(lambda x: '<br><br>'.join(dict.fromkeys(x))).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
