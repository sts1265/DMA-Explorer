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
    current_art_title = ""
    parsing_annex = False
    passed_toc = False 
    get_title_next = False

    # FIX: Using a more specific selector to avoid nested double-text
    # We look for p tags that aren't inside other captured tags
    for el in soup.find_all(['p', 'tr']):
        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. TRIGGER: Adoption Formula
        triggers = ["HAVE ADOPTED THIS REGULATION", "HAS ADOPTED THIS REGULATION", 
                    "HABEN FOLGENDE VERORDNUNG ERLASSEN", "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"]
        if any(marker in text.upper() for marker in triggers):
            passed_toc = True
            continue

        # 2. ANNEX START
        if "ANNEX" in text.upper() and len(text) < 20:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            continue

        # 3. RECITALS (BEFORE Adoption)
        if not passed_toc and not parsing_annex:
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 
                             'Label': f'Recital ({rec_match.group(1)})', 'Text': text})
            continue

        # 4. ARTICLE HEADINGS & TITLES
        if not parsing_annex and passed_toc:
            # Check if this line is "Article X"
            if (text.startswith("Article") or text.startswith("Artikel")) and len(text) < 30:
                art_num_match = re.search(r'\d+', text)
                if art_num_match:
                    current_art_num = f"Article_{art_num_match.group(0)}"
                    get_title_next = True # The next line will be the title
                    continue
                elif "premier" in text.lower():
                    current_art_num = "Article_1"
                    get_title_next = True
                    continue
            
            # If the previous line was "Article X", this line is the Official Title
            if get_title_next:
                current_art_title = text
                get_title_next = False
                continue

        # 5. CONTENT CAPTURE
        if current_art_num:
            # Handle mixed granularity for Art 5/6
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
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
                'Title': current_art_title, # Store the language-specific title
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # FIX: The lambda now handles cases where Title might be different across rows
        df = df.groupby(['ID', 'Type', 'Label'], sort=False).agg({
            'Title': 'first',
            'Text': lambda x: '<br><br>'.join(dict.fromkeys(x))
        }).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
