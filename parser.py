import pandas as pd
from bs4 import BeautifulSoup
import re
import os

# Configuration
INPUT_FILE = 'dma.html'
OUTPUT_FILE = 'dma_explorer_data.csv'

if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found in repository.")
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

data = []

# --- EXTRACT RECITALS ---
paragraphs = soup.find_all('p')
for p in paragraphs:
    text = p.get_text(strip=True)
    match = re.match(r'^\((\d+)\)', text)
    if match:
        rec_num = match.group(1)
        data.append({
            'ID': f'REC_{rec_num}',
            'Type': 'Recital',
            'Parent': 'Preamble',
            'Label': f'Recital {rec_num}',
            'Text': text,
            'Related_Recitals': '',
            'External_Links': ''
        })

# --- EXTRACT ARTICLES & PARAGRAPHS ---
current_art_label = ""
current_art_title = ""

for p in paragraphs:
    text = p.get_text(strip=True)
    
    # Catch "Article X"
    if text.startswith("Article") and len(text) < 15:
        current_art_label = text
        current_art_title = "" # Reset title for new article
        continue
    
    # Catch the Title (usually follows Article heading)
    if current_art_label and not current_art_title and len(text) > 5:
        current_art_title = text
        continue

    # Catch numbered paragraphs: "1. The gatekeeper..."
    para_match = re.match(r'^(\d+)\.\s+(.*)', text)
    if current_art_label and para_match:
        para_num = para_match.group(1)
        clean_id = current_art_label.replace(" ", "_")
        data.append({
            'ID': f'{clean_id}_{para_num}',
            'Type': 'Article Paragraph',
            'Parent': f'{current_art_label}: {current_art_title}',
            'Label': f'{current_art_label}({para_num})',
            'Text': para_match.group(2),
            'Related_Recitals': '',
            'External_Links': ''
        })

# Save to CSV
df = pd.DataFrame(data)
df.to_csv(OUTPUT_FILE, index=False)
print(f"Successfully created {OUTPUT_FILE}")
