# Navara AI - Drug Repurposing Platform

A production-grade AI-powered platform for discovering new therapeutic applications of FDA-approved drugs using advanced computational biology and machine learning.

## Overview

Navara AI accelerates drug discovery by identifying repurposing opportunities for existing FDA-approved medications. The platform integrates six major biomedical databases and uses graph-based machine learning to discover novel drug-disease relationships in real-time.

### Key Features

- Real-time analysis of 25,000+ diseases against 15,000+ FDA-approved drugs
- Integration with six authoritative medical databases
- Safety filtering system that automatically removes contraindicated drugs
- Clinical validation engine with trial data and literature evidence
- Graph-based knowledge representation of drug-gene-disease relationships
- Sub-5-second query response time after initial cache build

## System Architecture

### Backend Stack

- **Framework**: FastAPI with async/await architecture
- **Data Sources**: 
  - OpenTargets Platform (disease-gene associations)
  - ChEMBL (FDA-approved drugs)
  - DGIdb (drug-gene interactions)
  - ClinicalTrials.gov (clinical trial data)
  - PubMed (scientific literature)
  - OpenFDA (adverse event reports)
- **Graph Engine**: NetworkX for biological network analysis
- **Machine Learning**: Custom scoring algorithms with multi-factor weighted analysis

### Frontend Stack

- **Framework**: React 18 with Vite
- **Styling**: TailwindCSS with custom terminal-inspired theme
- **UI Design**: Monospace typography, graph paper backgrounds, brutalist aesthetic

## Installation

### Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher
- pip3 and npm package managers

### Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd navara-ai
```

2. Run the automated setup:
```bash
chmod +x setup_production_apis.sh
./setup_production_apis.sh
```

3. Start the application:
```bash
chmod +x start.sh
./start.sh
```

4. Access the platform:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Manual Installation

#### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Usage

### Basic Query

1. Enter a disease name (e.g., "Parkinson Disease")
2. Set minimum score threshold (default: 0.2)
3. Set maximum number of candidates (default: 10)
4. Click "Initiate Repurposing Analysis"

### Understanding Results

Each drug candidate includes:

- **Composite Score**: Overall match score (0-1 scale)
- **Confidence Level**: High, Medium, or Low based on evidence strength
- **Shared Genes**: Gene targets common to drug and disease
- **Shared Pathways**: Biological pathways modulated by both
- **Mechanism of Action**: How the drug works at molecular level
- **Clinical Validation**: Trial data, literature, safety signals

### Safety Filtering

The platform automatically filters drugs with:

- **Absolute Contraindications**: Never use (e.g., dopamine antagonists for Parkinson's)
- **Relative Contraindications**: Use with extreme caution (configurable)

Filtered drugs are displayed separately with clear explanations.

### Clinical Validation

Click "Validate Clinically" on any candidate to retrieve:

- Active clinical trials from ClinicalTrials.gov
- Published literature from PubMed
- Adverse event data from OpenFDA
- Mechanism compatibility analysis
- Overall risk assessment (Low/Medium/High)

## API Documentation

### POST /analyze

Analyze a disease and return drug repurposing candidates.

**Request Body:**
```json
{
  "disease_name": "string",
  "min_score": 0.2,
  "max_results": 10
}
```

**Response:**
```json
{
  "success": true,
  "disease": {
    "name": "string",
    "genes_count": 0,
    "pathways_count": 0,
    "top_genes": ["string"]
  },
  "candidates": [
    {
      "drug_name": "string",
      "score": 0.85,
      "confidence": "high",
      "shared_genes": ["string"],
      "shared_pathways": ["string"],
      "mechanism": "string",
      "explanation": "string"
    }
  ],
  "filtered_count": 0,
  "filtered_drugs": []
}
```

### POST /validate_clinical

Perform clinical validation on a drug-disease pair.

**Request Body:**
```json
{
  "drug_name": "string",
  "disease_name": "string",
  "drug_data": {},
  "disease_data": {}
}
```

**Response:**
```json
{
  "success": true,
  "validation": {
    "risk_level": "LOW",
    "recommendation": "string",
    "clinical_trials": {},
    "literature_evidence": {},
    "safety_signals": {},
    "mechanism_analysis": {}
  }
}
```

## Configuration

### Backend Configuration

Edit `backend/.env` (create if doesn't exist):

```env
# Server configuration
HOST=0.0.0.0
PORT=8000

# Cache configuration
CACHE_DIR=/tmp/drug_repurposing_cache
CACHE_DRUGS=true

# API rate limits
MAX_REQUESTS_PER_MINUTE=60

# Scoring thresholds
MIN_GENE_SCORE=0.1
MIN_PATHWAY_SCORE=0.1
```

### Frontend Configuration

Edit `frontend/vite.config.js`:

```javascript
export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

## Development

### Project Structure

```
navara-ai/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── models.py              # Pydantic data models
│   ├── requirements.txt       # Python dependencies
│   └── pipeline/
│       ├── data_fetcher.py    # Database integration
│       ├── graph_builder.py   # Knowledge graph construction
│       ├── scorer.py          # Scoring algorithms
│       ├── drug_filter.py     # Safety filtering
│       └── clinical_validator.py  # Clinical validation
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React component
│   │   ├── App.css           # Custom styles
│   │   └── main.jsx          # Entry point
│   ├── package.json          # Node dependencies
│   └── vite.config.js        # Vite configuration
├── start.sh                  # Startup script
├── stop.sh                   # Shutdown script
└── README.md                 # This file
```

### Running Tests

Backend tests:
```bash
cd backend
source venv/bin/activate
python -m pytest tests/
```

Database connectivity test:
```bash
cd backend
python test_production_apis.py
```

### Diagnostic Tools

Check why no candidates appear:
```bash
cd backend
python diagnose.py
```

Rebuild drug database cache:
```bash
python rebuild_database.py
```

## Performance Optimization

### First Query

- Duration: 5-10 seconds
- Reason: Building initial cache, fetching from APIs
- Impact: One-time operation per disease

### Subsequent Queries

- Duration: Less than 2 seconds
- Reason: Using cached data
- Impact: Production-ready response time

### Cache Management

Cache location: `/tmp/drug_repurposing_cache/`

Clear cache:
```bash
rm -rf /tmp/drug_repurposing_cache/
```

## Known Limitations

1. **Network Dependency**: Requires internet connection for initial data fetching
2. **Cache Persistence**: Cache stored in /tmp may be cleared on system restart
3. **API Rate Limits**: Some external APIs have rate limits (handled with exponential backoff)
4. **Disease Name Matching**: Requires exact or close disease names from OpenTargets database
5. **DGIdb Coverage**: Not all drugs have gene target information available

## Troubleshooting

### Backend fails to start

Check logs:
```bash
cat backend.log
```

Common issues:
- Port 8000 already in use: `lsof -ti:8000 | xargs kill -9`
- Missing dependencies: `pip install -r requirements.txt`
- Python version: Ensure Python 3.9+

### Frontend fails to start

Check logs:
```bash
cat frontend.log
```

Common issues:
- Port 3000 already in use: `lsof -ti:3000 | xargs kill -9`
- Missing node_modules: `cd frontend && npm install`
- Node version: Ensure Node.js 18+

### No candidates found

Possible causes:
1. Min score threshold too high (try 0.1-0.2)
2. Disease name not in OpenTargets (check spelling)
3. DGIdb API temporarily unavailable (check backend.log)
4. Cache corruption (clear cache and retry)

Run diagnostic:
```bash
cd backend
python diagnose.py
```

### SSL/Certificate errors

Update certificates:
```bash
pip install --upgrade certifi
```

## Contributing

This project is currently in active development. Contributions, issues, and feature requests are welcome.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Citation

If you use this platform in your research, please cite:

```
Navara AI Drug Repurposing Platform (2024)
Available at: [repository-url]
```

## Contact

For questions, support, or collaboration opportunities, please contact:

- Email: [your-email]
- Website: [your-website]
- LinkedIn: [your-linkedin]

## Acknowledgments

This platform integrates data from:

- OpenTargets Platform
- European Bioinformatics Institute (ChEMBL)
- Drug Gene Interaction Database (DGIdb)
- ClinicalTrials.gov (U.S. National Library of Medicine)
- PubMed (National Center for Biotechnology Information)
- OpenFDA (U.S. Food and Drug Administration)

## Version History

### Version 2.0.0 (Current)
- Production-ready API integration
- Safety filtering system
- Clinical validation engine
- Real-time database connectivity
- Enhanced scoring algorithms

### Version 1.0.0
- Initial prototype release
- Basic drug repurposing functionality
- Local database only

## Roadmap

### Planned Features

- Batch query processing for multiple diseases
- Export results to PDF/Excel
- User authentication and saved queries
- Drug combination analysis
- Molecular docking integration
- Machine learning model for score prediction
- Integration with additional databases (DrugBank, SIDER)
- API rate limiting and usage analytics
- Docker containerization
- Kubernetes deployment configuration

## Technical Specifications

### System Requirements

**Minimum:**
- 4 GB RAM
- 2 CPU cores
- 10 GB disk space
- Internet connection

**Recommended:**
- 8 GB RAM
- 4 CPU cores
- 20 GB disk space
- Stable internet connection

### Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### API Rate Limits

- OpenTargets: 10 requests/second
- ChEMBL: No official limit (use responsibly)
- DGIdb: No official limit (use responsibly)
- ClinicalTrials.gov: No official limit
- PubMed: 3 requests/second without API key
- OpenFDA: 240 requests/minute

## Security Considerations

- No user data is stored on servers
- All API calls are made server-side to protect keys
- CORS enabled for localhost development only
- Input sanitization on all user queries
- Rate limiting on API endpoints
- SSL/TLS for all external API communications

## Disclaimer

This platform is for research and informational purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. All drug repurposing suggestions must be validated through appropriate preclinical and clinical studies. Consult qualified medical professionals before making any healthcare decisions.
