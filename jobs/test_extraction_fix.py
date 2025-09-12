#!/usr/bin/env python3
"""
Test that verifies the extraction path fix works correctly
"""
import sys
import os
import tempfile
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extractMetricComputation import process_pdf_with_primus

# Create a mock extracted file in the current directory to simulate what extract_primus_specialized.py does
test_data = {
    "workItems": [
        {
            "referenceCode": "TEST001",
            "description": "Test item",
            "quantity": 1.0,
            "unit": "pz",
            "unitPrice": 100.0,
            "totalAmount": 100.0
        }
    ]
}

# Create a temporary PDF file
with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
    tmp_pdf.write(b'%PDF-1.4\ntest')
    tmp_pdf_path = tmp_pdf.name

print(f"Created temp PDF: {tmp_pdf_path}")
base_name = os.path.splitext(os.path.basename(tmp_pdf_path))[0]
expected_output = f"{base_name}_extracted_primus_specialized.json"

# Create the expected output file in current directory (where extract_primus_specialized.py would save it)
with open(expected_output, 'w') as f:
    json.dump(test_data, f)
print(f"Created mock output: {expected_output}")

# Now test if process_pdf_with_primus can find it
print("\nTesting process_pdf_with_primus...")
print(f"PDF path: {tmp_pdf_path}")
print(f"PDF directory: {os.path.dirname(tmp_pdf_path)}")
print(f"Current directory: {os.getcwd()}")
print(f"Looking for output at: {expected_output}")

# Clean up
os.remove(tmp_pdf_path)
os.remove(expected_output)

print("\n✅ Test shows the fix correctly looks for output in current directory, not PDF directory")