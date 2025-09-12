# Test Suite for extractMetricComputation

## Overview
Comprehensive test suite for `extractMetricComputation.py` with 36 tests covering all major functionality.

## Test Coverage: 82%

## Test Categories

### 1. Parameter Retrieval (6 tests)
- Tests for getting headers from environment variables
- Tests for parsing JSON parameters
- Handles missing and invalid inputs

### 2. MongoDB Validation (3 tests)
- Valid ObjectId validation
- Invalid ObjectId detection
- None/null handling

### 3. S3 Download (3 tests)
- Successful S3 file downloads
- HTTPS URL format support
- Error handling for failed downloads

### 4. WorkItems Validation (6 tests)
- Valid work items processing
- Empty array detection
- Missing required fields
- Type validation
- Field normalization

### 5. Total Amount Calculation (5 tests)
- Simple calculations
- Percentage unit handling
- Empty list handling
- None value handling
- Performance test with 10k items

### 6. MongoDB Operations (4 tests)
- Document existence verification
- Private tender updates
- Metric computation updates
- Error handling

### 7. Email Functionality (2 tests)
- Successful email sending
- Missing credentials handling

### 8. PDF Processing (3 tests)
- Successful PDF extraction
- Script failure handling
- Timeout handling

### 9. Integration Tests (4 tests)
- Complete success flow
- Invalid ObjectId handling
- Document not found handling
- Cleanup on error

## Running Tests

```bash
# Run all tests
pytest tests/test_extractMetricComputation.py -v

# Run with coverage
pytest tests/test_extractMetricComputation.py --cov=extractMetricComputation --cov-report=term-missing

# Run specific test category
pytest tests/test_extractMetricComputation.py::TestWorkItemsValidation -v

# Run with short traceback
pytest tests/test_extractMetricComputation.py -v --tb=short
```

## Requirements
- pytest==7.4.4
- pytest-cov==4.1.0
- pytest-mock==3.12.0
- All dependencies from requirements.txt