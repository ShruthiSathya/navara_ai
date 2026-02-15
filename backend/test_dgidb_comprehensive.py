#!/usr/bin/env python3
"""
DIAGNOSTIC SCRIPT - Verify DGIdb Integration Works
This will test if drugs actually get enriched with gene targets
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the fixed fetcher
from pipeline.data_fetcher import ProductionDataFetcher


async def diagnose_dgidb_integration():
    print("\n" + "="*70)
    print("🔍 DIAGNOSING DGIDB INTEGRATION")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    # Test 1: Fetch disease
    print("\n📊 TEST 1: Fetching disease from OpenTargets...")
    disease = await fetcher.fetch_disease_data("Parkinson Disease")
    
    if not disease:
        print("❌ Disease not found!")
        await fetcher.close()
        return False
    
    print(f"✅ Disease: {disease['name']}")
    print(f"   Genes from OpenTargets: {len(disease['genes'])}")
    print(f"   Top genes: {disease['genes'][:10]}")
    print(f"   Pathways: {len(disease['pathways'])}")
    
    # Test 2: Fetch small set of drugs
    print("\n💊 TEST 2: Fetching drugs from ChEMBL...")
    drugs = await fetcher.fetch_approved_drugs(limit=50)
    
    if not drugs:
        print("❌ No drugs fetched!")
        await fetcher.close()
        return False
    
    print(f"✅ Fetched {len(drugs)} drugs")
    
    # Test 3: Check DGIdb enhancement
    print("\n🔍 TEST 3: Checking DGIdb enhancement...")
    drugs_with_targets = [d for d in drugs if d.get('targets')]
    
    print(f"   Drugs with targets: {len(drugs_with_targets)}/{len(drugs)}")
    print(f"   Enhancement rate: {len(drugs_with_targets)/len(drugs)*100:.1f}%")
    
    if len(drugs_with_targets) == 0:
        print("\n❌ PROBLEM: No drugs have gene targets!")
        print("   This means DGIdb enhancement failed")
        print("   Possible causes:")
        print("   1. DGIdb API is down")
        print("   2. Drug names don't match DGIdb format")
        print("   3. Network/SSL issues")
        await fetcher.close()
        return False
    
    # Test 4: Show sample enriched drugs
    print("\n📋 TEST 4: Sample enriched drugs:")
    for drug in drugs_with_targets[:5]:
        print(f"\n   {drug['name']}:")
        print(f"      Targets: {len(drug['targets'])} genes")
        print(f"      Sample targets: {drug['targets'][:5]}")
        print(f"      Pathways: {len(drug['pathways'])}")
    
    # Test 5: Check gene overlap
    print("\n🎯 TEST 5: Checking gene overlap with disease...")
    disease_genes = set(disease['genes'])
    overlapping_drugs = []
    
    for drug in drugs_with_targets:
        drug_genes = set(drug['targets'])
        overlap = disease_genes & drug_genes
        
        if overlap:
            overlapping_drugs.append({
                'name': drug['name'],
                'overlap_count': len(overlap),
                'overlap_genes': list(overlap)
            })
    
    print(f"   Drugs with gene overlap: {len(overlapping_drugs)}")
    
    if len(overlapping_drugs) == 0:
        print("\n⚠️  WARNING: No drugs share genes with disease!")
        print("   This could mean:")
        print("   1. DGIdb data doesn't include genes for this disease")
        print("   2. Need more drugs (try limit=500)")
        print("   3. Disease-drug match is actually rare")
        
        # Show what genes we have
        all_drug_genes = set()
        for drug in drugs_with_targets:
            all_drug_genes.update(drug['targets'])
        
        print(f"\n   Total unique genes in drugs: {len(all_drug_genes)}")
        print(f"   Sample drug genes: {list(all_drug_genes)[:20]}")
        print(f"\n   Disease genes needed: {disease_genes}")
        
        await fetcher.close()
        return False
    
    # Test 6: Show overlapping drugs
    print("\n🏆 TEST 6: Drugs with gene overlap:")
    overlapping_drugs.sort(key=lambda x: x['overlap_count'], reverse=True)
    
    for i, drug in enumerate(overlapping_drugs[:10], 1):
        print(f"\n   {i}. {drug['name']}")
        print(f"      Overlap: {drug['overlap_count']} genes")
        print(f"      Genes: {drug['overlap_genes'][:5]}")
    
    await fetcher.close()
    
    print("\n" + "="*70)
    print("✅ DIAGNOSIS COMPLETE")
    print("="*70)
    print(f"\nResults:")
    print(f"  Disease genes: {len(disease['genes'])}")
    print(f"  Drugs fetched: {len(drugs)}")
    print(f"  Drugs with targets: {len(drugs_with_targets)}")
    print(f"  Drugs with overlap: {len(overlapping_drugs)}")
    
    if len(overlapping_drugs) >= 5:
        print("\n✅ SUCCESS! Gene matching is working!")
        print("   The scoring system should now work properly.")
        return True
    else:
        print("\n⚠️  PARTIAL SUCCESS")
        print("   DGIdb is working but overlap is low.")
        print("   Try fetching more drugs (limit=500)")
        return False


if __name__ == "__main__":
    success = asyncio.run(diagnose_dgidb_integration())
    sys.exit(0 if success else 1)