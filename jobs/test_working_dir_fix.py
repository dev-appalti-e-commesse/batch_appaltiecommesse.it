#!/usr/bin/env python3
"""
Test that verifies the working directory fix for subprocess execution
"""
import sys
import os
import tempfile
import subprocess
import json

# Create a temporary PDF file in /tmp to simulate S3 download
with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, dir='/tmp') as tmp_pdf:
    tmp_pdf.write(b'%PDF-1.4\ntest')
    tmp_pdf_path = tmp_pdf.name

print(f"Created temp PDF: {tmp_pdf_path}")
print(f"PDF directory: {os.path.dirname(tmp_pdf_path)}")

# Get script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Script directory: {script_dir}")
print(f"Current working directory: {os.getcwd()}")

# Create a mock extraction script
mock_script = os.path.join(script_dir, 'test_extractor.py')
with open(mock_script, 'w') as f:
    f.write("""
import os
import sys
print(f"Extractor CWD: {os.getcwd()}")
pdf_path = sys.argv[1]
base_name = os.path.splitext(os.path.basename(pdf_path))[0]
output_file = f"{base_name}_extracted_primus_specialized.json"
print(f"Creating output file: {output_file}")
with open(output_file, 'w') as f:
    f.write('{"workItems": []}')
""")

# Test 1: Run without cwd (will create file in current directory)
print("\n=== Test 1: Without cwd ===")
result1 = subprocess.run([sys.executable, mock_script, tmp_pdf_path], 
                        capture_output=True, text=True)
print(f"Stdout: {result1.stdout}")
base_name = os.path.splitext(os.path.basename(tmp_pdf_path))[0]
output_in_cwd = f"{base_name}_extracted_primus_specialized.json"
if os.path.exists(output_in_cwd):
    print(f"✓ File created in CWD: {output_in_cwd}")
    os.remove(output_in_cwd)
else:
    print(f"✗ File NOT in CWD")

# Test 2: Run with cwd=script_dir (will create file in script directory)
print("\n=== Test 2: With cwd=script_dir ===")
result2 = subprocess.run([sys.executable, mock_script, tmp_pdf_path], 
                        capture_output=True, text=True, cwd=script_dir)
print(f"Stdout: {result2.stdout}")
output_in_script_dir = os.path.join(script_dir, f"{base_name}_extracted_primus_specialized.json")
if os.path.exists(output_in_script_dir):
    print(f"✓ File created in script_dir: {output_in_script_dir}")
    os.remove(output_in_script_dir)
else:
    print(f"✗ File NOT in script_dir")

# Clean up
os.remove(tmp_pdf_path)
os.remove(mock_script)

print("\n✅ Test shows that cwd parameter controls where output file is created")