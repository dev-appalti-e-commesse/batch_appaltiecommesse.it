#!/usr/bin/env python3
"""
Test completo che simula l'estrazione di un computo metrico
e mostra il risultato finale come farebbe il job AWS Batch
"""
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extractMetricComputation import process_pdf_with_primus, calculate_total_amount, validate_and_normalize_workitems

# Test with computo-small.pdf
pdf_path = "computo-small.pdf"
if not os.path.exists(pdf_path):
    print(f"ERROR: File {pdf_path} not found!")
    sys.exit(1)

print("=" * 60)
print("📄 TESTING METRIC COMPUTATION EXTRACTION")
print("=" * 60)
print(f"PDF File: {pdf_path}")
print()

# Step 1: Extract work items from PDF
print("🔍 Step 1: Extracting work items from PDF...")
result = process_pdf_with_primus(pdf_path)

if not result or 'workItems' not in result:
    print("❌ FAILED: No work items found")
    sys.exit(1)

work_items = result['workItems']
print(f"✅ Extracted {len(work_items)} work items")
print()

# Step 2: Validate and normalize
print("✔️ Step 2: Validating and normalizing work items...")
try:
    validate_and_normalize_workitems(work_items)
    print(f"✅ All {len(work_items)} items validated successfully")
except Exception as e:
    print(f"❌ Validation failed: {e}")
    sys.exit(1)
print()

# Step 3: Calculate total amount
print("💰 Step 3: Calculating total amount...")
total_amount = calculate_total_amount(work_items)
print(f"✅ Total amount: €{total_amount:,.2f}")
print()

# Step 4: Display results
print("📊 EXTRACTION RESULTS:")
print("-" * 60)
for item in work_items:
    prog = item.get('progressiveNumber', 'N/A')
    ref = item.get('referenceCode', 'N/A')
    desc = item.get('description', 'N/A')
    qty = item.get('quantity', 0)
    price = item.get('unitPrice', 0)
    uom = item.get('unitOfMeasurement', 'N/A')
    
    # Truncate description for display
    if len(desc) > 50:
        desc = desc[:50] + "..."
    
    item_total = qty * price if uom != '%' else price * (qty / 100)
    
    print(f"{prog:3d}. [{ref:12s}] {desc:50s}")
    print(f"     Qty: {qty:8.2f} {uom:5s} × €{price:8.2f} = €{item_total:10.2f}")
    print()

print("-" * 60)
print(f"TOTAL AMOUNT: €{total_amount:,.2f}")
print("=" * 60)

# Save sample output
output_file = "test_extraction_result.json"
output_data = {
    "pdfFile": pdf_path,
    "workItemsCount": len(work_items),
    "totalAmount": total_amount,
    "workItems": work_items[:3]  # Save only first 3 for sample
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)
    
print(f"\n💾 Sample output saved to: {output_file}")
