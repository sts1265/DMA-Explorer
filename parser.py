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

    # Strategy: Only look at <p> tags to avoid div/p duplication
    # Most EUR-Lex content is contained within <p> tags.
    for p in soup.find_all('p'):
        # Clean up text: replace non-breaking spaces and strip whitespace
        text = p.get_text(" ", strip=True).replace('\xa0', ' ').strip()
        if not text:
            continue

        # 1. EXTRACT RECITALS (e.g., "(1) The purpose...")
        rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
        if rec_match:
            data.append({
                'ID': f'REC_{rec_match.group(1)}',
                'Type': 'Recital',
                'Label': f'Recital ({rec_match.group(1)})',
                'Text': text
            })
            continue # Recitals are usually separate from articles

        # 2. DETECT ARTICLE HEADINGS (e.g., "Article 5" or "Artikel 5")
        if (text.startswith("Article") or text.startswith("Artikel")) and len(text) < 20:
            art_num_match = re.search(r'\d+', text)
            if art_num_match:
                current_art_num = f"Article_{art_num_match.group(0)}"
            continue

        # 3. EXTRACT CONTENT
        if current_art_num:
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            
            # Logic: Granular for Art 5 & 6, Block for others
            if current_art_num in ["Article_5", "Article_6"] and para_match:
                para_id = f"{current_art_num}_{para_match.group(1)}"
                label = f"{current_art_num.replace('_', ' ')}({para_match.group(1)})"
            else:
                para_id = current_art_num
                label = current_art_num.replace('_', ' ')

            data.append({
                'ID': para_id,
                'Type': 'Article Paragraph',
                'Label': label,
                'Text': text
            })

    if data:
        df = pd.DataFrame(data)
        # Merge text blocks for the same ID (Crucial for 'Block' Articles)
        df = df.groupby(['ID', 'Type', 'Label'], sort=False)['Text'].apply(lambda x: '<br><br>'.join(x)).reset_index()
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
        print(f"✅ Extracted {len(df)} items for {lang_code}")
