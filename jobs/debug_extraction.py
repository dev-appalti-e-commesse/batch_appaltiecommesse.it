#!/usr/bin/env python3
"""
Debug script to analyze why PDF extraction works locally but fails in container
"""
import os
import sys
import pdfplumber
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_pdf_extraction(pdf_path: str):
    """Debug PDF text extraction to understand differences between local and container"""
    
    logger.info(f"=== PDF DEBUG ANALYSIS ===")
    logger.info(f"PDF Path: {pdf_path}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"pdfplumber version: {pdfplumber.__version__}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"PDF opened successfully - {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages):
                logger.info(f"\n=== PAGE {page_num + 1} ===")
                
                # Extract text with different methods
                text_default = page.extract_text()
                text_tolerance = page.extract_text(x_tolerance=2, y_tolerance=2)
                
                logger.info(f"Default extraction length: {len(text_default) if text_default else 0}")
                logger.info(f"Tolerance extraction length: {len(text_tolerance) if text_tolerance else 0}")
                
                # Show first 500 characters of each method
                if text_default:
                    logger.info(f"DEFAULT TEXT (first 500 chars):\n{text_default[:500]}")
                    
                if text_tolerance:
                    logger.info(f"TOLERANCE TEXT (first 500 chars):\n{text_tolerance[:500]}")
                
                # Look for key Primus format indicators
                text_to_analyze = text_tolerance or text_default or ""
                
                logger.info(f"\n=== FORMAT DETECTION ===")
                logger.info(f"Contains 'TARIFFA': {'TARIFFA' in text_to_analyze}")
                logger.info(f"Contains 'DESIGNAZIONE DEI LAVORI': {'DESIGNAZIONE DEI LAVORI' in text_to_analyze}")
                logger.info(f"Contains 'SOMMANO': {'SOMMANO' in text_to_analyze}")
                
                # Show all lines to understand structure
                lines = text_to_analyze.split('\n')
                logger.info(f"\n=== ALL LINES ({len(lines)} total) ===")
                for i, line in enumerate(lines[:50]):  # First 50 lines
                    line_clean = line.strip()
                    if line_clean:  # Only show non-empty lines
                        logger.info(f"Line {i:2d}: {repr(line_clean)}")
                
                if len(lines) > 50:
                    logger.info(f"... and {len(lines) - 50} more lines")
                
                break  # Only analyze first page for debugging
                
    except Exception as e:
        logger.error(f"Error during PDF debug: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_extraction.py <path_to_pdf_file>")
        sys.exit(1)
    
    pdf_file_path = sys.argv[1]
    debug_pdf_extraction(pdf_file_path)