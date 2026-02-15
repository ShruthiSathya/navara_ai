"""
Database-Driven Drug Safety Filter
Uses OpenFDA API to dynamically fetch contraindications and warnings

This replaces hardcoded rules with real-time data from FDA drug labels
"""

import aiohttp
import asyncio
from typing import List, Dict, Tuple, Optional
import logging
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


class DatabaseDrivenSafetyFilter:
    """
    Intelligent drug safety filter that pulls contraindications from:
    1. OpenFDA Drug Labels API (contraindications, warnings, boxed warnings)
    2. OpenFDA Adverse Events API (statistical analysis of serious events)
    3. Local cache to reduce API calls
    """
    
    def __init__(self, cache_ttl: int = 86400):
        """
        Initialize the database-driven filter.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 24 hours)
        """
        self.openfda_base = "https://api.fda.gov"
        self.cache = {}  # In-memory cache
        self.cache_ttl = cache_ttl
        
        # Disease-specific keywords to search for in contraindications
        self.disease_keywords = {
            "diabetes": [
                "diabetes", "diabetic", "hyperglycemia", "glucose", "insulin resistance",
                "blood sugar", "glycemic control", "diabetic patients"
            ],
            "parkinson": [
                "parkinson", "parkinsonian", "dopamine", "extrapyramidal", 
                "movement disorder", "tremor", "rigidity"
            ],
            "alzheimer": [
                "alzheimer", "dementia", "cognitive", "memory", "cholinergic",
                "anticholinergic", "acetylcholine"
            ],
            "asthma": [
                "asthma", "bronchospasm", "broncho", "airway", "respiratory",
                "breathing", "wheezing", "beta-blocker"
            ],
            "epilepsy": [
                "epilepsy", "seizure", "convulsion", "seizure threshold"
            ],
            "hypertension": [
                "hypertension", "blood pressure", "hypertensive", "elevated blood pressure"
            ],
            "heart_failure": [
                "heart failure", "cardiac failure", "congestive", "cardiomyopathy",
                "ventricular dysfunction"
            ],
            "copd": [
                "copd", "chronic obstructive", "emphysema", "chronic bronchitis",
                "respiratory", "bronchospasm"
            ],
            "glaucoma": [
                "glaucoma", "intraocular pressure", "narrow-angle", "angle-closure"
            ],
            "osteoporosis": [
                "osteoporosis", "bone", "fracture", "bone density", "bone loss"
            ],
            "crohn": [
                "crohn", "inflammatory bowel", "ibd", "intestinal inflammation"
            ],
            "rheumatoid_arthritis": [
                "infection", "tuberculosis", "immunosuppression", "live vaccine"
            ],
            "depression": [
                "depression", "suicidal", "mood", "psychiatric"
            ]
        }
        
        # Known problematic drug-disease combinations
        # Used as backup when API data is insufficient
        self.critical_contraindications = {
            "diabetes": {
                "drugs": ["olanzapine", "clozapine", "quetiapine", "risperidone"],
                "reason": "Atypical antipsychotics cause metabolic syndrome and diabetes"
            },
            "asthma": {
                "drugs": ["propranolol", "atenolol", "metoprolol", "nadolol", "timolol"],
                "reason": "Beta-blockers cause life-threatening bronchospasm"
            },
            "parkinson": {
                "drugs": ["perphenazine", "haloperidol", "olanzapine", "metoclopramide"],
                "reason": "Dopamine antagonists worsen Parkinson's symptoms"
            }
        }
        
        # Drugs withdrawn from market (always filter)
        self.withdrawn_drugs = {
            "troglitazone", "rofecoxib", "cerivastatin", "fenfluramine",
            "terfenadine", "valdecoxib", "pemoline", "propoxyphene"
        }
    
    def _normalize_disease_name(self, disease_name: str) -> str:
        """Normalize disease name to match our keyword dictionary."""
        disease_lower = disease_name.lower().strip()
        
        mappings = {
            "parkinson": "parkinson",
            "parkinson's": "parkinson",
            "parkinson disease": "parkinson",
            "parkinsonian disorder": "parkinson",
            "alzheimer": "alzheimer",
            "alzheimer's": "alzheimer",
            "alzheimer disease": "alzheimer",
            "diabetes": "diabetes",
            "diabetes mellitus": "diabetes",
            "type 2 diabetes": "diabetes",
            "diabetes mellitus type 2": "diabetes",
            "asthma": "asthma",
            "copd": "copd",
            "chronic obstructive pulmonary disease": "copd",
            "epilepsy": "epilepsy",
            "seizure": "epilepsy",
            "hypertension": "hypertension",
            "high blood pressure": "hypertension",
            "heart failure": "heart_failure",
            "glaucoma": "glaucoma",
            "osteoporosis": "osteoporosis",
            "crohn": "crohn",
            "crohn disease": "crohn",
            "crohn's disease": "crohn",
            "rheumatoid arthritis": "rheumatoid_arthritis",
            "depression": "depression",
            "major depressive disorder": "depression"
        }
        
        for key, value in mappings.items():
            if key in disease_lower:
                return value
        
        return disease_lower.replace(" ", "_")
    
    async def _fetch_drug_label(self, drug_name: str) -> Optional[Dict]:
        """
        Fetch drug label data from OpenFDA API.
        Returns contraindications, warnings, and boxed warnings.
        """
        # Check cache first
        cache_key = f"label_{drug_name}"
        if cache_key in self.cache:
            logger.debug(f"Cache hit for {drug_name} label")
            return self.cache[cache_key]
        
        try:
            # Search for drug label
            url = f"{self.openfda_base}/drug/label.json"
            params = {
                "search": f'openfda.generic_name:"{drug_name}"',
                "limit": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('results'):
                            result = data['results'][0]
                            
                            # Extract relevant sections
                            label_data = {
                                "contraindications": result.get('contraindications', []),
                                "warnings": result.get('warnings', []),
                                "boxed_warning": result.get('boxed_warning', []),
                                "warnings_and_cautions": result.get('warnings_and_cautions', []),
                                "precautions": result.get('precautions', []),
                                "adverse_reactions": result.get('adverse_reactions', [])
                            }
                            
                            # Cache the result
                            self.cache[cache_key] = label_data
                            logger.info(f"✅ Fetched label for {drug_name}")
                            return label_data
                        else:
                            logger.warning(f"No label found for {drug_name}")
                            return None
                    else:
                        logger.warning(f"FDA API returned {response.status} for {drug_name}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching label for {drug_name}")
            return None
        except Exception as e:
            logger.error(f"Error fetching label for {drug_name}: {e}")
            return None
    
    async def _analyze_serious_adverse_events(
        self, 
        drug_name: str, 
        disease_name: str
    ) -> Dict:
        """
        Analyze serious adverse events from FAERS database.
        Returns statistics on serious events related to the disease.
        """
        cache_key = f"adverse_{drug_name}_{disease_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Get disease keywords
            normalized_disease = self._normalize_disease_name(disease_name)
            keywords = self.disease_keywords.get(normalized_disease, [disease_name.lower()])
            
            # Search for serious adverse events
            url = f"{self.openfda_base}/drug/event.json"
            
            # Build search query for serious events with disease-related reactions
            search_terms = []
            for keyword in keywords[:3]:  # Limit to top 3 keywords
                search_terms.append(f'patient.reaction.reactionmeddrapt:"{keyword}"')
            
            params = {
                "search": f'patient.drug.medicinalproduct:"{drug_name}" AND serious:1 AND ({" OR ".join(search_terms)})',
                "count": "patient.reaction.reactionmeddrapt.exact",
                "limit": 10
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        result = {
                            "serious_event_count": sum(r['count'] for r in data.get('results', [])),
                            "top_reactions": [
                                {"reaction": r['term'], "count": r['count']} 
                                for r in data.get('results', [])[:5]
                            ]
                        }
                        
                        self.cache[cache_key] = result
                        logger.info(f"✅ Analyzed adverse events for {drug_name} + {disease_name}")
                        return result
                    else:
                        return {"serious_event_count": 0, "top_reactions": []}
                        
        except Exception as e:
            logger.error(f"Error analyzing adverse events for {drug_name}: {e}")
            return {"serious_event_count": 0, "top_reactions": []}
    
    def _check_label_for_contraindication(
        self, 
        label_data: Dict, 
        disease_keywords: List[str]
    ) -> Tuple[bool, str]:
        """
        Check if drug label contains contraindications for the disease.
        Returns (is_contraindicated, reason)
        """
        if not label_data:
            return False, ""
        
        # Check each section
        sections_to_check = [
            'contraindications',
            'boxed_warning',
            'warnings',
            'warnings_and_cautions',
            'precautions'
        ]
        
        for section_name in sections_to_check:
            section_content = label_data.get(section_name, [])
            
            # Join all text in section
            if isinstance(section_content, list):
                text = " ".join(section_content).lower()
            else:
                text = str(section_content).lower()
            
            # Check if any disease keyword appears in this section
            for keyword in disease_keywords:
                if keyword in text:
                    # Extract context around the keyword
                    idx = text.find(keyword)
                    start = max(0, idx - 100)
                    end = min(len(text), idx + 200)
                    context = text[start:end]
                    
                    # Clean up the context
                    reason = context.replace('\n', ' ').strip()
                    if len(reason) > 200:
                        reason = reason[:200] + "..."
                    
                    logger.info(f"Found contraindication: {keyword} in {section_name}")
                    return True, f"FDA label {section_name} mentions: {reason}"
        
        return False, ""
    
    async def filter_candidates(
        self,
        candidates: List[Dict],
        disease_name: str,
        remove_absolute: bool = True,
        remove_relative: bool = False,
        use_adverse_events: bool = True,
        serious_event_threshold: int = 100
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter drug candidates using database-driven approach.
        
        Args:
            candidates: List of drug candidates
            disease_name: Disease being treated
            remove_absolute: Remove absolutely contraindicated drugs
            remove_relative: Remove relatively contraindicated drugs
            use_adverse_events: Use adverse event statistics
            serious_event_threshold: Minimum serious events to flag
            
        Returns:
            (safe_candidates, filtered_out_candidates)
        """
        normalized_disease = self._normalize_disease_name(disease_name)
        disease_keywords = self.disease_keywords.get(
            normalized_disease, 
            [disease_name.lower()]
        )
        
        logger.info(f"🔍 Database-driven filtering for '{disease_name}' (normalized: '{normalized_disease}')")
        logger.info(f"Disease keywords: {disease_keywords}")
        
        safe_candidates = []
        filtered_out = []
        
        # Process each candidate
        for candidate in candidates:
            drug_name = candidate.get('drug_name', '').lower().strip()
            
            # Check if drug is withdrawn from market
            if drug_name in self.withdrawn_drugs:
                candidate['contraindication_reason'] = f"WITHDRAWN from market - should not be used"
                candidate['contraindication_severity'] = 'absolute'
                candidate['contraindication_source'] = 'market_withdrawal'
                filtered_out.append(candidate)
                logger.info(f"❌ FILTERED (withdrawn): {drug_name}")
                continue
            
            # Check critical contraindications (backup for API failures)
            critical_rules = self.critical_contraindications.get(normalized_disease, {})
            if drug_name in critical_rules.get('drugs', []):
                candidate['contraindication_reason'] = critical_rules['reason']
                candidate['contraindication_severity'] = 'absolute'
                candidate['contraindication_source'] = 'critical_rule'
                filtered_out.append(candidate)
                logger.info(f"❌ FILTERED (critical rule): {drug_name}")
                continue
            
            # Fetch FDA drug label
            label_data = await self._fetch_drug_label(drug_name)
            
            if label_data:
                # Check label for contraindications
                is_contraindicated, reason = self._check_label_for_contraindication(
                    label_data, 
                    disease_keywords
                )
                
                if is_contraindicated and remove_absolute:
                    candidate['contraindication_reason'] = reason
                    candidate['contraindication_severity'] = 'absolute'
                    candidate['contraindication_source'] = 'fda_label'
                    filtered_out.append(candidate)
                    logger.info(f"❌ FILTERED (FDA label): {drug_name}")
                    continue
            else:
                logger.warning(f"⚠️ No FDA label data for {drug_name}")
            
            # Analyze adverse events (if enabled)
            if use_adverse_events:
                adverse_data = await self._analyze_serious_adverse_events(
                    drug_name, 
                    disease_name
                )
                
                if adverse_data['serious_event_count'] >= serious_event_threshold:
                    top_reactions = [r['reaction'] for r in adverse_data['top_reactions'][:3]]
                    
                    if remove_relative:
                        candidate['contraindication_reason'] = (
                            f"High rate of serious adverse events related to {disease_name} "
                            f"({adverse_data['serious_event_count']} reports): {', '.join(top_reactions)}"
                        )
                        candidate['contraindication_severity'] = 'relative'
                        candidate['contraindication_source'] = 'adverse_events'
                        filtered_out.append(candidate)
                        logger.info(f"⚠️ FILTERED (adverse events): {drug_name}")
                        continue
                    else:
                        # Add warning but don't filter
                        candidate['safety_warning'] = (
                            f"Note: {adverse_data['serious_event_count']} serious adverse "
                            f"events reported related to {disease_name}"
                        )
                        logger.info(f"⚠️ WARNING added for {drug_name}")
            
            # Candidate passed all checks
            safe_candidates.append(candidate)
        
        logger.info(
            f"✅ Filtering complete: {len(safe_candidates)} safe, "
            f"{len(filtered_out)} filtered"
        )
        
        return safe_candidates, filtered_out
    
    def clear_cache(self):
        """Clear the internal cache."""
        self.cache = {}
        logger.info("Cache cleared")


# Alias for backward compatibility
DrugSafetyFilter = DatabaseDrivenSafetyFilter


# Testing
if __name__ == "__main__":
    async def test_filter():
        filter = DatabaseDrivenSafetyFilter()
        
        test_cases = [
            ("olanzapine", "Type 2 Diabetes"),
            ("propranolol", "Asthma"),
            ("diphenhydramine", "Alzheimer's Disease"),
            ("perphenazine", "Parkinson's Disease"),
            ("metformin", "Type 2 Diabetes"),
        ]
        
        print("=" * 70)
        print("DATABASE-DRIVEN DRUG SAFETY FILTER TEST")
        print("=" * 70)
        print()
        
        for drug, disease in test_cases:
            candidates = [{"drug_name": drug, "score": 0.8}]
            safe, filtered = await filter.filter_candidates(
                candidates, 
                disease,
                use_adverse_events=False  # Disable for testing speed
            )
            
            print(f"Drug: {drug}, Disease: {disease}")
            if filtered:
                reason = filtered[0].get('contraindication_reason', 'No reason')
                source = filtered[0].get('contraindication_source', 'unknown')
                print(f"  ❌ FILTERED ({source}): {reason[:100]}")
            else:
                print(f"  ✅ SAFE")
            print()
    
    # Run async test
    asyncio.run(test_filter())