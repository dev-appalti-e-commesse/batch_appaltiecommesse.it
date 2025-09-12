#!/usr/bin/env python3
"""
Crop per-riga da PDF usando come delimitatore la parola 'SOMMANO',
mantenendo la grafica originale (immagini identiche al PDF).

La riga 'SOMMANO' è inclusa nel ritaglio (vedi extend_bottom).
Puoi regolare l'inclusione con --include-keyword-padding.

Uso:
  python crop_sommano.py --pdf "file.pdf" --out "cartella_output" --zip

Opzioni utili:
  --keyword "SOMMANO"              (delimitatore, default: SOMMANO)
  --dpi 144                        (qualità export)
  --left 6 --right 6               (margini orizzontali in punti PDF)
  --extend-top -4                  (estensione top dal 1° blocco)
  --extend-bottom 6                (quanto scendere sotto 'SOMMANO' per includerlo bene)
  --include-keyword-padding 8      (padding extra sotto 'SOMMANO')
  --zip                            (crea anche un .zip con tutti i ritagli)
"""

import os
import zipfile
import argparse
from pathlib import Path

import fitz  # PyMuPDF


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def crop_rows_by_keyword(
        pdf_path: Path,
        out_dir: Path,
        keyword: str = "SOMMANO",
        dpi: int = 144,
        left_margin: float = 6.0,
        right_margin: float = 6.0,
        extend_top: float = -4.0,
        extend_bottom: float = 6.0,
        include_keyword_padding: float = 8.0,
        make_zip: bool = True,
) -> Path | None:
    """
    Ritaglia il PDF in immagini per ciascun segmento terminante con 'keyword'.
    Il crop include la riga 'keyword' grazie a extend_bottom + padding.
    """
    pdf_path = pdf_path.resolve()
    out_dir = ensure_dir(out_dir.resolve())

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF non trovato: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    saved_files = []

    for pno in range(len(doc)):
        page = doc[pno]

        # Trova tutte le occorrenze della parola chiave (SOMMANO)
        hits = page.search_for(keyword)
        if not hits:
            continue

        hits = sorted(hits, key=lambda r: (r.y0, r.x0))

        # Top del contenuto della pagina (euristica)
        blocks = page.get_text("blocks")
        page_top = page.rect.y0 + 10
        if blocks:
            page_top = min(b[1] for b in blocks) + extend_top

        prev_bottom = page_top
        row_idx = 1

        for rect in hits:
            # Ritaglio a tutta larghezza: include la riga 'SOMMANO'
            bottom = rect.y1 + extend_bottom + include_keyword_padding
            crop = fitz.Rect(
                page.rect.x0 + left_margin,
                prev_bottom,
                page.rect.x1 - right_margin,
                bottom,
                )

            crop = crop & page.rect
            if crop.height >= 6 and crop.width >= 6:
                pix = page.get_pixmap(matrix=matrix, clip=crop, alpha=False)
                fname = out_dir / f"page{pno+1:02d}_row{row_idx:02d}.png"
                pix.save(str(fname))
                saved_files.append(fname)
                row_idx += 1

            # Il prossimo ritaglio parte appena sotto la riga 'SOMMANO'
            prev_bottom = rect.y1 + 2

    zip_path = None
    if make_zip and saved_files:
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in saved_files:
                zf.write(f, arcname=f.name)

        print(f"Archivio ZIP: {zip_path}  ({len(saved_files)} immagini)")

    print(f"Ritagli salvati in: {out_dir}")
    return zip_path


def parse_args():
    ap = argparse.ArgumentParser(description="Crop sezioni PDF fino alla riga 'SOMMANO', includendo la riga stessa.")
    ap.add_argument("--pdf", required=True, help="Percorso del file PDF d'origine")
    ap.add_argument("--out", required=True, help="Cartella di output per i ritagli")
    ap.add_argument("--keyword", default="SOMMANO", help="Parola di delimitazione")
    ap.add_argument("--dpi", type=int, default=144, help="Risoluzione di render (default: 144)")
    ap.add_argument("--left", type=float, default=6.0, help="Margine sinistro in punti PDF")
    ap.add_argument("--right", type=float, default=6.0, help="Margine destro in punti PDF")
    ap.add_argument("--extend-top", type=float, default=-4.0, help="Estensione top dal primo blocco")
    ap.add_argument("--extend-bottom", type=float, default=6.0, help="Estensione oltre la baseline 'SOMMANO'")
    ap.add_argument("--include-keyword-padding", type=float, default=8.0, help="Padding extra sotto 'SOMMANO'")
    ap.add_argument("--zip", action="store_true", help="Crea anche lo ZIP dei ritagli")
    return ap.parse_args()


def main():
    args = parse_args()
    crop_rows_by_keyword(
        pdf_path=Path(args.pdf),
        out_dir=Path(args.out),
        keyword=args.keyword,
        dpi=args.dpi,
        left_margin=args.left,
        right_margin=args.right,
        extend_top=args.extend_top,
        extend_bottom=args.extend_bottom,
        include_keyword_padding=args.include_keyword_padding,
        make_zip=args.zip,
    )


if __name__ == "__main__":
    main()
