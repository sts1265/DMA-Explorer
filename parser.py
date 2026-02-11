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
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    print(f"Processing: {lang_code}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []

    # 1. EXTRACT RECITALS
    # EUR-Lex recitals are almost always paragraphs starting with (1), (2) etc.
    # In your file, they often use the class 'oj-normal'
    for p in soup.find_all(['p', 'div']):
        text = p.get_text(" ", strip=True)
        # Regex to find (1) or (10) at the start
        rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
        if rec_match:
            data.append({
                'ID': f'REC_{rec_match.group(1)}',
                'Type': 'Recital',
                'Label': f'Recital {rec_match.group(1)}',
                'Text': text
            })

    # 2. EXTRACT ARTICLES & PARAGRAPHS
    current_art_num = ""
    
    # EUR-Lex uses 'oj-ti-art' for the "Article 1" heading
    # and 'oj-normal' or 'oj-ti-gr-1' for content
    elements = soup.find_all(['p', 'div'])
    
    for el in elements:
        text = el.get_text(" ", strip=True)
        
        # Detect "Article 1", "Article 2" etc.
        if "Article" in text and len(text) < 15:
            # Clean up text to get just "Article_1"
            current_art_num = text.replace(" ", "_").strip()
            continue

        # Detect Paragraphs like "1. ", "2. " inside an Article
        if current_art_num:
            para_match = re.match(r'^(\d+)\.\s+(.*)', text)
            if para_match:
                para_num = para_match.group(1)
                data.append({
                    'ID': f'{current_art_num}_{para_num}',
                    'Type': 'Article Paragraph',
                    'Label': f"{current_art_num.replace('_', ' ')}({para_num})",
                    'Text': text
                })
            # Handle Article 2 (Definitions) which often lacks "1." numbering
            elif "Article_2" in current_art_num and len(text) > 30:
                # We create a generic ID for definitions if they aren't numbered
                data.append({
                    'ID': f'{current_art_num}_0',
                    'Type': 'Article Paragraph',
                    'Label': 'Article 2 (Definitions)',
                    'Text': text
                })

    if data:
        df = pd.DataFrame(data)
        # Remove duplicates in case the HTML structure repeats elements
        df = df.drop_duplicates(subset=['ID'])
        df.to_csv(f"{OUTPUT_FOLDER}/dma_{lang_code}.csv", index=False)
        print(f"✅ Success: Extracted {len(data)} items for {lang_code}")
    else:
        print(f"⚠️ Warning: No data found for {lang_code}. The HTML structure might be unique.")

print("Processing complete.")
