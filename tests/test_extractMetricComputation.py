#!/usr/bin/env python3
"""
Test suite for extractMetricComputation.py
Tests all functions including parameter retrieval, MongoDB operations, 
S3 downloads, workItems validation, and totalAmount calculations.
"""

import os
import sys
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from bson import ObjectId
from bson.errors import InvalidId

# Add parent directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'jobs'))
import extractMetricComputation as emc


class TestParameterRetrieval:
    """Test parameter retrieval functions"""
    
    def test_get_header_exists(self):
        """Test getting header when it exists in environment"""
        with patch.dict(os.environ, {'X_USER_EMAIL': 'test@example.com'}):
            result = emc.get_header('x-user-email')
            assert result == 'test@example.com'
    
    def test_get_header_not_exists(self):
        """Test getting header when it doesn't exist"""
        with patch.dict(os.environ, {}, clear=True):
            result = emc.get_header('x-user-email')
            assert result is None
    
    def test_get_header_with_dash(self):
        """Test header name conversion (dash to underscore)"""
        with patch.dict(os.environ, {'X_USER_COMPANY_ID': 'company123'}):
            result = emc.get_header('x-user-company-id')
            assert result == 'company123'
    
    def test_get_param_valid_json(self):
        """Test getting parameter from valid JSON"""
        job_params = json.dumps({'s3Url': 's3://bucket/file.pdf', 'id': '123'})
        with patch.dict(os.environ, {'JOB_PARAMS': job_params}):
            result = emc.get_param('s3Url')
            assert result == 's3://bucket/file.pdf'
    
    def test_get_param_invalid_json(self):
        """Test getting parameter from invalid JSON"""
        with patch.dict(os.environ, {'JOB_PARAMS': 'invalid json'}):
            result = emc.get_param('s3Url')
            assert result is None
    
    def test_get_param_missing_key(self):
        """Test getting parameter that doesn't exist in JSON"""
        job_params = json.dumps({'id': '123'})
        with patch.dict(os.environ, {'JOB_PARAMS': job_params}):
            result = emc.get_param('s3Url')
            assert result is None


class TestMongoDBValidation:
    """Test MongoDB ObjectId validation"""
    
    def test_validate_objectid_valid(self):
        """Test validation of valid ObjectId"""
        valid_id = '507f1f77bcf86cd799439011'
        assert emc.validate_objectid(valid_id) is True
    
    def test_validate_objectid_invalid(self):
        """Test validation of invalid ObjectId"""
        invalid_ids = [
            'invalid',
            '123',
            '',
            'zzzzzzzzzzzzzzzzzzzzzzzzzz'
        ]
        for invalid_id in invalid_ids:
            assert emc.validate_objectid(invalid_id) is False
    
    def test_validate_objectid_none(self):
        """Test validation of None ObjectId"""
        assert emc.validate_objectid(None) is False


class TestS3Download:
    """Test S3 file download functionality"""
    
    @patch('extractMetricComputation.s3_client')
    def test_download_s3_file_success(self, mock_s3):
        """Test successful S3 file download"""
        s3_url = 's3://test-bucket/test-file.pdf'
        
        # Mock successful download
        mock_s3.download_file.return_value = None
        
        result = emc.download_s3_file(s3_url)
        
        # Check that a temp file path was returned
        assert result is not None
        assert result.endswith('.pdf')
        
        # Check S3 was called correctly
        mock_s3.download_file.assert_called_once()
        call_args = mock_s3.download_file.call_args[0]
        assert call_args[0] == 'test-bucket'
        assert call_args[1] == 'test-file.pdf'
        
        # Clean up temp file
        if os.path.exists(result):
            os.remove(result)
    
    @patch('extractMetricComputation.s3_client')
    def test_download_s3_file_https_url(self, mock_s3):
        """Test S3 download with HTTPS URL format"""
        s3_url = 'https://test-bucket.s3.eu-north-1.amazonaws.com/test-file.pdf'
        
        mock_s3.download_file.return_value = None
        
        result = emc.download_s3_file(s3_url)
        
        assert result is not None
        mock_s3.download_file.assert_called_once()
        call_args = mock_s3.download_file.call_args[0]
        assert call_args[0] == 'test-bucket'
        assert call_args[1] == 'test-file.pdf'
        
        if os.path.exists(result):
            os.remove(result)
    
    @patch('extractMetricComputation.s3_client')
    def test_download_s3_file_failure(self, mock_s3):
        """Test S3 download failure"""
        s3_url = 's3://test-bucket/test-file.pdf'
        
        # Mock download failure
        mock_s3.download_file.side_effect = Exception('S3 error')
        
        result = emc.download_s3_file(s3_url)
        
        assert result is None


