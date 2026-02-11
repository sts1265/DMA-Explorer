import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

# Configuration
SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Find all .html files in the sources folder
html_files = glob.glob(f"{SOURCE_FOLDER}/*.html")

def parse_dma(file_path):
    lang_code = os.path.basename(file_path).split('_')[-1].replace('.html', '')
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    data = []
    paragraphs = soup.find_all('p')
    
    # Logic for Recitals and Articles (same as before)
    # ... [Same extraction logic as the previous script] ...
    
    df = pd.DataFrame(data)
    output_path = f"{OUTPUT_FOLDER}/dma_{lang_code}.csv"
    df.to_csv(output_path, index=False)
    print(f"Processed {lang_code}")

for file in html_files:
    parse_dma(file)
