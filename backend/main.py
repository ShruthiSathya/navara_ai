"""
FastAPI Backend for Drug Repurposing Platform
Uses production pipeline with real API integrations
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio

# Import production pipeline
from pipeline.production_pipeline import ProductionPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Drug Repurposing API",
    description="Find drug repurposing candidates using real databases",
    version="2.0.0"
)

# CORS middleware - CRITICAL for frontend to work
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline instance (reuses cache)
pipeline = None


class AnalyzeRequest(BaseModel):
    """Request model for disease analysis"""
    disease_name: str
    min_score: float = 0.2
    max_results: int = 20


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


@app.on_event("startup")
async def startup_event():
    """Initialize pipeline on startup"""
    global pipeline
    logger.info("🚀 Starting Drug Repurposing API...")
    logger.info("📊 Databases: OpenTargets, ChEMBL, DGIdb, ClinicalTrials.gov")
    pipeline = ProductionPipeline()
    logger.info("✅ API ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global pipeline
    if pipeline:
        await pipeline.close()
    logger.info("👋 API shutting down")


@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Drug Repurposing API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "API is running with production databases"
    }


@app.post("/analyze", tags=["Analysis"])
async def analyze_disease(request: AnalyzeRequest):
    """
    Analyze a disease and find drug repurposing candidates.
    
    This endpoint:
    1. Fetches disease data from OpenTargets
    2. Fetches approved drugs from ChEMBL
    3. Enhances with DGIdb interactions
    4. Scores drug-disease matches
    5. Returns ranked candidates
    
    Note: First query takes 30-60 seconds (fetching + caching drugs).
          Subsequent queries are <2 seconds (using cache).
    """
    global pipeline
    
    if not pipeline:
        raise HTTPException(
            status_code=503,
            detail="Pipeline not initialized. Please try again."
        )
    
    try:
        logger.info(f"📥 Received analysis request for: {request.disease_name}")
        logger.info(f"   Min score: {request.min_score}, Max results: {request.max_results}")
        
        # Run analysis
        result = await pipeline.analyze_disease(
            disease_name=request.disease_name,
            min_score=request.min_score,
            max_results=request.max_results
        )
        
        if not result.get('success'):
            logger.warning(f"❌ Analysis failed: {result.get('error')}")
            raise HTTPException(
                status_code=404,
                detail=result.get('error', 'Disease not found')
            )
        
        logger.info(f"✅ Analysis complete: {len(result.get('candidates', []))} candidates found")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/diseases/search", tags=["Search"])
async def search_diseases(query: str):
    """
    Search for diseases by name (future feature).
    Currently returns suggestions for common searches.
    """
    suggestions = [
        "Parkinson Disease",
        "Huntington Disease",
        "Gaucher Disease",
        "Wilson Disease",
        "Duchenne Muscular Dystrophy",
        "Cystic Fibrosis",
        "Alzheimer Disease",
        "ALS (Amyotrophic Lateral Sclerosis)",
    ]
    
    # Simple filter by query
    filtered = [d for d in suggestions if query.lower() in d.lower()]
    
    return {
        "query": query,
        "suggestions": filtered[:10]
    }


if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*70)
    print("🧬 Drug Repurposing Platform - Backend Server")
    print("="*70)
    print("\n📊 Connected to:")
    print("   • OpenTargets Platform (25,000+ diseases)")
    print("   • ChEMBL (15,000+ approved drugs)")
    print("   • DGIdb (50,000+ drug-gene interactions)")
    print("   • ClinicalTrials.gov (real-time trial data)")
    print("\n🌐 Starting server at: http://localhost:8000")
    print("📖 API Docs at: http://localhost:8000/docs")
    print("\n💡 Note: First query takes 30-60s (fetching + caching)")
    print("         Subsequent queries: <2 seconds\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )