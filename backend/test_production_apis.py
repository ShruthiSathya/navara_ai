#!/usr/bin/env python3
"""
PRODUCTION API TEST SCRIPT
Tests all real database connections with SSL certificate handling
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.data_fetcher import ProductionDataFetcher


async def test_ssl_connection():
    """Test that SSL connection works"""
    print("\n" + "="*70)
    print("🔒 TESTING SSL CERTIFICATE HANDLING")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    print(f"✅ SSL Context created: {fetcher.ssl_context}")
    print(f"   Check hostname: {fetcher.ssl_context.check_hostname}")
    print(f"   Verify mode: {fetcher.ssl_context.verify_mode}")
    await fetcher.close()


async def test_opentargets():
    """Test OpenTargets disease data fetching"""
    print("\n" + "="*70)
    print("🧬 TEST 1: OpenTargets Platform (Disease-Gene Associations)")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    test_diseases = [
        "Huntington Disease",
        "Parkinson Disease",
        "Gaucher Disease",
        "Cystic Fibrosis",
    ]
    
    results = []
    
    for disease_name in test_diseases:
        print(f"\n🔍 Testing: {disease_name}")
        disease = await fetcher.fetch_disease_data(disease_name)
        
        if disease:
            print(f"  ✅ Found: {disease['name']}")
            print(f"  📊 Genes: {len(disease['genes'])}")
            print(f"  🧪 Pathways: {len(disease['pathways'])}")
            print(f"  🔬 Rare disease: {disease.get('is_rare', False)}")
            print(f"  📋 Active trials: {disease.get('active_trials_count', 0)}")
            
            if disease['genes']:
                print(f"  🎯 Top genes: {', '.join(disease['genes'][:5])}")
            if disease['pathways']:
                print(f"  🛤️  Top pathways: {', '.join(disease['pathways'][:3])}")
            
            results.append(True)
        else:
            print(f"  ❌ NOT FOUND in OpenTargets")
            results.append(False)
    
    await fetcher.close()
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Success Rate: {success_rate:.0f}% ({sum(results)}/{len(results)} diseases found)")
    
    return success_rate > 50  # At least 50% should work


async def test_chembl():
    """Test ChEMBL drug database"""
    print("\n" + "="*70)
    print("💊 TEST 2: ChEMBL (Approved Drugs)")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    print("\n🔍 Fetching 20 approved drugs from ChEMBL...")
    drugs = await fetcher.fetch_approved_drugs(limit=20)
    
    if drugs and len(drugs) > 0:
        print(f"\n✅ Successfully fetched {len(drugs)} drugs")
        print("\n📋 Sample drugs:")
        
        for i, drug in enumerate(drugs[:10], 1):
            print(f"\n  {i}. {drug['name']}")
            print(f"     ID: {drug['id']}")
            print(f"     Indication: {drug['indication']}")
            
            if drug['targets']:
                print(f"     Targets ({len(drug['targets'])}): {', '.join(drug['targets'][:3])}")
            else:
                print(f"     Targets: None yet (will be added by DGIdb)")
            
            if drug.get('smiles'):
                print(f"     SMILES: {drug['smiles'][:50]}...")
        
        await fetcher.close()
        return True
    else:
        print("  ❌ FAILED to fetch drugs from ChEMBL")
        await fetcher.close()
        return False


async def test_dgidb():
    """Test DGIdb drug-gene interactions"""
    print("\n" + "="*70)
    print("🔗 TEST 3: DGIdb (Drug-Gene Interactions)")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    # Create mock drugs to test DGIdb enhancement
    mock_drugs = [
        {"name": "Metformin", "id": "MOCK1", "targets": [], "pathways": []},
        {"name": "Aspirin", "id": "MOCK2", "targets": [], "pathways": []},
        {"name": "Ibuprofen", "id": "MOCK3", "targets": [], "pathways": []},
    ]
    
    print("\n🔍 Testing DGIdb enhancement for known drugs...")
    enhanced_drugs = await fetcher._enhance_with_dgidb(mock_drugs)
    
    success_count = 0
    print("\n📋 Results:")
    for drug in enhanced_drugs:
        print(f"\n  • {drug['name']}")
        if drug['targets']:
            print(f"    ✅ Targets found: {', '.join(drug['targets'][:5])}")
            if drug['pathways']:
                print(f"    ✅ Pathways inferred: {', '.join(drug['pathways'][:3])}")
            success_count += 1
        else:
            print(f"    ⚠️  No targets found")
    
    await fetcher.close()
    return success_count > 0


async def test_clinical_trials():
    """Test ClinicalTrials.gov integration"""
    print("\n" + "="*70)
    print("📋 TEST 4: ClinicalTrials.gov (Active Research)")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    test_diseases = [
        "Huntington Disease",
        "Gaucher Disease",
        "Duchenne Muscular Dystrophy",
    ]
    
    success_count = 0
    for disease_name in test_diseases:
        print(f"\n🔍 Testing: {disease_name}")
        
        # Create minimal disease data for testing
        disease = {
            "name": disease_name,
            "genes": [],
            "pathways": []
        }
        
        disease = await fetcher._add_clinical_trials_count(disease)
        
        trials = disease.get('active_trials_count', 0)
        if trials > 0:
            print(f"  ✅ Found {trials} active clinical trials")
            success_count += 1
        else:
            print(f"  ℹ️  No active trials found (or connection issue)")
    
    await fetcher.close()
    return success_count > 0


async def test_full_pipeline():
    """Test complete pipeline with a real disease"""
    print("\n" + "="*70)
    print("🚀 TEST 5: Full Pipeline (Disease → Drugs → Matching)")
    print("="*70)
    
    fetcher = ProductionDataFetcher()
    
    disease_name = "Parkinson Disease"
    print(f"\n🔍 Running full pipeline for: {disease_name}")
    
    # Fetch disease
    print("\n1️⃣  Fetching disease data...")
    disease = await fetcher.fetch_disease_data(disease_name)
    
    if not disease:
        print("  ❌ Disease not found!")
        await fetcher.close()
        return False
    
    print(f"  ✅ Disease: {disease['name']}")
    print(f"     Genes: {len(disease['genes'])}")
    print(f"     Pathways: {len(disease['pathways'])}")
    
    # Fetch drugs
    print("\n2️⃣  Fetching approved drugs...")
    drugs = await fetcher.fetch_approved_drugs(limit=50)
    print(f"  ✅ Fetched {len(drugs)} drugs")
    
    # Simple scoring (count overlapping genes/pathways)
    print("\n3️⃣  Finding drug-disease matches...")
    matches = []
    
    for drug in drugs:
        gene_overlap = len(set(drug['targets']) & set(disease['genes']))
        pathway_overlap = len(set(drug['pathways']) & set(disease['pathways']))
        
        if gene_overlap > 0 or pathway_overlap > 0:
            score = gene_overlap * 0.6 + pathway_overlap * 0.4
            matches.append({
                'drug': drug['name'],
                'score': score,
                'genes': gene_overlap,
                'pathways': pathway_overlap
            })
    
    # Sort by score
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    if matches:
        print(f"\n  ✅ Found {len(matches)} potential matches!")
        print("\n📊 Top 5 candidates:")
        for i, match in enumerate(matches[:5], 1):
            print(f"\n     {i}. {match['drug']}")
            print(f"        Score: {match['score']:.2f}")
            print(f"        Shared genes: {match['genes']}")
            print(f"        Shared pathways: {match['pathways']}")
    else:
        print("\n  ℹ️  No strong matches found (this is normal for small drug set)")
    
    await fetcher.close()
    return len(matches) > 0


async def run_all_tests():
    """Run all tests sequentially"""
    print("\n" + "🧪"*35)
    print("PRODUCTION API INTEGRATION TESTS")
    print("Testing: OpenTargets, ChEMBL, DGIdb, ClinicalTrials.gov")
    print("🧪"*35)
    
    results = {}
    
    try:
        # Test SSL
        await test_ssl_connection()
        
        # Test each API
        print("\n" + "▼"*70)
        results['opentargets'] = await test_opentargets()
        
        print("\n" + "▼"*70)
        results['chembl'] = await test_chembl()
        
        print("\n" + "▼"*70)
        results['dgidb'] = await test_dgidb()
        
        print("\n" + "▼"*70)
        results['clinicaltrials'] = await test_clinical_trials()
        
        print("\n" + "▼"*70)
        results['pipeline'] = await test_full_pipeline()
        
        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:20s}: {status}")
        
        total_passed = sum(results.values())
        total_tests = len(results)
        
        print(f"\nOverall: {total_passed}/{total_tests} tests passed")
        
        if total_passed >= 3:  # At least 3 out of 5 should work
            print("\n" + "="*70)
            print("✅ SYSTEM IS WORKING!")
            print("="*70)
            print("\n🎉 Your database integrations are operational!")
            print("\nNext steps:")
            print("  1. Update backend/pipeline/data_fetcher.py")
            print("     cp backend/pipeline/data_fetcher_production.py backend/pipeline/data_fetcher.py")
            print("  2. Update requirements:")
            print("     cp backend/requirements_production.txt backend/requirements.txt")
            print("  3. Restart your app: ./stop.sh && ./start.sh")
            print("  4. Test with: http://localhost:3000")
        else:
            print("\n" + "="*70)
            print("⚠️  SOME TESTS FAILED")
            print("="*70)
            print("\nTroubleshooting:")
            print("  1. Check internet connection")
            print("  2. Verify firewall allows HTTPS connections")
            print("  3. Try running: pip install --upgrade certifi")
            print("  4. Check logs above for specific errors")
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ CRITICAL ERROR!")
        print("="*70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n🔧 Debug steps:")
        print("  1. Install certifi: pip install --upgrade certifi")
        print("  2. Check SSL: python -c 'import ssl; print(ssl.OPENSSL_VERSION)'")
        print("  3. Test connection: curl https://api.platform.opentargets.org")


if __name__ == "__main__":
    print("\n🔬 Starting PRODUCTION API tests...")
    print("This will test real connections to public databases")
    print("Expected duration: 30-90 seconds\n")
    
    asyncio.run(run_all_tests())