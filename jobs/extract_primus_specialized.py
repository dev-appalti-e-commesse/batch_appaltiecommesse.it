import os
import re
import json

from dotenv import load_dotenv
import pdfplumber
import google.generativeai as genai
import concurrent.futures
from tqdm import tqdm
import sys
from typing import List, Dict, Optional, Tuple
import logging

# Load environment variables
load_dotenv()

# Configuration
API_MODEL_NAME = "gemini-1.5-pro-latest"
MAX_WORKERS = 1  # Reduced for more stable processing

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Gemini API
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file or environment variables.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(API_MODEL_NAME)
    logger.info("Gemini API initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    sys.exit(1)


class PrimusWorkItem:
    """Data class for a Primus work item"""
    def __init__(self):
        self.progressive_number: Optional[int] = None
        self.reference_code: Optional[str] = None
        self.description: Optional[str] = None
        self.quantity: Optional[float] = None
        self.unit_price: Optional[float] = None
        self.unit_of_measurement: Optional[str] = None
        self.raw_text: str = ""
        
    def to_dict(self) -> Dict:
        return {
            "progressiveNumber": self.progressive_number,
            "referenceCode": self.reference_code,
            "description": self.description,
            "quantity": self.quantity,
            "unitPrice": self.unit_price,
            "unitOfMeasurement": self.unit_of_measurement
        }
    
    def is_valid(self) -> bool:
        """Check if this work item has essential data"""
        return (self.progressive_number is not None and 
                self.description is not None and 
                len(self.description.strip()) > 10)


class PrimusPDFExtractor:
    """Specialized extractor for Primus PDF layouts"""
    
    def __init__(self):
        self.junk_patterns = [
            r'^pag\.\s*\d+$',
            r'^riporto\s*$',
            r'^a\s*riportare\s*$', 
            r'^totale\s*€',
            r'^data\s*:',
            r'^firma\s*:',
            r'^\s*€\s*[\d,\.]+\s*$',
            r'parziale\s+s\d{2}-s\d{2}',
            r'rieplogo\s+super\s+categorie',
            r'^num\.?\s*ord\.?\s*tariffa\s*$',
            r'^designazione\s+dei\s+lavori\s*$',
            r'^dimensioni\s*$',
            r'^importi\s*$',
            r'^quantità\s*$',
            r'^unitario\s*$',
            r'^lavori\s+a\s+(corpo|misura)\s*$',
            r'^piano\s+terzo\s*$',
            r'^opere\s+edili\s*$',
            r'^\s*[a-z]{2,}\s+[a-z]{2,}\s*$'  # Generic two-word headers
        ]
        
    def is_junk_line(self, text: str) -> bool:
        """Identifies and filters out common header, footer, or non-item lines (from universal extractor)"""
        text_lower = text.strip().lower()
        if not text_lower:
            return True
        
        junk_patterns = [
            r'^pag\.\s*\d+$',
            r'^r i p o r t o$',
            r'^committente:',
            r'^a r i p o r t a r e',
            r'd i m e n s i o n i',
            r'i m p o r t i',
            r'parziale s\d{2}-s\d{2}',
            r'rieplogo super categorie',
            r'^via\s*\.{3,}',
            r'^num\.ord\.',
            # DO NOT remove these lines - we need them for format detection!
            # r'^designazione dei lavori',
            # r'^tariffa$',
            r'^quantità$',
            r'^par\.ug\.',
            r'^lung\.',
            r'^larg\.',
            r'^h/peso',
            r'^unitario',
            r'^totale$'
        ]
        
        for pattern in junk_patterns:
            if re.search(pattern, text_lower):
                return True
                
        return False
    
    def normalize_text_line(self, line: str) -> str:
        """Normalize text line for consistent cross-platform parsing"""
        if not line:
            return line
        
        # Normalize spacing around common separators
        line = re.sub(r'\s*/\s*', '/', line)  # "1 / 1" -> "1/1"
        line = re.sub(r'\s*-\s*', '-', line)  # "A - B" -> "A-B"
        line = re.sub(r'\s+', ' ', line)      # Multiple spaces -> single space
        line = line.strip()
        
        return line
    
    def extract_work_item_chunks(self, pdf_path: str) -> List[str]:
        """Extract work item chunks using proven universal extractor logic"""
        logger.info(f"Reading, cleaning, and parsing PDF: {pdf_path}")
        
        full_document_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Opened PDF with {len(pdf.pages)} pages")
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
                        if page_text:
                            # Clean and normalize lines for consistent cross-platform parsing
                            cleaned_lines = []
                            for line in page_text.split('\n'):
                                if not self.is_junk_line(line):
                                    normalized_line = self.normalize_text_line(line)
                                    if normalized_line:  # Only add non-empty normalized lines
                                        cleaned_lines.append(normalized_line)
                            full_document_text += "\n".join(cleaned_lines) + "\n"
                            logger.debug(f"Extracted {len(cleaned_lines)} lines from page {i+1}")
                        else:
                            logger.warning(f"No text extracted from page {i+1}")
                    except Exception as e:
                        logger.error(f"Error extracting text from page {i+1}: {e}")
                        continue

            # Check if this is a Primus format with TARIFFA/DESIGNAZIONE columns
            tariffa_found = "TARIFFA" in full_document_text
            designazione_found = "DESIGNAZIONE DEI LAVORI" in full_document_text
            logger.info(f"Format detection: TARIFFA={tariffa_found}, DESIGNAZIONE DEI LAVORI={designazione_found}")
            
            # DEBUG: Show first 1000 characters of extracted text
            logger.info(f"DEBUG - First 1000 chars of extracted text: {repr(full_document_text[:1000])}")
            
            # DEBUG: Show first 20 lines after cleaning
            lines_sample = full_document_text.split('\n')[:20]
            logger.info(f"DEBUG - First 20 lines after cleaning:")
            for i, line in enumerate(lines_sample):
                if line.strip():
                    logger.info(f"  Line {i:2d}: {repr(line.strip())}")
            
            if (tariffa_found and designazione_found):
                logger.info("Detected Primus format - trying Primus extraction methods")
                
                # First try the specialized TARIFFA/DESIGNAZIONE method
                primus_chunks = self.extract_primus_format_chunks(full_document_text)
                if primus_chunks and len(primus_chunks) > 200:  # Higher threshold - need many chunks for large PDFs
                    logger.info(f"Primus method returned {len(primus_chunks)} chunks")
                    return primus_chunks
                else:
                    logger.warning(f"Primus method returned only {len(primus_chunks) if primus_chunks else 0} chunks")
                
                # Try the fraction format method
                fraction_chunks = self.extract_fraction_format_chunks(full_document_text)
                if fraction_chunks and len(fraction_chunks) > 200:  # Higher threshold - need many chunks for large PDFs
                    logger.info(f"Fraction format method returned {len(fraction_chunks)} chunks")
                    return fraction_chunks
                else:
                    logger.warning(f"Fraction method returned only {len(fraction_chunks) if fraction_chunks else 0} chunks")
                
                logger.warning("Both specialized Primus methods returned insufficient chunks, falling back to universal patterns")

            # Try multiple patterns to identify work item starts (fallback for other Primus variants)
            patterns_to_try = [
                # Pattern 1: "1 / 17" format but only split when followed by another fraction pattern
                r'(?=\n\d+\s*/\s*\d+\s+[A-Za-z])',  # Only split when there's text after the fraction 
                # Pattern 2: Just number at start of line BUT exclude 3-digit reference code endings
                r'(?=\n(?!\d{3}\s)\d+\s+[A-Z])',
                # Pattern 3: Number followed by tariff code
                r'(?=\n\d+\s+\d+\.\w+)',
            ]
            
            best_chunks = []
            best_count = 0
            
            for pattern in patterns_to_try:
                try:
                    item_start_pattern = re.compile(pattern)
                    all_chunks = item_start_pattern.split(full_document_text)
                    
                    # Filter chunks that contain "SOMMANO" (indicating complete work items)
                    valid_chunks = [
                        chunk.strip() for chunk in all_chunks 
                        if chunk.strip() and "SOMMANO" in chunk and len(chunk.strip()) > 50
                    ]
                    
                    logger.info(f"Pattern '{pattern}' found {len(valid_chunks)} chunks")
                    
                    if len(valid_chunks) > best_count:
                        best_chunks = valid_chunks
                        best_count = len(valid_chunks)
                        
                except Exception as e:
                    logger.info(f"Pattern '{pattern}' failed: {e}")
                    continue
            
            if not best_chunks:
                # Fallback: Split by "SOMMANO" and try to reconstruct
                logger.info("Trying fallback method: splitting by SOMMANO")
                lines = full_document_text.split('\n')
                chunks = []
                current_chunk = []
                
                for line in lines:
                    current_chunk.append(line)
                    if "SOMMANO" in line and len(current_chunk) > 5:
                        chunk_text = '\n'.join(current_chunk)
                        # Look for a number at the start of the chunk
                        if re.search(r'^\d+\s+', chunk_text.strip()):
                            chunks.append(chunk_text.strip())
                        current_chunk = []
                
                best_chunks = chunks
            
            logger.info(f"Successfully identified {len(best_chunks)} potential work item chunks after cleaning.")
            
            # Show sample of what we found
            if best_chunks:
                logger.info("Sample chunks found:")
                for i, chunk in enumerate(best_chunks[:3]):
                    first_line = chunk.split('\n')[0].strip()[:100]
                    logger.info(f"  Chunk {i+1}: {first_line}...")
            
            return best_chunks
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            return []

    def extract_primus_format_chunks(self, full_document_text: str) -> List[str]:
        """Extract work items from Primus format with TARIFFA/DESIGNAZIONE columns
        Handles split reference codes properly (e.g., 01.A01.A65. followed by 010)"""
        logger.info("🔍 PRIMUS METHOD: Starting Primus-specific extraction")
        
        lines = full_document_text.split('\n')
        chunks = []
        current_chunk = []
        in_data_section = False
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
                
            # Start collecting data after we see table headers
            if ("DESIGNAZIONE DEI LAVORI" in line_stripped or "LAVORI A CORPO" in line_stripped):
                in_data_section = True
                logger.info(f"🔍 PRIMUS METHOD: Found data section start at line {line_num}")
                continue
                
            if not in_data_section:
                continue
                
            # Debug: show first few lines we're analyzing
            if line_num <= 20:
                logger.info(f"🔍 PRIMUS METHOD: Analyzing line {line_num}: {repr(line_stripped)}")
                
            # Look for MAIN work item starts: number + description or number + reference code
            # Pattern: "1 Nolo di autocarro...", "2 Nolo di piattaforma...", "5 Scavo a sezione..."
            # BUT NOT 3-digit reference code endings like "005", "010", "015"
            
            # First check if this is a 3-digit reference code ending (should NOT start new item)
            is_reference_code_ending = re.match(r'^(\d{3})(\s|$)', line_stripped)
            
            if is_reference_code_ending:
                # This is a reference code ending like "005", "010", "015"
                # Add it to the current chunk, don't start a new one
                if current_chunk:
                    current_chunk.append(line_stripped)
                
            else:
                # Check for actual work item starts - multiple patterns:
                # 1. Traditional: "1 Nolo di...", "2 Demolizione..."
                # 2. Fraction format: "1/17", "2/18", "3/19" (extract just the first number)
                # 3. Special cases: items that start with lowercase
                
                # Robust patterns - text is now normalized so "1 / 1" becomes "1/1"
                main_item_match = re.match(r'^([1-9]\d?)\s+([A-Z][a-zA-Z]{3,})', line_stripped)
                # Match fraction format after normalization: "1/1", "2/2", etc.
                fraction_match = re.match(r'^([1-9]\d?)/\d+', line_stripped)
                special_case_match = re.match(r'^(13|37|74)\s+(cemento|metalli|legno)', line_stripped)
                
                if main_item_match or fraction_match or special_case_match:
                    logger.info(f"🔍 PRIMUS METHOD: FOUND MATCH! Line: {repr(line_stripped[:100])}")
                    if main_item_match:
                        item_number = int(main_item_match.group(1))
                        descriptive_word = main_item_match.group(2)
                        valid_item = (item_number <= 100 and 
                                    not descriptive_word.lower().startswith(('circuit', 'linea', 'sotto')))
                        logger.info(f"🔍 PRIMUS METHOD: Main item match - number: {item_number}, word: {descriptive_word}")
                    elif fraction_match:
                        item_number = int(fraction_match.group(1))
                        valid_item = True  # Fraction patterns are always valid work items
                        logger.info(f"🔍 PRIMUS METHOD: Fraction match - number: {item_number}")
                    else:  # special_case_match
                        item_number = int(special_case_match.group(1))
                        valid_item = True
                        logger.info(f"🔍 PRIMUS METHOD: Special case match - number: {item_number}")
                    
                    if valid_item:
                        # If we have a previous chunk, save it
                        if current_chunk:
                            chunk_text = '\n'.join(current_chunk).strip()
                            if len(chunk_text) > 30:  # Don't require SOMMANO - some items might not have it
                                chunks.append(chunk_text)
                        
                        # Start new chunk with the current line
                        current_chunk = [line_stripped]
                        logger.debug(f"Started new work item {item_number}: {line_stripped[:50]}...")
                    else:
                        # This is likely a continuation line, add to current chunk
                        if current_chunk:
                            current_chunk.append(line_stripped)
                
                # Handle other continuation lines
                elif current_chunk:
                    # Include meaningful continuation lines
                    if (line_stripped and 
                        not line_stripped.startswith('A R I P O R T A R E') and
                        not line_stripped.startswith('R I P O R T O') and
                        not line_stripped.startswith('COMMITTENTE') and
                        not line_stripped.startswith('Pag.')):
                        current_chunk.append(line_stripped)
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if len(chunk_text) > 30:
                chunks.append(chunk_text)
        
        logger.info(f"🔍 PRIMUS METHOD: Completed extraction with {len(chunks)} work items")
        
        # Debug: show a few sample chunks
        if chunks:
            logger.info("🔍 PRIMUS METHOD: Sample chunks found:")
            for i, chunk in enumerate(chunks[:5]):
                first_line = chunk.split('\n')[0][:100]
                logger.info(f"  Chunk {i+1}: {first_line}...")
        else:
            logger.warning("🔍 PRIMUS METHOD: No chunks found!")
        
        return chunks
        
    def extract_fraction_format_chunks(self, full_document_text: str) -> List[str]:
        """Extract work items from Primus fraction format (like "19/35 4033", "20/36 4036")
        Pattern: {progressive}/{reference} {reference_code} followed by description and SOMMANO"""
        logger.info("🔍 FRACTION METHOD: Starting fraction format extraction")
        
        lines = full_document_text.split('\n')
        chunks = []
        current_chunk = []
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Look for fraction pattern work items (like "19/35 4033", "20/36 4036", "1/1 Rimozione")
            # Pattern: progressive/reference [reference_code OR description] (text is normalized)
            fraction_match = re.match(r'^(\d+)/\d+(?:\s+\d+|\s+[A-Z])', line_stripped)
            
            if fraction_match:
                # If we have a previous chunk, save it
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk).strip()
                    if len(chunk_text) > 50:  # Don't require SOMMANO - some items might not have it
                        chunks.append(chunk_text)
                
                # Start new chunk with the fraction line
                current_chunk = [line_stripped]
                progressive_num = fraction_match.group(1)
                logger.debug(f"🔍 FRACTION METHOD: Started work item {progressive_num}: {line_stripped[:50]}...")
                
            elif current_chunk:
                # Add continuation lines to current chunk
                current_chunk.append(line_stripped)
                
                # If we hit SOMMANO, this chunk is complete - save and start fresh
                if "SOMMANO" in line_stripped:
                    chunk_text = '\n'.join(current_chunk).strip()
                    if len(chunk_text) > 50:
                        chunks.append(chunk_text)
                        logger.debug(f"🔍 FRACTION METHOD: Completed chunk with SOMMANO")
                    current_chunk = []
        
        # Handle the last chunk if it exists
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if len(chunk_text) > 50:
                chunks.append(chunk_text)
        
        logger.info(f"🔍 FRACTION METHOD: Completed extraction with {len(chunks)} work items")
        
        # Debug: show a few sample chunks
        if chunks:
            logger.info("🔍 FRACTION METHOD: Sample chunks found:")
            for i, chunk in enumerate(chunks[:5]):
                first_line = chunk.split('\n')[0][:100]
                logger.info(f"  Chunk {i+1}: {first_line}...")
        else:
            logger.warning("🔍 FRACTION METHOD: No chunks found!")
        
        return chunks
        
    def call_gemini_for_extraction(self, text_chunk: str) -> Optional[Dict]:
        """Extract structured data from work item using Gemini with universal extractor prompt"""
        
        prompt = f"""
        ### **Context**
        You are analyzing a **computo metrico estimativo for construction works**. The document
        can be in multiple formats:
        1. Traditional format with progressive numbers, tariff codes, work descriptions, and "SOMMANO"
        2. Structured table format with columns: "Numero d'ordine Listino Prezzi", "Descrizione", "u.m.", "Quantità", "prezzo unitario"
        3. Computo metrico table format with columns: "N.", "Rif.", "Descrizione", "Quantità", "Prezzo unitario", "Prezzo complessivo"
        4. Allegato table format with columns: "No.", "TARIFFA", "DESIGNAZIONE DEI LAVORI", "Quantità", "IMPORTI"
        5. Primus format with TARIFFA/DESIGNAZIONE columns and "SOMMANO" totals
        ---
        ### **Role**
        Act as an **AI assistant specialized in structured data extraction from computi metrici
        edilizi**, with strict attention to fidelity to the original text and correct transformation into
        JSON format.
        ---
        ### **Action**
        * Identify the **work item** in the provided text.
        * Extract and normalize the data according to the schema below.
        * Do not modify, interpret, or summarize: always keep the exact original values.
        * If a field is missing, assign the value `null`.
        ---
        ### **Format**
        All extracted data must be returned as JSON using the following schema:
        ```json
        {{
        "progressiveNumber": number,
        "referenceCode": "codice",
        "description": "detailed description of the work item",
        "quantity": number,
        "unitPrice": number,
        "unitOfMeasurement": "unità di misura"
        }}
        ```
        #### Extraction rules
        1. **progressiveNumber**
        * Extract the progressive number at the start (1-100).
        * If written as "2/2" or similar, take only the first integer (e.g., 2).
        * Always return an integer.
        
        2. **referenceCode**
        * Look for alphanumeric codes like "01.P24.C60.0", "07.A20.T30.015".
        * Extract codes like "A 3.01.9", "G 1.01.1" from patterns like "1 A 3.01.9".
        * If you cannot find a clear code, use `null`.
        
        3. **description**
        * Extract text before "SOMMANO" or calculations.
        * Include all relevant details but exclude measurement calculations and price calculations.
        * Preserve the essence of the description but clean up formatting.
        
        4. **quantity**
        * Extract the numeric value that appears after "SOMMANO".
        * Convert to a decimal number (e.g., 6,00 → 6.0, 1,65 → 1.65).
        
        5. **unitPrice**
        * Extract the unit price before the final total.
        * Convert to a number, removing currency symbols.
        
        6. **unitOfMeasurement**
        * Extract the unit after "SOMMANO" (e.g., h, m², m³, kg, cad).
        * Keep the exact Italian notation.
        ---
        ### **Tone**
        * **Precise, technical, and rule-based**.
        * No interpretation, no reformulation.
        * Focus exclusively on **accurate extraction and correct formatting** of the data.
        
        **IMPORTANT**: If the provided text does not look like a detailed work item description (e.g., it is just a header or a random line), return the single word "REJECT" instead of a JSON object.

        Text to analyze:
        ---
        {text_chunk}
        ---
        """
        
        try:
            generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
            response = model.generate_content(prompt, generation_config=generation_config, request_options={"timeout": 60})
            
            if "REJECT" in response.text:
                return None
                
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Error in Gemini extraction: {e}")
            return None


