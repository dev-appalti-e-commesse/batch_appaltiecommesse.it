#!/usr/bin/env python3
import os
import sys
import json
import logging
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse, unquote
import os
from bson import ObjectId
from bson.errors import InvalidId
import boto3
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.italian_time import get_italian_time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('MetricComputation')

# MongoDB configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'appalti_e_commesse'

# AWS S3 configuration
AWS_REGION = 'eu-north-1'
s3_client = boto3.client('s3', region_name=AWS_REGION)

# Email configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', SMTP_USER)


def format_email_html(body_content: str, to_email: str) -> str:
    """Format email content with HTML template and Gembai branding"""
    logo_url = "https://gembai.it/assets/images/logo_Gembai-appalti_e_commesse.png"

    # Convert plain text with newlines to HTML paragraphs
    html_content = ""
    for line in body_content.split('\n'):
        if line.strip():
            html_content += f"<p>{line}</p>"

    html = f"""<!DOCTYPE html>
    <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Open+Sans&display=swap');
            </style>
        </head>
        <body>
            <div style="font-family: 'Open Sans', sans-serif; max-width:600px; margin:0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="{logo_url}" alt="Gembai Logo" style="height: 40px;">
                </div>

                <div style="margin-bottom: 20px;">
                    <p>Ciao!</p>
                </div>

                <div style="margin-bottom: 20px;">
                    {html_content}
                </div>

                <div style="margin-top: 30px;">
                    <p>Il Team di Gembai</p>
                </div>

                <div style="margin-top: 20px;">
                    <span style="font-size: 12px; color: #666;">
                        Questa email è stata inviata a {to_email}. Se non hai richiesto tu questa operazione, per favore contattaci immediatamente a info@appaltiecommesse.it
                    </span>
                </div>
            </div>
        </body>
    </html>"""

    return html


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email notification to user"""
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning(f"Email credentials not configured, skipping email to {to_email}")
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = f"Gembai <{EMAIL_FROM}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        # Create HTML version
        html_body = format_email_html(body, to_email)

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)

        text = msg.as_string()
        server.sendmail(EMAIL_FROM, to_email, text)
        server.quit()

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def get_header(header_name: str) -> Optional[str]:
    """Get header value from environment variable"""
    env_var = header_name.upper().replace('-', '_')
    return os.environ.get(env_var)


def get_param(param_name: str) -> Optional[str]:
    """Get parameter value from JOB_PARAMS environment variable"""
    job_params = os.environ.get('JOB_PARAMS', '{}')
    try:
        params = json.loads(job_params)
        return params.get(param_name)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JOB_PARAMS: {job_params}")
        return None


def validate_objectid(id_str: str) -> bool:
    """Validate if string is a valid MongoDB ObjectId"""
    if id_str is None or not isinstance(id_str, str):
        return False
    try:
        ObjectId(id_str)
        return True
    except (InvalidId, TypeError):
        return False


def download_s3_file(s3_url: str) -> Optional[str]:
    """Download file from S3 URL to temporary file"""
    try:
        # Parse S3 URL
        parsed = urlparse(s3_url)
        
        if parsed.scheme == 's3':
            # s3://bucket/key format
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
        elif 's3.amazonaws.com' in parsed.netloc or 's3' in parsed.netloc:
            # https://bucket.s3.region.amazonaws.com/key format
            parts = parsed.netloc.split('.')
            bucket = parts[0]
            key = parsed.path.lstrip('/')
        else:
            # Try to extract from path
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) == 2:
                bucket = path_parts[0]
                key = path_parts[1]
            else:
                raise ValueError(f"Cannot parse S3 URL: {s3_url}")
        
        logger.info(f"Downloading from S3 - Bucket: {bucket}, Key: {key}")
        # URL decode the key to handle special characters like spaces
        key = unquote(key)
        logger.info(f"Downloading from S3 - Bucket: {bucket}, Decoded Key: {key}")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        temp_file.close()
        
        # Download file from S3
        s3_client.download_file(bucket, key, temp_path)
        logger.info(f"Downloaded S3 file to: {temp_path}")
        
        return temp_path
        
    except Exception as e:
        logger.error(f"Failed to download S3 file: {str(e)}")
        return None


def validate_and_normalize_workitems(work_items: List[Dict]) -> None:
    """
    Normalizza e valida workItems secondo le regole specificate:
    - progressiveNumber: assegnato automaticamente (1, 2, 3...)
    - referenceCode: OBBLIGATORIO (string)
    - description: opzionale (string o null)
    - quantity: opzionale (default 0)
    - unitPrice: opzionale (default 0)
    - unitOfMeasurement: opzionale (string o null)
    """
    
    if not isinstance(work_items, list):
        raise ValueError(f"workItems deve essere un array, ricevuto: {type(work_items)}")
    
    if len(work_items) == 0:
        raise ValueError("workItems è un array vuoto")
    
    # Normalizza e valida ogni workItem
    for i, item in enumerate(work_items):
        if not isinstance(item, dict):
            raise ValueError(f"workItem {i} deve essere un oggetto, ricevuto: {type(item)}")
        
        # 1. Assegna progressiveNumber (intero progressivo da 1)
        item['progressiveNumber'] = i + 1
        """
        # 2. Verifica referenceCode OBBLIGATORIO
        if 'referenceCode' not in item or not item['referenceCode']:
            raise ValueError(f"workItem {i}: referenceCode è obbligatorio")
        
        if not isinstance(item['referenceCode'], str):
            raise ValueError(f"workItem {i}: referenceCode deve essere string, ricevuto {type(item['referenceCode'])}")
        """
        
        # 3. Gestisci description (opzionale)
        if 'description' not in item:
            item['description'] = None
        elif item['description'] is not None and not isinstance(item['description'], str):
            raise ValueError(f"workItem {i}: description deve essere string o null, ricevuto {type(item['description'])}")
        
        # 4. Gestisci quantity (default 0 se mancante)
        if 'quantity' not in item or item['quantity'] is None:
            item['quantity'] = 0
        elif not isinstance(item['quantity'], (int, float)):
            raise ValueError(f"workItem {i}: quantity deve essere number, ricevuto {type(item['quantity'])}")
        
        # 5. Gestisci unitPrice (default 0 se mancante)
        if 'unitPrice' not in item or item['unitPrice'] is None:
            item['unitPrice'] = 0
        elif not isinstance(item['unitPrice'], (int, float)):
            raise ValueError(f"workItem {i}: unitPrice deve essere number, ricevuto {type(item['unitPrice'])}")
        
        # 6. Gestisci unitOfMeasurement (opzionale)
        if 'unitOfMeasurement' not in item:
            item['unitOfMeasurement'] = None
        elif item['unitOfMeasurement'] is not None and not isinstance(item['unitOfMeasurement'], str):
            raise ValueError(f"workItem {i}: unitOfMeasurement deve essere string o null, ricevuto {type(item['unitOfMeasurement'])}")


def calculate_total_amount(work_items: List[Dict]) -> float:
    """
    Calcola il totale ottimizzato per heap minimo con ~10k oggetti complessi
    Replica esattamente la logica TypeScript fornita
    """
    if not work_items:
        return 0.0
    
    total = 0.0
    for item in work_items:
        # Accesso diretto per performance, con defaults corretti
        unit_price = item.get('unitPrice', 0) or 0
        quantity = item.get('quantity', 0) or 0
        unit_of_measurement = item.get('unitOfMeasurement') or ''
        
        # Logica esatta del TypeScript
        if unit_of_measurement == '%':
            item_value = unit_price * (quantity / 100.0)
        else:
            item_value = quantity * unit_price
        
        total += item_value
    
    return total


def process_pdf_with_primus(pdf_path: str) -> Optional[Dict]:
    """Call extract_primus_specialized.py to process PDF"""
    try:
        # Verify PDF file exists and has content
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return None
            
        file_size = os.path.getsize(pdf_path)
        logger.info(f"PDF file size: {file_size} bytes")
        
        if file_size == 0:
            logger.error("PDF file is empty")
            return None
            
        # Check if it's actually a PDF
        with open(pdf_path, 'rb') as f:
            header = f.read(5)
            if not header.startswith(b'%PDF'):
                logger.error(f"File does not appear to be a PDF. Header: {header}")
                return None
        
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        primus_script = os.path.join(script_dir, 'extract_primus_specialized.py')
        
        logger.info(f"Running extraction script: {primus_script}")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Call the script with real-time output streaming
        import threading
        import queue
        import time

        def read_output(pipe, output_queue, pipe_name):
            """Read output from pipe and put in queue"""
            try:
                for line in iter(pipe.readline, ''):
                    if line:
                        output_queue.put((pipe_name, line.rstrip()))
                pipe.close()
            except Exception as e:
                output_queue.put(('error', f"Error reading {pipe_name}: {e}"))
            finally:
                output_queue.put((pipe_name, None))  # Signal end

        # Start subprocess
        process = subprocess.Popen(
            [sys.executable, primus_script, pdf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=script_dir,
            bufsize=1,
            universal_newlines=True
        )

        # Create queues and threads for reading output
        output_queue = queue.Queue()

        stdout_thread = threading.Thread(
            target=read_output,
            args=(process.stdout, output_queue, 'stdout')
        )
        stderr_thread = threading.Thread(
            target=read_output,
            args=(process.stderr, output_queue, 'stderr')
        )

        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Track output and timing
        all_stdout = []
        all_stderr = []
        start_time = time.time()
        timeout_seconds = 14400  # 4 hours
        streams_ended = {'stdout': False, 'stderr': False}

        # Process output in real-time
        try:
            while not all(streams_ended.values()) or not output_queue.empty():
                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    process.kill()
                    logger.error("Primus extraction timed out")
                    return None

                try:
                    # Get output with short timeout to allow timeout checking
                    pipe_name, line = output_queue.get(timeout=1.0)

                    if line is None:
                        # Stream ended
                        streams_ended[pipe_name] = True
                        continue

                    # Store output for later analysis
                    if pipe_name == 'stdout':
                        all_stdout.append(line)
                    elif pipe_name == 'stderr':
                        all_stderr.append(line)

                    # Log immediately to CloudWatch
                    if pipe_name == 'stdout':
                        if line.startswith("[EXTRACTION]"):
                            logger.info(line)
                        elif line.strip():
                            logger.info(f"Extraction: {line}")
                    elif pipe_name == 'stderr':
                        if line.strip():
                            logger.warning(f"Extraction stderr: {line}")

                except queue.Empty:
                    # No output available, continue to check timeout
                    continue

            # Wait for process to complete
            returncode = process.wait()

            # Log summary
            logger.info(f"Extraction completed with return code: {returncode}")
            logger.info(f"Total stdout lines: {len(all_stdout)}")
            logger.info(f"Total stderr lines: {len(all_stderr)}")

            if returncode != 0:
                logger.error(f"Primus extraction failed with return code {returncode}")
                # Log last few lines for debugging
                if all_stderr:
                    logger.error("Last stderr lines:")
                    for line in all_stderr[-10:]:
                        logger.error(f"  {line}")
                return None

        except Exception as e:
            process.kill()
            logger.error(f"Error during extraction streaming: {str(e)}")
            return None
        finally:
            # Ensure threads complete
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
        
        # Read the output JSON file
        # The extract_primus_specialized.py saves the file in its working directory (script_dir)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(script_dir, f"{base_name}_extracted_primus_specialized.json")
        
        if not os.path.exists(output_path):
            logger.error(f"Output file not found: {output_path}")
            # List files in script directory for debugging
            logger.info(f"Files in script directory: {os.listdir(script_dir)[:20]}")
            return None
        
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Log the number of items found
        if 'workItems' in data:
            logger.info(f"Loaded {len(data['workItems'])} work items from extraction")
        else:
            logger.warning("No workItems key in extracted data")
        
        # Clean up the output file
        try:
            os.remove(output_path)
        except:
            pass
            
        return data
        
    except subprocess.TimeoutExpired:
        logger.error("Primus extraction timed out")
        return None
    except Exception as e:
        logger.error(f"Error processing PDF with Primus: {str(e)}")
        return None


def verify_document_exists(db_client: MongoClient, doc_type: str, doc_id: str) -> bool:
    """Verify if document exists in MongoDB"""
    try:
        db = db_client[DATABASE_NAME]
        
        # Choose collection based on type
        if doc_type == 'privateTender':
            collection = db['private_tenders']
        elif doc_type == 'metricComputation':
            collection = db['metric_computations']
        else:
            logger.error(f"Invalid document type: {doc_type}")
            return False
        
        # Query with lean() for performance
        document = collection.find_one(
            {'_id': ObjectId(doc_id)},
            {'_id': 1}  # Only fetch _id field
        )
        
        return document is not None
        
    except Exception as e:
        logger.error(f"Error verifying document: {str(e)}")
        return False


def split_pdf_by_sommano(pdf_path: str, s3_url: str, work_items: List[Dict]) -> Dict[int, Dict]:
    """Split PDF by SOMMANO keyword and upload splits to S3, returning mapping of work items to files"""
    try:
        import tempfile
        import shutil
        from pathlib import Path

        # Parse original S3 URL to get bucket and base key
        parsed = urlparse(s3_url)
        if parsed.scheme == 's3':
            bucket = parsed.netloc
            original_key = parsed.path.lstrip('/')
        elif 's3.amazonaws.com' in parsed.netloc or 's3' in parsed.netloc:
            parts = parsed.netloc.split('.')
            bucket = parts[0]
            original_key = parsed.path.lstrip('/')
        else:
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) == 2:
                bucket = path_parts[0]
                original_key = path_parts[1]
            else:
                raise ValueError(f"Cannot parse S3 URL: {s3_url}")

        # Decode the key
        original_key = unquote(original_key)

        # Get directory and filename parts
        key_dir = os.path.dirname(original_key)
        original_filename = os.path.basename(original_key)
        base_name, ext = os.path.splitext(original_filename)

        logger.info(f"Splitting PDF: {original_filename}")

        # Create temporary directory for output
        temp_dir = tempfile.mkdtemp()
        output_dir = os.path.join(temp_dir, 'splits')
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Import the splitting function directly
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, script_dir)
            from extract_primus_specialized_split import crop_rows_by_keyword

            # Run the split function
            crop_rows_by_keyword(
                pdf_path=Path(pdf_path),
                out_dir=Path(output_dir),
                keyword="SOMMANO",
                dpi=144,
                left_margin=6.0,
                right_margin=6.0,
                extend_top=-4.0,
                extend_bottom=6.0,
                include_keyword_padding=8.0,
                make_zip=False
            )

            # Get all generated PNG files
            png_files = sorted([f for f in os.listdir(output_dir) if f.endswith('.png')])

            if not png_files:
                logger.warning("No split files generated")
                return {}

            logger.info(f"Generated {len(png_files)} split files")

            # Map each split to corresponding work item (1-based indexing)
            work_item_files = {}
            upload_date = datetime.now(timezone.utc)

            # Convert PNGs to PDFs and upload to S3
            for i, png_file in enumerate(png_files, 1):
                png_path = os.path.join(output_dir, png_file)

                # Convert PNG to PDF using PIL
                from PIL import Image
                img = Image.open(png_path)
                pdf_path = os.path.join(temp_dir, f"temp_{i}.pdf")
                img.save(pdf_path, "PDF")

                # Generate S3 key for split file
                split_filename = f"{base_name}_{i}.pdf"
                split_key = os.path.join(key_dir, split_filename) if key_dir else split_filename

                # Upload to S3 with proper content type
                logger.info(f"Uploading split {i}/{len(png_files)}: {split_filename}")
                s3_client.upload_file(
                    pdf_path,
                    bucket,
                    split_key,
                    ExtraArgs={'ContentType': 'application/pdf'}
                )

                # Use same URL format as original
                split_url = s3_url.replace('.pdf', f'_{i}.pdf')

                # Map to work item (splits are 1-indexed, work items progressiveNumber is 1-indexed)
                work_item_files[i] = {
                    'name': split_filename,
                    'fileUrl': split_url,
                    'uploadDate': upload_date
                }

                # Clean up temp PDF
                os.remove(pdf_path)

            logger.info(f"Successfully uploaded {len(work_item_files)} split files to S3")
            return work_item_files

        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    except Exception as e:
        logger.error(f"Error splitting PDF: {str(e)}")
        return {}


def update_work_items_with_files(db_client: MongoClient, doc_type: str, doc_id: str,
                                work_items: List[Dict], work_item_files: Dict[int, Dict]) -> bool:
    """Update work items with file information"""
    try:
        # Add file info to corresponding work items
        for work_item in work_items:
            progressive_num = work_item.get('progressiveNumber')
            if progressive_num and progressive_num in work_item_files:
                work_item['file'] = work_item_files[progressive_num]
                logger.info(f"Work item {progressive_num} linked to file: {work_item_files[progressive_num]['name']}")

        # Now update the document with work items that have file info
        return update_document(db_client, doc_type, doc_id, work_items, calculate_total_amount(work_items))

    except Exception as e:
        logger.error(f"Error updating work items with files: {str(e)}")
        return False


def update_document(db_client: MongoClient, doc_type: str, doc_id: str,
                   work_items: List[Dict], total_amount: float) -> bool:
    """Update document in MongoDB with workItems and totalAmount"""
    try:
        db = db_client[DATABASE_NAME]

        # Choose collection and field names based on type
        if doc_type == 'privateTender':
            collection = db['private_tenders']
            update_fields = {
                'tenderContent.workItems': work_items,
                'tenderContent.totalAmount': total_amount,
                'updatedAt': get_italian_time()
            }
        elif doc_type == 'metricComputation':
            collection = db['metric_computations']
            update_fields = {
                'content.workItems': work_items,
                'content.totalAmount': total_amount,
                'updatedAt': get_italian_time()
            }
        else:
            logger.error(f"Failed to update database - Invalid document type: {doc_type}")
            return False

        # Update document using $set for specific fields
        result = collection.update_one(
            {'_id': ObjectId(doc_id)},
            {'$set': update_fields}
        )

        if result.matched_count == 0:
            logger.error(f"Failed to update database - Document not found in {collection.name}: {doc_id}")
            return False
        elif result.modified_count == 0:
            logger.warning(f"Document not modified (may already have same values): {doc_id}")
            return True
        else:
            logger.info(f"Document updated successfully: {doc_id} (modified {result.modified_count} fields)")
            return True

    except Exception as e:
        logger.error(f"Failed to update database - MongoDB error in {collection.name if 'collection' in locals() else 'unknown'} for DocID {doc_id}: {str(e)}")
        return False


def run_primus_quality_check(pdf_path: str) -> Optional[Dict]:
    """Run extract_primus_specialized_quality.py on the PDF"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        quality_script = os.path.join(script_dir, 'extract_primus_specialized_quality.py')

        logger.info(f"Running quality check script: {quality_script}")

        # Modify the quality script to use the provided PDF path
        with open(quality_script, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # Replace the hardcoded path with the actual PDF path
        modified_content = script_content.replace(
            '"/Users/cto/Documents/enterprise/AIBF/_AIBF_CLIENTI/GEMBAI/computi/PRIMUS/Mun_VII_CIG_7720106103_03_Computo_Metrico_Estimativo - 22 pagine.pdf"',
            f'"{pdf_path}"'
        )

        # Create a temporary modified script
        temp_script = os.path.join(script_dir, 'temp_quality_check.py')
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        try:
            # Run the modified script
            result = subprocess.run(
                [sys.executable, temp_script],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
                cwd=script_dir
            )

            if result.returncode == 0:
                # Parse the JSON output
                quality_result = json.loads(result.stdout.strip())
                logger.info(f"Quality check result: {json.dumps(quality_result, indent=2)}")
                return quality_result
            else:
                logger.error(f"Quality check failed with return code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return None

        finally:
            # Clean up temporary script
            if os.path.exists(temp_script):
                os.remove(temp_script)

    except Exception as e:
        logger.error(f"Error running quality check: {str(e)}")
        return None


def main():
    logger.info("Starting MetricComputation service")

    job_id = os.environ.get('AWS_BATCH_JOB_ID', 'local-test')

    # Initialize variables for cleanup
    temp_file_path = None
    mongo_client = None

    try:
        # Get parameters from environment
        user_email = get_header('x-user-email')
        user_company_id = get_header('x-user-company-id')
        s3_url = get_param('s3Url')
        doc_id = get_param('id')
        title = get_param('title')
        doc_type = get_param('type')

        # Extract filename from S3 URL
        filename = os.path.basename(urlparse(s3_url).path) if s3_url else 'documento'
        
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Headers: email={user_email}, company={user_company_id}")
        logger.info(f"Params: s3Url={s3_url}, id={doc_id}, title={title}, type={doc_type}")
        
        # Validate required parameters
        if not all([user_email, s3_url, doc_id, title, doc_type]):
            raise ValueError("Missing required parameters")
        
        # Validate ObjectId
        if not validate_objectid(doc_id):
            error_msg = f"Invalid MongoDB ObjectId: {doc_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Connect to MongoDB
        logger.info("Connecting to MongoDB...")
        mongo_client = MongoClient(MONGO_URI)
        
        # Verify document exists
        logger.info(f"Verifying document exists: {doc_id} in {doc_type}")
        if not verify_document_exists(mongo_client, doc_type, doc_id):
            error_msg = f"Document not found: {doc_id} in {doc_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Download file from S3
        logger.info(f"Downloading file from S3: {s3_url}")
        temp_file_path = download_s3_file(s3_url)
        if not temp_file_path:
            error_msg = "Failed to download file from S3"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Run quality check first
        logger.info("Running PDF quality check...")
        quality_result = run_primus_quality_check(temp_file_path)
        if quality_result:
            print(f"QUALITY CHECK RESULT: {json.dumps(quality_result, indent=2)}")

            # Check quality ratio threshold
            quality_ratio = quality_result.get('quality_ratio', 0)
            if quality_ratio < 0.95:
                # Determine document type labels
                if doc_type == 'privateTender':
                    doc_label = "della gara"
                else:  # metricComputation
                    doc_label = "del computo metrico"

                error_msg = f"Cannot extract file because low quality (ratio: {quality_ratio})"
                logger.error(error_msg)

                # Send error email
                email_subject = f"Impossibile digitalizzare computo metrico da file {filename} {doc_label} {title}"
                email_body = f"Impossibile digitalizzare computo metrico da file {filename} {doc_label} {title} a causa della bassa qualità del file. Riprovare con un altro file"
                send_email(user_email, email_subject, email_body)

                # Log final result with failure status
                result = {
                    'job_id': job_id,
                    'job_type': 'MetricComputation',
                    'status': 'failed',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'document_id': doc_id,
                    'document_type': doc_type,
                    'error': 'low_quality_pdf',
                    'quality_ratio': quality_ratio,
                    'message': error_msg
                }
                logger.info(f"Job terminated due to low quality PDF: {json.dumps(result, indent=2)}")

                # Exit gracefully with status 0 (successful termination, but job marked as failed)
                sys.exit(0)
        else:
            logger.warning("Quality check failed, continuing with extraction...")

        # Process PDF with Primus extractor
        logger.info("Processing PDF with Primus extractor...")
        extraction_result = process_pdf_with_primus(temp_file_path)
        
        if not extraction_result or 'workItems' not in extraction_result:
            error_msg = "Failed to extract workItems from PDF"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        work_items = extraction_result['workItems']
        logger.info(f"Extracted {len(work_items)} work items")
        
        # Validate and normalize workItems
        logger.info("Validating and normalizing work items...")
        try:
            validate_and_normalize_workitems(work_items)
            logger.info(f"Validation OK: {len(work_items)} workItems processed")
        except ValueError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            raise
        
        # Calculate total amount
        logger.info("Calculating total amount...")
        total_amount = calculate_total_amount(work_items)
        logger.info(f"Total amount calculated: {total_amount}")
        
        # Update database
        logger.info("Updating database...")
        if not update_document(mongo_client, doc_type, doc_id, work_items, total_amount):
            # Error details already logged in update_document function
            raise ValueError("Failed to update database")

        # Split PDF by SOMMANO and upload to S3
        logger.info("Splitting PDF by SOMMANO keyword...")
        work_item_files = split_pdf_by_sommano(temp_file_path, s3_url, work_items)

        if work_item_files:
            logger.info(f"PDF split into {len(work_item_files)} files and uploaded to S3")

            # Update work items with file information
            logger.info("Updating work items with file information...")
            if update_work_items_with_files(mongo_client, doc_type, doc_id, work_items, work_item_files):
                logger.info("Work items updated with file information successfully")
            else:
                logger.warning("Failed to update work items with file information")
        else:
            logger.warning("PDF splitting failed or no splits generated")

        # Success - send success email
        logger.info("Process completed successfully")

        # Determine document type labels
        if doc_type == 'privateTender':
            doc_label = "della gara"
            doc_label_for = "per la gara"
            doc_label_edit = "della gara"
        else:  # metricComputation
            doc_label = "del computo metrico"
            doc_label_for = "per il computo metrico"
            doc_label_edit = "del computo metrico"

        email_subject = f"Risultato estrazione file {filename} {doc_label} {title} su gembai.it"
        email_body = (f"Abbiamo finito l'estrazione del computo metrico {doc_label_for} {title}\n\n"
                     f"Vai alla modifica {doc_label_edit} per controllare che tutte le lavorazioni "
                     f"siano state estratte correttamente.\n\n"
                     f"Controlla se il valore totale estratto corrisponde al valore totale nel "
                     f"file del computo metrico.\n\n"
                     f"Dettagli estrazione:\n"
                     f"- Voci estratte: {len(work_items)}\n"
                     f"- Importo totale: €{total_amount:,.2f}")

        send_email(user_email, email_subject, email_body)
        
        # Log final result
        result = {
            'job_id': job_id,
            'job_type': 'MetricComputation',
            'status': 'success',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'document_id': doc_id,
            'document_type': doc_type,
            'metrics': {
                'work_items_count': len(work_items),
                'total_amount': total_amount
            }
        }
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        # Log error and send single error email
        logger.error(f"Job failed - Error during processing: {str(e)}")
        if user_email and title and doc_type:
            # Determine document type labels
            if doc_type == 'privateTender':
                doc_label = "della gara"
                doc_label_for = "per la gara"
                doc_label_edit = "della gara"
            else:  # metricComputation
                doc_label = "del computo metrico"
                doc_label_for = "per il computo metrico"
                doc_label_edit = "del computo metrico"

            # Get filename if available
            if 's3_url' in locals() and s3_url:
                filename = os.path.basename(urlparse(s3_url).path)
            else:
                filename = 'documento'

            # Determine specific error details for logging (not for user)
            if "Invalid MongoDB ObjectId" in str(e):
                error_detail = "ID documento non valido"
            elif "Document not found" in str(e):
                error_detail = "Documento non trovato nel database"
            elif "Failed to download file from S3" in str(e):
                error_detail = "Impossibile scaricare il file dal server"
            elif "Failed to extract workItems" in str(e):
                error_detail = "Impossibile estrarre le voci di computo dal PDF"
            elif "Validation error" in str(e):
                error_detail = f"Errore nella validazione: {str(e).replace('Validation error: ', '')}"
            elif "Failed to update database" in str(e):
                error_detail = "Impossibile aggiornare il database"
            else:
                error_detail = str(e)

            logger.error(f"Error detail for debugging: {error_detail}")

            # Send email with standard message (same as success but indicates there was an error)
            email_subject = f"Risultato estrazione file {filename} {doc_label} {title} su gembai.it"
            email_body = (f"Si è verificato un errore durante l'estrazione del computo metrico {doc_label_for} {title}.\n\n"
                         f"Errore: {error_detail}\n\n"
                         f"Ti preghiamo di riprovare o contattare il supporto se il problema persiste.")

            send_email(user_email, email_subject, email_body)
        sys.exit(1)
        
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {str(e)}")
        
        # Close MongoDB connection
        if mongo_client:
            try:
                mongo_client.close()
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.warning(f"Failed to close MongoDB connection: {str(e)}")


if __name__ == "__main__":
    main()