class TestWorkItemsValidation:
    """Test workItems validation and normalization"""
    
    def test_validate_and_normalize_valid_items(self):
        """Test validation of valid work items"""
        work_items = [
            {
                'referenceCode': 'REF001',
                'description': 'Test description',
                'quantity': 10,
                'unitPrice': 100.5,
                'unitOfMeasurement': 'm²'
            },
            {
                'referenceCode': 'REF002',
                'description': None,
                'quantity': None,
                'unitPrice': None
            }
        ]
        
        # Should not raise exception
        emc.validate_and_normalize_workitems(work_items)
        
        # Check progressive numbers were assigned
        assert work_items[0]['progressiveNumber'] == 1
        assert work_items[1]['progressiveNumber'] == 2
        
        # Check defaults were applied
        assert work_items[1]['quantity'] == 0
        assert work_items[1]['unitPrice'] == 0
        assert work_items[1]['unitOfMeasurement'] is None
    
    def test_validate_empty_array(self):
        """Test validation fails for empty array"""
        with pytest.raises(ValueError, match="array vuoto"):
            emc.validate_and_normalize_workitems([])
    
    def test_validate_not_array(self):
        """Test validation fails for non-array"""
        with pytest.raises(ValueError, match="deve essere un array"):
            emc.validate_and_normalize_workitems("not an array")
    
    def test_validate_missing_reference_code(self):
        """Test validation fails for missing referenceCode"""
        work_items = [
            {
                'description': 'Test description'
            }
        ]
        
        with pytest.raises(ValueError, match="referenceCode è obbligatorio"):
            emc.validate_and_normalize_workitems(work_items)
    
    def test_validate_invalid_types(self):
        """Test validation fails for invalid field types"""
        # Invalid referenceCode type
        work_items = [{'referenceCode': 123}]
        with pytest.raises(ValueError, match="referenceCode deve essere string"):
            emc.validate_and_normalize_workitems(work_items)
        
        # Invalid quantity type
        work_items = [{'referenceCode': 'REF001', 'quantity': 'not a number'}]
        with pytest.raises(ValueError, match="quantity deve essere number"):
            emc.validate_and_normalize_workitems(work_items)
    
    def test_validate_normalizes_missing_fields(self):
        """Test that missing optional fields are normalized"""
        work_items = [
            {
                'referenceCode': 'REF001'
                # Missing all optional fields
            }
        ]
        
        emc.validate_and_normalize_workitems(work_items)
        
        assert work_items[0]['description'] is None
        assert work_items[0]['quantity'] == 0
        assert work_items[0]['unitPrice'] == 0
        assert work_items[0]['unitOfMeasurement'] is None
        assert work_items[0]['progressiveNumber'] == 1


class TestTotalAmountCalculation:
    """Test total amount calculation"""
    
    def test_calculate_total_simple(self):
        """Test simple total calculation"""
        work_items = [
            {'quantity': 10, 'unitPrice': 100},
            {'quantity': 5, 'unitPrice': 50}
        ]
        
        total = emc.calculate_total_amount(work_items)
        assert total == 1250.0  # (10*100) + (5*50)
    
    def test_calculate_total_with_percentage(self):
        """Test total calculation with percentage unit"""
        work_items = [
            {'quantity': 10, 'unitPrice': 1000, 'unitOfMeasurement': 'm²'},
            {'quantity': 10, 'unitPrice': 1000, 'unitOfMeasurement': '%'}  # 10% of 1000
        ]
        
        total = emc.calculate_total_amount(work_items)
        assert total == 10100.0  # (10*1000) + (1000*(10/100))
    
    def test_calculate_total_empty_list(self):
        """Test total calculation for empty list"""
        total = emc.calculate_total_amount([])
        assert total == 0.0
    
    def test_calculate_total_with_none_values(self):
        """Test total calculation handles None values"""
        work_items = [
            {'quantity': None, 'unitPrice': 100},
            {'quantity': 10, 'unitPrice': None},
            {'quantity': 5, 'unitPrice': 50}
        ]
        
        total = emc.calculate_total_amount(work_items)
        assert total == 250.0  # Only the last item counts
    
    def test_calculate_total_large_dataset(self):
        """Test total calculation with 10k items (performance test)"""
        # Create 10k items
        work_items = [
            {'quantity': i, 'unitPrice': 0.1, 'unitOfMeasurement': 'pz'}
            for i in range(1, 10001)
        ]
        
        total = emc.calculate_total_amount(work_items)
        # Sum of 1 to 10000 = 10000 * 10001 / 2 = 50,005,000
        # Each multiplied by 0.1 = 5,000,500
        assert total == 5000500.0


