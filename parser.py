import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Robust triggers for European legal texts
ADOPTION_TRIGGERS = [
    r"HAVE ADOPTED THIS REGULATION", 
    r"HAS ADOPTED THIS REGULATION", 
    r"HABEN FOLGENDE VERORDNUNG ERLASSEN", 
    r"ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"
]

# Patterns to recognize "Article 1" in various languages
ARTICLE_ONE_PATTERNS = [r"^Article\s+1\b", r"^Artikel\s+1\b", r"^Article\s+premier\b", r"^Articolo\s+1\b"]

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

    # Process tags, excluding those nested inside other text-heavy tags to prevent double-text
    for el in soup.find_all(['p', 'tr', 'h1', 'h2', 'h3']):
        # If the tag is inside a table row and we are already processing rows, skip it
        if el.name == 'p' and el.find_parent('tr'):
            continue
            
        text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text or len(text) < 2: continue

        # 1. DETECT TRANSITION TO ARTICLES (The "Trigger")
        if not passed_toc:
            # Check for Adoption Formula
            if any(re.search(marker, text.upper()) for marker in ADOPTION_TRIGGERS):
                passed_toc = True
                print(f"   >>> Found Adoption Trigger")
                continue
            # Check for "Article 1" as a fallback trigger
            if any(re.search(pat, text, re.IGNORECASE) for pat in ARTICLE_ONE_PATTERNS):
                passed_toc = True
                print(f"   >>> Found Article 1 (Fallback Trigger)")
                # Don't 'continue' here, let the Article logic below catch it

        # 2. DETECT ANNEX
        if "ANNEX" in text.upper() and len(text) < 25:
            parsing_annex = True
            current_art_num = "ANNEX_MAIN"
            print(f"   >>> Found Annex")
            continue

        # 3. RECITALS (Only if we haven't reached Articles yet)
        if not passed_toc and not parsing_annex:
            rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
            if rec_match:
                data.append({'ID': f'REC_{rec_match.group(1)}', 'Type': 'Recital', 
                             'Label': f'Recital ({rec_match.group(1)})', 'Text': text})
            continue

        # 4. ARTICLE HEADINGS
        if passed_toc and not parsing_annex:
            # Matches "Article X" or "Artikel X"
            if any(text.startswith(w) for w in ["Article", "Artikel", "Artigo", "Articolo"]) and len(text) < 45:
                num_match = re.search(r'\d+', text)
                if num_match:
                    current_art_num = f"Article_{num_match.group(0)}"
                    get_title_next = True 
                    continue
                elif "premier" in text.lower():
                    current_art_num = "Article_1"
                    get_title_next = True
                    continue
            
            if get_title_next:
                current_art_title = text
                get_title_next = False
                continue

        # 5. CAPTURE CONTENT
        if current_art_num:
            # Check for Paragraph numbering (specifically for Art 5/6)
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
        # Deduplicate and join fragments
        df = df.groupby(['ID', 'Type', 'Label'], sort=False).agg({
            'Title': 'first',
            'Text': lambda x: '<br><br>'.join(dict.fromkeys(x))
        }).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False, encoding='utf-8')
        print(f"   Saved {len(df)} rows.")
