import pdfplumber

def calcola_costo(caratteri_input: int, caratteri_output: int, long_context: bool = False) -> dict:
    """
    Calcola il costo in USD per l'uso di gemini-1.5-pro-latest
    in base al numero di caratteri input e output.
    """
    # Tariffe (USD per 1k caratteri)
    if not long_context:
        costo_input_k = 0.0003125
        costo_output_k = 0.00125
    else:
        costo_input_k = 0.000625
        costo_output_k = 0.0025

    costo_input = (caratteri_input / 1000) * costo_input_k
    costo_output = (caratteri_output / 1000) * costo_output_k
    totale = costo_input + costo_output

    return {
        "cost_input": round(costo_input, 6),
        "cost_output": round(costo_output, 6),
        "total_cost": round(totale, 6)
    }

# Elaborazione PDF
with pdfplumber.open("/Users/cto/Documents/enterprise/AIBF/_AIBF_CLIENTI/GEMBAI/computi/PRIMUS/Mun_VII_CIG_7720106103_03_Computo_Metrico_Estimativo - 22 pagine.pdf") as pdf:
    total_chars = 0
    bad_chars = 0

    for page in pdf.pages:
        text = page.extract_text()
        if text:
            total_chars += len(text)
            bad_chars += sum(1 for c in text if c in ['�', '?', '~'])  # simboli sospetti

    quality_ratio = 0
    if total_chars > 0:
        quality_ratio = 1 - (bad_chars / total_chars)

    # Calcolo costi stimati
    cost = calcola_costo(total_chars, total_chars)

    # JSON finale con tutte le informazioni
    risultato = {
        "total_chars": total_chars,
        "bad_chars": bad_chars,
        "quality_ratio": round(quality_ratio, 4),
        "cost": cost
    }

    import json
    print(json.dumps(risultato, indent=4))