class TestMongoDBOperations:
    """Test MongoDB operations"""
    
    @patch('extractMetricComputation.MongoClient')
    def test_verify_document_exists_private_tender(self, mock_mongo_client):
        """Test document verification for private tender"""
        # Setup mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.find_one.return_value = {'_id': ObjectId('507f1f77bcf86cd799439011')}
        
        client = mock_mongo_client()
        result = emc.verify_document_exists(client, 'privateTender', '507f1f77bcf86cd799439011')
        
        assert result is True
        mock_collection.find_one.assert_called_once()
    
    @patch('extractMetricComputation.MongoClient')
    def test_verify_document_not_exists(self, mock_mongo_client):
        """Test document verification when document doesn't exist"""
        # Setup mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.find_one.return_value = None
        
        client = mock_mongo_client()
        result = emc.verify_document_exists(client, 'metricComputation', '507f1f77bcf86cd799439011')
        
        assert result is False
    
    @patch('extractMetricComputation.MongoClient')
    def test_update_document_private_tender(self, mock_mongo_client):
        """Test document update for private tender"""
        # Setup mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        
        mock_mongo_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.update_one.return_value = mock_result
        
        client = mock_mongo_client()
        work_items = [{'test': 'data'}]
        result = emc.update_document(client, 'privateTender', '507f1f77bcf86cd799439011', 
                                    work_items, 1000.0)
        
        assert result is True
        
        # Check update was called with correct fields
        update_call = mock_collection.update_one.call_args
        assert update_call[0][1]['$set']['tenderContent.workItems'] == work_items
        assert update_call[0][1]['$set']['tenderContent.totalAmount'] == 1000.0
    
    @patch('extractMetricComputation.MongoClient')
    def test_update_document_metric_computation(self, mock_mongo_client):
        """Test document update for metric computation"""
        # Setup mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        
        mock_mongo_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.update_one.return_value = mock_result
        
        client = mock_mongo_client()
        work_items = [{'test': 'data'}]
        result = emc.update_document(client, 'metricComputation', '507f1f77bcf86cd799439011',
                                    work_items, 2000.0)
        
        assert result is True
        
        # Check update was called with correct fields for metricComputation
        update_call = mock_collection.update_one.call_args
        assert update_call[0][1]['$set']['content.workItems'] == work_items
        assert update_call[0][1]['$set']['content.totalAmount'] == 2000.0