def main(pdf_path: str):
    """Main extraction process for Primus PDFs using universal extractor approach"""
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return
    
    logger.info(f"Starting Primus extraction for: {pdf_path}")
    
    # Initialize extractor
    extractor = PrimusPDFExtractor()
    
    # Extract work item chunks using universal extractor logic
    work_item_chunks = extractor.extract_work_item_chunks(pdf_path)
    if not work_item_chunks:
        logger.error("No work item chunks identified")
        return
    
    logger.info(f"Processing {len(work_item_chunks)} work item chunks with Gemini...")
    
    # Process chunks with Gemini using universal extractor approach
    extracted_items = []
    successful_extractions = 0
    failed_extractions = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_chunk = {
            executor.submit(extractor.call_gemini_for_extraction, chunk): chunk 
            for chunk in work_item_chunks
        }
        
        for i, future in enumerate(tqdm(concurrent.futures.as_completed(future_to_chunk), 
                          total=len(work_item_chunks), 
                          desc="Processing work items")):
            try:
                chunk = future_to_chunk[future]
                result = future.result()
                
                # Debug: Show first few chunks to understand the issue
                if i < 5:
                    logger.info(f"=== DEBUG CHUNK {i+1} ===")
                    logger.info(f"Chunk text (first 300 chars): {chunk[:300]}...")
                    logger.info(f"Extraction result: {result}")
                    logger.info("=" * 50)
                
                if result and isinstance(result, dict):
                    extracted_items.append(result)
                    successful_extractions += 1
                else:
                    failed_extractions += 1
                    
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                failed_extractions += 1
    
    # Sort by progressive number for final output (handle None values)
    extracted_items.sort(key=lambda x: x.get('progressiveNumber') or 999)
    
    # Results summary
    logger.info(f"Extraction Results:")
    logger.info(f"  Total chunks processed: {len(work_item_chunks)}")
    logger.info(f"  Successful extractions: {successful_extractions}")
    logger.info(f"  Failed extractions: {failed_extractions}")
    logger.info(f"  Final work items: {len(extracted_items)}")
    
    # Show sample results
    if extracted_items:
        logger.info(f"Sample extracted items (first 3):")
        for i, item in enumerate(extracted_items[:3]):
            prog_num = item.get('progressiveNumber', 'N/A')
            ref_code = item.get('referenceCode', 'N/A')
            desc = item.get('description', 'N/A')
            if isinstance(desc, str) and len(desc) > 80:
                desc = desc[:80] + "..."
            logger.info(f"  Item {i+1}: #{prog_num} [{ref_code}] - {desc}")
    
    # Save results in universal extractor format
    final_output = {"workItems": extracted_items}
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_path = f"{base_name}_extracted_primus_specialized.json"
    
    logger.info(f"Saving results to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    logger.info("Primus extraction completed successfully!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_primus_specialized.py <path_to_pdf_file>")
        sys.exit(1)
    
    pdf_file_path = sys.argv[1]
    main(pdf_file_path)
