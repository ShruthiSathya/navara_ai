#!/usr/bin/env python3
"""
Backend Startup Diagnostic (Fixed for running from backend directory)
This will tell you exactly why the backend is failing to start
"""

import sys
import os
from pathlib import Path

print("=" * 70)
print("🔍 BACKEND STARTUP DIAGNOSTIC")
print("=" * 70)

# Check Python version
print(f"\n✅ Python version: {sys.version}")

# Check current directory
print(f"📁 Current directory: {os.getcwd()}")

# Determine if we're in the backend directory or parent
current_dir = Path.cwd()
if current_dir.name == 'backend':
    backend_dir = current_dir
    print("   ℹ️  Already in backend directory")
else:
    backend_dir = current_dir / 'backend'
    if not backend_dir.exists():
        print(f"   ❌ Backend directory not found at {backend_dir}")
        sys.exit(1)
    print(f"   ℹ️  Backend directory: {backend_dir}")

# Test 1: Import FastAPI
print("\n📦 Testing imports...")
try:
    import fastapi
    print(f"   ✅ FastAPI {fastapi.__version__}")
except ImportError as e:
    print(f"   ❌ FastAPI not installed: {e}")
    print("\n💡 FIX: Run this command:")
    print("   pip install fastapi uvicorn")
    sys.exit(1)

# Test 2: Import Uvicorn
try:
    import uvicorn
    print(f"   ✅ Uvicorn {uvicorn.__version__}")
except ImportError as e:
    print(f"   ❌ Uvicorn not installed: {e}")
    print("\n💡 FIX: Run this command:")
    print("   pip install uvicorn")
    sys.exit(1)

# Test 3: Check if main.py exists
print("\n📁 Checking files...")
main_py = backend_dir / 'main.py'
if not main_py.exists():
    print(f"   ❌ main.py not found at {main_py}")
    print("\n💡 You need to copy the fixed main.py to the backend directory")
    sys.exit(1)
else:
    print(f"   ✅ main.py found")

# Test 4: Check if pipeline directory exists
pipeline_dir = backend_dir / 'pipeline'
if not pipeline_dir.exists():
    print(f"   ❌ pipeline directory not found at {pipeline_dir}")
    sys.exit(1)
else:
    print(f"   ✅ pipeline directory found")

# Test 5: Import the main app
print("\n🔧 Testing main.py import...")

# Add backend directory to path if needed
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from main import app
    print("   ✅ main.py imported successfully")
    print(f"   ✅ App instance created: {type(app)}")
except ImportError as e:
    print(f"   ❌ Import error in main.py: {e}")
    print("\n💡 This means there's a missing dependency or import issue")
    
    # Try to get more details
    import traceback
    print("\n📋 Full error traceback:")
    traceback.print_exc()
    
    print("\n🔍 Common issues:")
    print("   1. Missing dependency in requirements.txt")
    print("   2. Pipeline module not found or has errors")
    print("   3. Missing data files")
    
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Other error: {type(e).__name__}: {e}")
    import traceback
    print("\n📋 Full error traceback:")
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check pipeline modules
print("\n📦 Testing pipeline modules...")
required_modules = [
    'pipeline.production_pipeline',
    'pipeline.clinical_validator',
    'pipeline.drug_filter',
    'pipeline.data_fetcher',
    'pipeline.graph_builder',
    'pipeline.scorer'
]

all_modules_ok = True
for module_name in required_modules:
    try:
        __import__(module_name)
        print(f"   ✅ {module_name}")
    except ImportError as e:
        print(f"   ❌ {module_name}: {e}")
        all_modules_ok = False
    except Exception as e:
        print(f"   ❌ {module_name}: {type(e).__name__}: {e}")
        all_modules_ok = False

if not all_modules_ok:
    print("\n💡 Some pipeline modules have errors. Check the error messages above.")
    sys.exit(1)

# Test 7: Try to run startup event
print("\n🚀 Testing startup event...")
try:
    import asyncio
    from main import startup_event
    
    print("   Running startup event...")
    asyncio.run(startup_event())
    print("   ✅ Startup event completed successfully")
    
except NameError:
    print("   ℹ️  No startup_event function found (this is OK)")
except Exception as e:
    print(f"   ⚠️  Startup event issue: {type(e).__name__}: {e}")
    import traceback
    print("\n📋 Full error traceback:")
    traceback.print_exc()
    
    print("\n💡 Note: This may not prevent the server from starting")

# Test 8: Check port availability
print("\n🔌 Checking port 8000...")
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 8000))
if result == 0:
    print("   ⚠️  Port 8000 is already in use!")
    print("   💡 Kill the process using: lsof -ti:8000 | xargs kill -9")
else:
    print("   ✅ Port 8000 is available")
sock.close()

print("\n" + "=" * 70)
print("✅ ALL CRITICAL DIAGNOSTICS PASSED!")
print("=" * 70)
print("\n💡 Backend should start successfully.")
print("\n🚀 To start the backend:")
print("   cd", backend_dir)
print("   uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
print("\n📝 Or use your startup script:")
print("   ./start.sh")
print()