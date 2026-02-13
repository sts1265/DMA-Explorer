import pandas as pd
from bs4 import BeautifulSoup
import re
import os
import glob

# Constants
SOURCE_FOLDER = 'sources'
OUTPUT_FOLDER = 'data'

# Ensure output directory exists
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Triggers for transition from preamble to legal body
ADOPTION_TRIGGERS = [
    r"HAVE ADOPTED THIS REGULATION", 
    r"HAS ADOPTED THIS REGULATION", 
    r"HABEN FOLGENDE VERORDNUNG ERLASSEN", 
    r"ONT ADOPTÉ LE PRÉSENT RÈGLEMENT",
    r"HAN ADOPTADO EL PRESENTE REGLAMENTO",
    r"AVEVANO ADOTTATO IL PRESENTE REGOLAMENTO"
]

# Fallback trigger: If adoption phrase is missed, switch when Article 1 is seen
ARTICLE_ONE_PATTERNS = [
    r"^Article\s+1\b", 
    r"^Artikel\s+1\b", 
    r"^Article\s+premier\b", 
    r"^Articolo\s+1\b",
    r"^Artículo\s+1\b"
]

def parse_dma():
    html_files = glob.glob(f"{SOURCE_FOLDER}/*.html")
    if not html_files:
        print(f"No HTML files found in {SOURCE_FOLDER}. Please place your DMA_en.html files there.")
        return

    for file_path in html_files:
        # Extract language code from filename (e.g., DMA_en.html -> en)
        lang_code = os.path.basename(file_path).split('_')[-1].split('.')[0].lower()
        print(f"Processing: {lang_code} ({file_path})")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        data = []
        current_art_num = ""
        current_art_title = ""
        parsing_annex = False
        passed_preamble = False 
        get_title_next = False

        # Extract all potential text elements
        elements = soup.find_all(['p', 'tr', 'h1', 'h2', 'h3'])
        
        for el in elements:
            # Prevent double-counting text from nested tags (like <p> inside <td>)
            if el.name == 'p' and el.find_parent('tr'):
                continue
                
            text = el.get_text(" ", strip=True).replace('\xa0', ' ').strip()
            if not text or len(text) < 2: 
                continue

            # 1. TRIGGER DETECTION: Switching from Recitals to Articles
            if not passed_preamble:
                if any(re.search(marker, text.upper()) for marker in ADOPTION_TRIGGERS):
                    passed_preamble = True
                    print(f"   >>> Found Adoption Trigger.")
                    continue
                if any(re.search(pat, text, re.IGNORECASE) for pat in ARTICLE_ONE_PATTERNS):
                    passed_preamble = True
                    print(f"   >>> Found Article 1 (Fallback Trigger).")
                    # Let the logic below process this text as Article 1 content

            # 2. ANNEX DETECTION
            # Typically "ANNEX" appears on its own line after the last article
            if "ANNEX" in text.upper() and len(text) < 15:
                parsing_annex = True
                current_art_num = "ANNEX_MAIN"
                current_art_title = "Annex"
                print(f"   >>> Entering Annex Section.")
                continue

            # 3. RECITALS (Only processed before the Trigger)
            if not passed_preamble and not parsing_annex:
                rec_match = re.match(r'^\((\d+)\)\s+(.*)', text)
                if rec_match:
                    num = rec_match.group(1)
                    data.append({
                        'ID': f'REC_{num}', 
                        'Type': 'Recital', 
                        'Label': f'Recital ({num})', 
                        'Title': '',
                        'Text': text
                    })
                continue

            # 4. ARTICLE HEADINGS (Only processed after the Trigger)
            if passed_preamble and not parsing_annex:
                # Identify "Article X" or "Artikel X"
                is_article_head = any(text.startswith(w) for w in ["Article", "Artikel", "Artigo", "Articolo", "Artículo"]) and len(text) < 50
                if is_article_head:
                    num_match = re.search(r'\d+', text)
                    if num_match:
                        current_art_num = f"Article_{num_match.group(0)}"
                        get_title_next = True # The next line is usually the Article title
                        continue
                    elif "premier" in text.lower():
                        current_art_num = "Article_1"
                        get_title_next = True
                        continue
                
                # Capture the title if we just found an Article header
                if get_title_next:
                    current_art_title = text
                    get_title_next = False
                    continue

            # 5. CONTENT CAPTURE (Articles & Annex)
            if current_art_num:
                row_id = current_art_num
                row_label = current_art_num.replace('_', ' ')
                row_type = 'Article Paragraph'
                
                if parsing_annex:
                    row_id = "ANNEX_MAIN"
                    row_label = "Annex"
                    row_type = "Annex"
                    current_art_title = "Annex"

                # SPLITTING FOR ARTICLE 5 & 6 (Paragraph level)
                # Matches "1. " or "(1) " at the start of the block
                if current_art_num in ["Article_5", "Article_6"]:
                    para_match = re.match(r'^(\d+)\.\s+|^\((\d+)\)\s+', text)
                    if para_match:
                        p_num = para_match.group(1) or para_match.group(2)
                        row_id = f"{current_art_num}_{p_num}"
                        row_label = f"{current_art_num.replace('_', ' ')}({p_num})"

                data.append({
                    'ID': row_id,
                    'Type': row_type,
                    'Label': row_label,
                    'Title': current_art_title,
                    'Text': text
                })

        # CLEANUP AND SAVE
        if data:
            df = pd.DataFrame(data)
            # Group by ID/Label to merge text fragments and remove internal duplicates
            df = df.groupby(['ID', 'Type', 'Label'], sort=False).agg({
                'Title': 'first',
                'Text': lambda x: '<br><br>'.join(dict.fromkeys(x))
            }).reset_index()
            
            output_file = f"{OUTPUT_FOLDER}/dma_{lang_code}.csv"
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   [Success] Saved {len(df)} rows to {output_file}")

if __name__ == "__main__":
    parse_dma()
