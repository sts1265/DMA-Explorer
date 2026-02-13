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
    # Captures 'fr', 'en', 'de', etc. from filenames like 'dma_fr.html'
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    print(f"Processing: {lang_code}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []
    current_art_num = ""
    parsing_annex = False
    passed_toc = False 

    for el in soup.find_all(['p', 'tr']):
        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. TRIGGER: Pivot from Recitals to Articles
        # Added French: "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"
        triggers = [
            "HAVE ADOPTED THIS REGULATION", 
            "HAS ADOPTED THIS REGULATION", 
            "HABEN FOLGENDE VERORDNUNG ERLASSEN",
            "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"
        ]
        
        if any(marker in text.upper() for marker in triggers):
            passed_toc = True
            print(f"--- Found Adoption Trigger in {lang_code} ---")
            continue

        # 2. DETECT ANNEX START (Usually at the very end)
        if "ANNEX" in text.upper() and len(text) < 20:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            continue

        # 3. CAPTURE RECITALS (Only happens BEFORE the trigger)
        if not passed_toc and not parsing_annex:
            # Matches (1), (2), etc.
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({
                    'ID': f'REC_{rec_match.group(1)}', 
                    'Type': 'Recital', 
                    'Label': f'Recital ({rec_match.group(1)})', 
                    'Text': text
                })
            continue

        # 4. DETECT ARTICLE HEADINGS (Only happens AFTER the trigger)
        if not parsing_annex and passed_toc:
            # Matches "Article 1", "Artikel 1", "Article premier" (FR)
            is_article_heading = any(text.startswith(word) for word in ["Article", "Artikel"])
            if is_article_heading and len(text) < 35:
                art_num_match = re.search(r'\d+', text)
                if art_num_match:
                    current_art_num = f"Article_{art_num_match.group(0)}"
                elif "premier" in text.lower(): # Special case for French Article 1
                    current_art_num = "Article_1"
                continue
        
        # 5. HANDLE ANNEX TABLES
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

        # 6. CAPTURE ARTICLE CONTENT
        if current_art_num:
            # Special check for Articles 5 and 6 to keep granularity
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
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # Final cleanup: Merge multiple paragraphs under the same ID
        df = df.groupby(['ID', 'Type', 'Label'], sort=False)['Text'].apply(lambda x: '<br><br>'.join(dict.fromkeys(x))).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
        print(f"Success: dma_{lang_code}.csv created.")