class TestEmailFunctionality:
    """Test email sending functionality"""
    
    @patch('extractMetricComputation.SMTP_USER', 'test@gmail.com')
    @patch('extractMetricComputation.SMTP_PASSWORD', 'password123')
    @patch('extractMetricComputation.SMTP_HOST', 'smtp.gmail.com')
    @patch('extractMetricComputation.SMTP_PORT', 587)
    @patch('extractMetricComputation.EMAIL_FROM', 'test@gmail.com')
    @patch('extractMetricComputation.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending"""
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        result = emc.send_email('user@example.com', 'Test Subject', 'Test Body')
        
        assert result is True
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@gmail.com', 'password123')
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
    
    def test_send_email_no_credentials(self):
        """Test email sending without credentials"""
        with patch.dict(os.environ, {}, clear=True):
            result = emc.send_email('user@example.com', 'Test Subject', 'Test Body')
        
        assert result is False  # Should return False when no credentials


class TestPDFProcessing:
    """Test PDF processing with Primus extractor"""
    
    @patch('extractMetricComputation.subprocess.run')
    @patch('extractMetricComputation.os.path.exists')
    @patch('builtins.open', create=True)
    @patch('extractMetricComputation.os.remove')
    def test_process_pdf_success(self, mock_remove, mock_open, mock_exists, mock_subprocess):
        """Test successful PDF processing"""
        # Setup mocks
        mock_subprocess.return_value.returncode = 0
        mock_exists.return_value = True
        
        # Mock JSON file reading
        mock_file = MagicMock()
        mock_file.read.return_value = json.dumps({'workItems': [{'test': 'data'}]})
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file
        
        result = emc.process_pdf_with_primus('/tmp/test.pdf')
        
        assert result is not None
        assert 'workItems' in result
        assert result['workItems'] == [{'test': 'data'}]
    
    @patch('extractMetricComputation.subprocess.run')
    def test_process_pdf_script_failure(self, mock_subprocess):
        """Test PDF processing when script fails"""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = 'Error message'
        
        result = emc.process_pdf_with_primus('/tmp/test.pdf')
        
        assert result is None
    
    @patch('extractMetricComputation.subprocess.run')
    def test_process_pdf_timeout(self, mock_subprocess):
        """Test PDF processing timeout"""
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired('cmd', 300)
        
        result = emc.process_pdf_with_primus('/tmp/test.pdf')
        
        assert result is None


class TestMainIntegration:
    """Integration tests for main function"""
    
    @patch('extractMetricComputation.send_email')
    @patch('extractMetricComputation.update_document')
    @patch('extractMetricComputation.process_pdf_with_primus')
    @patch('extractMetricComputation.download_s3_file')
    @patch('extractMetricComputation.verify_document_exists')
    @patch('extractMetricComputation.MongoClient')
    @patch.dict(os.environ, {
        'X_USER_EMAIL': 'test@example.com',
        'X_USER_COMPANY_ID': 'company123',
        'JOB_PARAMS': json.dumps({
            's3Url': 's3://bucket/file.pdf',
            'id': '507f1f77bcf86cd799439011',
            'title': 'Test Document',
            'type': 'privateTender'
        })
    })
    def test_main_success_flow(self, mock_mongo, mock_verify, mock_download,
                               mock_process, mock_update, mock_email):
        """Test successful execution of main function"""
        # Setup mocks
        mock_verify.return_value = True
        mock_download.return_value = '/tmp/test.pdf'
        mock_process.return_value = {
            'workItems': [
                {'referenceCode': 'REF001', 'quantity': 10, 'unitPrice': 100}
            ]
        }
        mock_update.return_value = True
        mock_email.return_value = True
        
        # Run main - should exit with 0 on success
        try:
            emc.main()
        except SystemExit as e:
            assert e.code != 1  # Should not exit with error code
        
        # Verify email was sent with success message
        calls = mock_email.call_args_list
        assert any('estratto correttamente' in str(call).lower() for call in calls)
    
    @patch('extractMetricComputation.send_email')
    @patch.dict(os.environ, {
        'X_USER_EMAIL': 'test@example.com',
        'X_USER_COMPANY_ID': 'company123',
        'JOB_PARAMS': json.dumps({
            's3Url': 's3://bucket/file.pdf',
            'id': 'invalid_id',  # Invalid ObjectId
            'title': 'Test Document',
            'type': 'privateTender'
        })
    })
    def test_main_invalid_objectid(self, mock_email):
        """Test main function with invalid ObjectId"""
        with pytest.raises(SystemExit) as exc_info:
            emc.main()
        
        assert exc_info.value.code == 1
        
        # Verify error email was sent
        mock_email.assert_called()
        calls = mock_email.call_args_list
        assert any('non valido' in str(call) for call in calls)
    
    @patch('extractMetricComputation.send_email')
    @patch('extractMetricComputation.verify_document_exists')
    @patch('extractMetricComputation.MongoClient')
    @patch.dict(os.environ, {
        'X_USER_EMAIL': 'test@example.com',
        'X_USER_COMPANY_ID': 'company123',
        'JOB_PARAMS': json.dumps({
            's3Url': 's3://bucket/file.pdf',
            'id': '507f1f77bcf86cd799439011',
            'title': 'Test Document',
            'type': 'privateTender'
        })
    })
    def test_main_document_not_found(self, mock_mongo, mock_verify, mock_email):
        """Test main function when document doesn't exist"""
        mock_verify.return_value = False
        
        with pytest.raises(SystemExit) as exc_info:
            emc.main()
        
        assert exc_info.value.code == 1
        
        # Verify error email was sent
        calls = mock_email.call_args_list
        assert any('non trovato' in str(call).lower() for call in calls)
    
    @patch('extractMetricComputation.send_email')
    @patch('extractMetricComputation.os.path.exists')
    @patch('extractMetricComputation.os.remove')
    @patch('extractMetricComputation.download_s3_file')
    @patch('extractMetricComputation.verify_document_exists')
    @patch('extractMetricComputation.MongoClient')
    @patch.dict(os.environ, {
        'X_USER_EMAIL': 'test@example.com',
        'X_USER_COMPANY_ID': 'company123',
        'JOB_PARAMS': json.dumps({
            's3Url': 's3://bucket/file.pdf',
            'id': '507f1f77bcf86cd799439011',
            'title': 'Test Document',
            'type': 'privateTender'
        })
    })
    def test_main_cleanup_on_error(self, mock_mongo, mock_verify, mock_download,
                                   mock_remove, mock_exists, mock_email):
        """Test that temporary files are cleaned up on error"""
        mock_verify.return_value = True
        mock_download.return_value = '/tmp/test.pdf'
        mock_exists.return_value = True  # File exists for cleanup
        
        # Make process_pdf fail to trigger error
        with patch('extractMetricComputation.process_pdf_with_primus', return_value=None):
            with pytest.raises(SystemExit):
                emc.main()
        
        # Verify cleanup was attempted
        mock_remove.assert_called_with('/tmp/test.pdf')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])