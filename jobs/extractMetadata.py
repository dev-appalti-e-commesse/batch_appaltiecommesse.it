#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('Metadata')

def main():
    logger.info("Hello, I'm Metadata service")
    
    job_id = os.environ.get('AWS_BATCH_JOB_ID', 'local-test')
    job_params = os.environ.get('JOB_PARAMS', '{}')
    
    logger.info(f"Job ID: {job_id}")
    logger.info(f"Job Parameters: {job_params}")
    
    try:
        params = json.loads(job_params) if job_params else {}
        logger.info(f"Parsed parameters: {params}")
        
        logger.info("Extracting metadata...")
        time.sleep(5)
        
        result = {
            'job_id': job_id,
            'job_type': 'Metadata',
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'parameters': params,
            'metadata': {
                'source': params.get('source', 'default'),
                'records_extracted': 50,
                'extraction_time': 5.0,
                'format': 'json'
            }
        }
        
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        logger.info("Finished")
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()