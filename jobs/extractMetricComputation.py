#!/usr/bin/env python3
import os
import sys
import json
import logging
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse
from bson import ObjectId
from bson.errors import InvalidId
import boto3
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email notification to user"""
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning(f"Email credentials not configured, skipping email to {to_email}")
            return False
            
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
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
        
        # 2. Verifica referenceCode OBBLIGATORIO
        if 'referenceCode' not in item or not item['referenceCode']:
            raise ValueError(f"workItem {i}: referenceCode è obbligatorio")
        
        if not isinstance(item['referenceCode'], str):
            raise ValueError(f"workItem {i}: referenceCode deve essere string, ricevuto {type(item['referenceCode'])}")
        
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
        
        # Call the script
        result = subprocess.run(
            [sys.executable, primus_script, pdf_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        # Log stdout/stderr regardless of return code
        if result.stdout:
            logger.info(f"Extraction stdout: {result.stdout[:1000]}")  # First 1000 chars
        if result.stderr:
            logger.warning(f"Extraction stderr: {result.stderr[:1000]}")
        
        if result.returncode != 0:
            logger.error(f"Primus extraction failed with return code {result.returncode}")
            return None
        
        # Read the output JSON file
        # The extract_primus_specialized.py saves the file in the current working directory
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = f"{base_name}_extracted_primus_specialized.json"
        
        if not os.path.exists(output_path):
            logger.error(f"Output file not found: {output_path}")
            # List files in current directory for debugging
            logger.info(f"Files in current directory: {os.listdir('.')[:20]}")
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
                'tenderContent.totalAmount': total_amount
            }
        elif doc_type == 'metricComputation':
            collection = db['metric_computations']
            update_fields = {
                'content.workItems': work_items,
                'content.totalAmount': total_amount
            }
        else:
            logger.error(f"Invalid document type: {doc_type}")
            return False
        
        # Update document using $set for specific fields
        result = collection.update_one(
            {'_id': ObjectId(doc_id)},
            {'$set': update_fields}
        )
        
        if result.modified_count > 0:
            logger.info(f"Document updated successfully: {doc_id}")
            return True
        else:
            logger.warning(f"Document not modified: {doc_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating document: {str(e)}")
        return False


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
            send_email(user_email, 
                      f"Errore nell'estrazione del computo {title}",
                      f"ID documento non valido: {doc_id}")
            raise ValueError(error_msg)
        
        # Connect to MongoDB
        logger.info("Connecting to MongoDB...")
        mongo_client = MongoClient(MONGO_URI)
        
        # Verify document exists
        logger.info(f"Verifying document exists: {doc_id} in {doc_type}")
        if not verify_document_exists(mongo_client, doc_type, doc_id):
            error_msg = f"Document not found: {doc_id} in {doc_type}"
            logger.error(error_msg)
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title}",
                      f"Documento non trovato nel database")
            raise ValueError(error_msg)
        
        # Download file from S3
        logger.info(f"Downloading file from S3: {s3_url}")
        temp_file_path = download_s3_file(s3_url)
        if not temp_file_path:
            error_msg = "Failed to download file from S3"
            logger.error(error_msg)
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title}",
                      "Impossibile scaricare il file dal server")
            raise ValueError(error_msg)
        
        # Process PDF with Primus extractor
        logger.info("Processing PDF with Primus extractor...")
        extraction_result = process_pdf_with_primus(temp_file_path)
        
        if not extraction_result or 'workItems' not in extraction_result:
            error_msg = "Failed to extract workItems from PDF"
            logger.error(error_msg)
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title}",
                      "Impossibile estrarre le voci di computo dal PDF")
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
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title}",
                      f"Errore nella validazione dei dati estratti: {str(e)}")
            raise
        
        # Calculate total amount
        logger.info("Calculating total amount...")
        total_amount = calculate_total_amount(work_items)
        logger.info(f"Total amount calculated: {total_amount}")
        
        # Update database
        logger.info("Updating database...")
        if not update_document(mongo_client, doc_type, doc_id, work_items, total_amount):
            error_msg = "Failed to update database"
            logger.error(error_msg)
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title}",
                      "Impossibile aggiornare il database")
            raise ValueError(error_msg)
        
        # Success - send success email
        logger.info("Process completed successfully")
        send_email(user_email,
                  f"Estrazione completata: {title}",
                  f"Abbiamo estratto correttamente il computo metrico {title}\\n\\n"
                  f"Voci estratte: {len(work_items)}\\n"
                  f"Importo totale: €{total_amount:,.2f}")
        
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
        # Log error and send error email
        logger.error(f"Error during processing: {str(e)}")
        if user_email:
            send_email(user_email,
                      f"Errore nell'estrazione del computo {title if title else ''}",
                      f"Ci sono stati errori nell'estrazione del computo: {str(e)}")
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