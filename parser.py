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

if not html_files:
    print("❌ Error: No .html files found in 'sources' folder.")
    exit(1)

for file_path in html_files:
    # Identify language from filename (e.g., dma_en.html -> en)
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    print(f"Processing: {lang_code}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []

    # 1. EXTRACT RECITALS
    # Targets paragraphs starting with (1), (2) etc.
    for p in soup.find_all(['p', 'div']):
        text = p.get_text(" ", strip=True)
        rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
        if rec_match:
            data.append({
                'ID': f'REC_{rec_match.group(1)}',
                'Type': 'Recital',
                'Label': f'Recital ({rec_match.group(1)})',
                'Text': text
            })

    # 2. EXTRACT ARTICLES & PARAGRAPHS
    current_art_num = ""
    elements = soup.find_all(['p', 'div'])
    
    for el in elements:
        text = el.get_text(" ", strip=True)
        
        # Detect "Article X" or "Artikel X" and standardize ID to "Article_X"
        # Increased length limit slightly to catch "Article 10" or "Artikel 54"
        if (text.startswith("Article") or text.startswith("Artikel")) and len(text) < 20:
            art_number_match = re.search(r'\d+', text)
            if art_number_match:
                current_art_num = f"Article_{art_number_match.group(0)}"
            continue

        if current_art_num:
            # Check for numbered paragraphs (e.g., "1. ")
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            
            # LOGIC: If Article 5 or 6, create granular IDs (Article_6_5)
            # Otherwise, use the Article ID for the whole block (Article_7)
            if current_art_num in ["Article_5", "Article_6"] and para_match:
                para_id = f"{current_art_num}_{para_match.group(1)}"
                label = f"{current_art_num.replace('_', ' ')}({para_match.group(1)})"
            else:
                para_id = current_art_num
                label = current_art_num.replace('_', ' ')

            # Avoid adding very short snippets or navigation text
            if len(text) > 5:
                data.append({
                    'ID': para_id,
                    'Type': 'Article Paragraph',
                    'Label': label,
                    'Text': text
                })

    if data:
        df = pd.DataFrame(data)
        
        # For non-granular Articles (blocks), we need to merge the text rows 
        # so they don't appear as separate entries in the sidebar.
        # We group by ID and Label and join the text with double line breaks.
        df = df.groupby(['ID', 'Type', 'Label'])['Text'].apply(lambda x: '<br><br>'.join(x)).reset_index()
        
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
        print(f"✅ Success: Extracted {len(df)} unique IDs for {lang_code}")
    else:
        print(f"⚠️ Warning: No data found for {lang_code}.")

print("Processing complete.")
