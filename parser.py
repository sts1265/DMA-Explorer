// ... (inside displayContent function)

if (getVal(row, 'Type') === 'Recital') {
    const num = id.replace('REC_', '');
    masterLinks.forEach(m => {
        const recs = getVal(m, 'Related_Recitals').split(',').map(s => s.trim().toLowerCase());
        // Check if this recital number OR the word 'annex' is mentioned
        if (recs.includes(num)) {
            const artData = dmaData.find(x => getVal(x, 'ID') === getVal(m, 'ID'));
            if (artData) {
                const d = document.createElement('details');
                d.innerHTML = `<summary>${getVal(artData, 'Label')}: ${resolveTitle(artData, m, lang, getVal(m, 'ID'))}</summary><div style="font-size:0.85rem; padding:10px;">${getVal(artData, 'Text')}</div>`;
                sideList.appendChild(d);
            }
        }
    });
} else {
    // Handling "Annex" in the Related_Recitals column of an Article
    const refs = getVal(map, 'Related_Recitals').split(',').map(s => s.trim());
    refs.forEach(ref => {
        const isAnnex = ref.toLowerCase() === "annex";
        const searchId = isAnnex ? "ANNEX_MAIN" : `REC_${ref}`;
        const refData = dmaData.find(x => getVal(x, 'ID') === searchId);
        
        if (refData) {
            const d = document.createElement('details');
            // If it's the annex, label it "Annex", otherwise "Recital X"
            d.innerHTML = `<summary>${isAnnex ? 'Annex' : 'Recital ' + ref}</summary><div style="font-size:0.85rem; padding:10px;">${getVal(refData, 'Text')}</div>`;
            sideList.appendChild(d);
        }
    });
}
// ...
