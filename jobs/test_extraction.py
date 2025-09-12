#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extractMetricComputation import process_pdf_with_primus

# Test with computo-small.pdf
pdf_path = "computo-small.pdf"
if not os.path.exists(pdf_path):
    print(f"ERROR: File {pdf_path} not found!")
    sys.exit(1)

print(f"Testing extraction with {pdf_path}...")
result = process_pdf_with_primus(pdf_path)

if result and 'workItems' in result:
    print(f"✅ SUCCESS: Found {len(result['workItems'])} work items")
    print(f"First 3 items:")
    for i, item in enumerate(result['workItems'][:3], 1):
        print(f"  {i}. {item.get('referenceCode', 'N/A')} - {item.get('description', 'N/A')[:50]}...")
else:
    print(f"❌ FAILED: No work items found")
    print(f"Result: {result}")
