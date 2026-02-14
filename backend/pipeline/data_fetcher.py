"""
PRODUCTION DATA FETCHER - REAL DATABASE INTEGRATIONS WITH SSL FIX
Uses: OpenTargets, ChEMBL, DGIdb, ClinicalTrials.gov
Handles SSL certificate verification issues
"""

import asyncio
import aiohttp
import ssl
import certifi
import json
import logging
from typing import Optional, List, Dict, Set
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductionDataFetcher:
    """
    Production-grade data fetcher with SSL certificate handling.
    Integrates multiple public databases for comprehensive analysis.
    """
    
    # API Endpoints (all FREE, no API keys needed!)
    OPENTARGETS_API = "https://api.platform.opentargets.org/api/v4/graphql"
    CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
    DGIDB_API = "https://dgidb.org/api/graphql"
    CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"
    
    def __init__(self, cache_dir: str = "/tmp/drug_repurposing_cache"):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory caches
        self.drug_cache = {}
        self.disease_cache = {}
        self.interaction_cache = {}
        
        # SSL context that handles certificate issues
        self.ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context that works around certificate verification issues.
        Uses certifi for up-to-date CA certificates.
        """
        try:
            # Try to use certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            logger.info("✅ Using certifi CA certificates")
            return ssl_context
        except Exception as e:
            logger.warning(f"⚠️  Certifi failed, trying alternative: {e}")
            
        try:
            # Alternative: create context with system certificates
            ssl_context = ssl.create_default_context()
            logger.info("✅ Using system CA certificates")
            return ssl_context
        except Exception as e:
            logger.warning(f"⚠️  System certs failed: {e}")
            
        # Last resort: disable verification (not recommended for production)
        logger.warning("⚠️  Using unverified SSL (not recommended for production)")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with SSL context and timeout"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        return self.session

    # ==================== DISEASE DATA ====================
    
    async def fetch_disease_data(self, disease_name: str) -> Optional[Dict]:
        """
        Main entry point: Fetch comprehensive disease data.
        Uses OpenTargets (covers rare + common diseases).
        """
        logger.info(f"🔍 Fetching disease data for: {disease_name}")
        
        # Check cache first
        cache_key = disease_name.lower().strip()
        if cache_key in self.disease_cache:
            logger.info("✅ Using cached disease data")
            return self.disease_cache[cache_key]
        
        # Fetch from OpenTargets
        data = await self._fetch_from_opentargets(disease_name)
        
        if data:
            # Enhance with pathway information
            data = await self._enhance_with_pathways(data)
            
            # Add clinical trial info
            data = await self._add_clinical_trials_count(data)
            
            # Check if it's a rare disease
            data = self._mark_rare_disease(data)
            
            # Cache it
            self.disease_cache[cache_key] = data
            logger.info(f"✅ Disease data ready: {data['name']} ({len(data['genes'])} genes, {len(data['pathways'])} pathways)")
        
        return data

    async def _fetch_from_opentargets(self, disease_name: str) -> Optional[Dict]:
        """
        Fetch from OpenTargets Platform.
        Covers 25,000+ diseases including rare diseases.
        """
        session = await self._get_session()
        
        # Step 1: Search for disease
        search_query = """
        query SearchDisease($query: String!) {
          search(queryString: $query, entityNames: ["disease"], page: {index: 0, size: 5}) {
            hits {
              id
              name
              description
              entity
            }
          }
        }
        """
        
        try:
            async with session.post(
                self.OPENTARGETS_API,
                json={"query": search_query, "variables": {"query": disease_name}},
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status != 200:
                    logger.error(f"❌ OpenTargets search failed: {resp.status}")
                    text = await resp.text()
                    logger.error(f"Response: {text[:200]}")
                    return None
                
                result = await resp.json()
                hits = result.get("data", {}).get("search", {}).get("hits", [])
                
                if not hits:
                    logger.warning(f"⚠️  No disease found in OpenTargets for: {disease_name}")
                    return None
                
                # Take the best match
                disease = hits[0]
                disease_id = disease["id"]
                found_name = disease["name"]
                
                logger.info(f"✅ Found disease: {found_name} (ID: {disease_id})")
            
            # Step 2: Fetch associated genes with scores
            targets_query = """
            query DiseaseTargets($efoId: String!) {
              disease(efoId: $efoId) {
                id
                name
                description
                associatedTargets(page: {index: 0, size: 200}) {
                  count
                  rows {
                    target {
                      id
                      approvedSymbol
                      approvedName
                      biotype
                    }
                    score
                  }
                }
              }
            }
            """
            
            async with session.post(
                self.OPENTARGETS_API,
                json={"query": targets_query, "variables": {"efoId": disease_id}},
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status != 200:
                    logger.error(f"❌ Failed to fetch disease targets")
                    return None
                
                result = await resp.json()
                disease_data = result.get("data", {}).get("disease", {})
                
                if not disease_data:
                    return None
                
                # Extract genes and scores
                rows = disease_data.get("associatedTargets", {}).get("rows", [])
                genes = []
                gene_scores = {}
                
                for row in rows:
                    target = row.get("target", {})
                    symbol = target.get("approvedSymbol")
                    score = row.get("score", 0)
                    
                    if symbol and score > 0.1:  # Filter low-confidence associations
                        genes.append(symbol)
                        gene_scores[symbol] = score
                
                logger.info(f"📊 Found {len(genes)} associated genes")
                
                return {
                    "name": found_name,
                    "id": disease_id,
                    "description": disease_data.get("description", "")[:500],
                    "genes": genes,
                    "gene_scores": gene_scores,
                    "pathways": [],  # Will be populated by _enhance_with_pathways
                    "source": "OpenTargets Platform"
                }
        
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error fetching from OpenTargets: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ OpenTargets fetch failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _enhance_with_pathways(self, disease_data: Dict) -> Dict:
        """
        Map disease genes to biological pathways.
        Uses curated knowledge for critical pathways.
        """
        genes = disease_data.get("genes", [])[:50]
        
        if not genes:
            disease_data["pathways"] = []
            return disease_data
        
        # Use curated pathway mapping
        pathways = self._map_genes_to_pathways(genes)
        disease_data["pathways"] = pathways
        
        return disease_data

    def _map_genes_to_pathways(self, genes: List[str]) -> List[str]:
        """
        Curated gene-to-pathway mapping based on biological knowledge.
        """
        pathway_map = {
            # Signal transduction
            "EGFR": ["EGFR signaling", "MAPK signaling", "PI3K-Akt signaling"],
            "KRAS": ["RAS signaling", "MAPK signaling", "PI3K-Akt signaling"],
            "PIK3CA": ["PI3K-Akt signaling", "mTOR signaling"],
            "PTEN": ["PI3K-Akt signaling", "Cell growth regulation"],
            "MTOR": ["mTOR signaling", "Autophagy", "Protein synthesis"],
            "TP53": ["p53 signaling", "Apoptosis", "DNA damage response", "Cell cycle"],
            "AKT1": ["PI3K-Akt signaling", "Cell survival"],
            
            # Inflammation & Immune
            "TNF": ["TNF signaling", "NF-κB signaling", "Inflammatory response", "Cytokine signaling"],
            "IL6": ["JAK-STAT signaling", "Cytokine signaling", "Acute phase response"],
            "IL1B": ["Inflammatory response", "Cytokine signaling"],
            "NFKB1": ["NF-κB signaling", "Inflammatory response"],
            "STAT3": ["JAK-STAT signaling", "Cytokine signaling"],
            
            # Metabolism
            "PPARG": ["Lipid metabolism", "Adipogenesis", "Insulin sensitivity"],
            "INSR": ["Insulin signaling", "Glucose metabolism"],
            "PRKAA1": ["AMPK signaling", "Energy metabolism"],
            "PRKAA2": ["AMPK signaling", "Autophagy"],
            
            # Lysosomal & Protein degradation
            "GBA": ["Lysosomal function", "Sphingolipid metabolism", "Autophagy"],
            "GAA": ["Glycogen metabolism", "Lysosomal storage"],
            "HEXA": ["Sphingolipid metabolism", "GM2 ganglioside degradation"],
            "HEXB": ["Sphingolipid metabolism", "Lysosomal storage"],
            "NPC1": ["Cholesterol trafficking", "Lysosomal function"],
            "NPC2": ["Cholesterol metabolism", "Lipid transport"],
            "LAMP1": ["Lysosomal function", "Autophagy"],
            "LAMP2": ["Autophagy", "Lysosomal membrane"],
            "ATP7B": ["Copper metabolism", "Metal ion homeostasis"],
            "GLA": ["Sphingolipid metabolism", "Lysosomal function"],
            "GALNS": ["Glycosaminoglycan metabolism", "Lysosomal storage"],
            
            # Neurodegeneration
            "SNCA": ["Alpha-synuclein aggregation", "Dopamine metabolism"],
            "LRRK2": ["Autophagy", "Mitochondrial function", "Vesicle trafficking"],
            "PRKN": ["Mitophagy", "Ubiquitin-proteasome system"],
            "PINK1": ["Mitophagy", "Mitochondrial quality control"],
            "DJ1": ["Oxidative stress response", "Mitochondrial function"],
            "HTT": ["Huntingtin aggregation", "Ubiquitin-proteasome system"],
            "APP": ["Amyloid-beta production", "APP processing"],
            "MAPT": ["Tau protein function", "Microtubule stability"],
            "SOD1": ["Oxidative stress response", "Superoxide metabolism"],
            "TDP43": ["RNA metabolism", "Protein aggregation"],
            "FUS": ["RNA metabolism", "Protein aggregation"],
            
            # Muscle & structural
            "DMD": ["Dystrophin-glycoprotein complex", "Muscle fiber integrity"],
            "CFTR": ["Chloride ion transport", "CFTR trafficking"],
            "FXN": ["Iron-sulfur cluster biogenesis", "Mitochondrial function"],
            
            # Cell cycle & proliferation
            "BRCA1": ["DNA repair", "Homologous recombination"],
            "BRCA2": ["DNA repair", "Genome stability"],
            "RB1": ["Cell cycle regulation", "G1/S checkpoint"],
            
            # Neurotransmission
            "DRD1": ["Dopamine signaling", "cAMP signaling"],
            "DRD2": ["Dopamine signaling", "G-protein coupled receptor"],
            "SLC6A3": ["Dopamine reuptake", "Neurotransmitter transport"],
            "TH": ["Dopamine biosynthesis", "Catecholamine synthesis"],
            "DDC": ["Dopamine biosynthesis", "Neurotransmitter synthesis"],
            "MAOB": ["Dopamine metabolism", "Monoamine oxidase"],
            
            # Additional key genes
            "PSEN1": ["Amyloid-beta production", "Gamma-secretase complex"],
            "PSEN2": ["Amyloid-beta production", "Gamma-secretase complex"],
            "APOE": ["Lipid metabolism", "Amyloid-beta clearance"],
            "GSK3B": ["Tau phosphorylation", "Wnt signaling"],
            "BACE1": ["Amyloid-beta production", "APP processing"],
        }
        
        pathways = set()
        for gene in genes:
            if gene in pathway_map:
                pathways.update(pathway_map[gene])
        
        # If we found pathways, return them; otherwise use generic
        if pathways:
            return sorted(list(pathways))
        else:
            return ["General cellular signaling", "Metabolic pathways"]

    def _mark_rare_disease(self, disease_data: Dict) -> Dict:
        """Mark if a disease is rare based on keywords or prevalence."""
        name = disease_data.get("name", "").lower()
        description = disease_data.get("description", "").lower()
        
        # Keywords that indicate rare disease
        rare_keywords = [
            "rare", "orphan", "syndrome", "dystrophy", "atrophy",
            "familial", "congenital", "hereditary", "genetic disorder",
            "lysosomal storage", "mitochondrial", "metabolic disorder"
        ]
        
        is_rare = any(keyword in name or keyword in description for keyword in rare_keywords)
        
        disease_data["is_rare"] = is_rare
        if is_rare:
            logger.info(f"🔬 Identified as RARE DISEASE: {disease_data['name']}")
        
        return disease_data

    async def _add_clinical_trials_count(self, disease_data: Dict) -> Dict:
        """Add count of active clinical trials for this disease"""
        try:
            session = await self._get_session()
            disease_name = disease_data["name"]
            
            async with session.get(
                self.CLINICALTRIALS_API,
                params={
                    "query.cond": disease_name,
                    "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
                    "pageSize": 1,
                    "format": "json",
                    "countTotal": "true"
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total = data.get("totalCount", 0)
                    disease_data["active_trials_count"] = total
                    logger.info(f"📋 Found {total} active clinical trials")
                else:
                    disease_data["active_trials_count"] = 0
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch clinical trials: {e}")
            disease_data["active_trials_count"] = 0
        
        return disease_data

    # ==================== DRUG DATA ====================
    
    async def fetch_approved_drugs(self, limit: int = 500) -> List[Dict]:
        """
        Fetch FDA/EMA approved drugs from ChEMBL.
        Returns drug name, targets, mechanism, SMILES, etc.
        """
        logger.info(f"💊 Fetching approved drugs from ChEMBL (limit={limit})...")
        
        # Check if we have cached drugs
        cache_file = self.cache_dir / "chembl_approved_drugs.json"
        if cache_file.exists():
            try:
                logger.info("✅ Loading drugs from cache")
                with open(cache_file, 'r') as f:
                    cached_drugs = json.load(f)
                    if len(cached_drugs) >= limit:
                        return cached_drugs[:limit]
            except Exception as e:
                logger.warning(f"⚠️  Cache read failed: {e}")
        
        # Fetch from ChEMBL
        drugs = await self._fetch_chembl_approved_drugs(limit)
        
        # Enhance with DGIdb interactions
        drugs = await self._enhance_with_dgidb(drugs)
        
        # Cache results
        try:
            with open(cache_file, 'w') as f:
                json.dump(drugs, f, indent=2)
            logger.info(f"✅ Cached {len(drugs)} drugs")
        except Exception as e:
            logger.warning(f"⚠️  Cache write failed: {e}")
        
        logger.info(f"✅ Fetched {len(drugs)} approved drugs")
        return drugs

    async def _fetch_chembl_approved_drugs(self, limit: int) -> List[Dict]:
        """Fetch approved drugs from ChEMBL database."""
        session = await self._get_session()
        drugs = []
        
        try:
            # ChEMBL API: Get molecules with max_phase=4 (approved)
            async with session.get(
                f"{self.CHEMBL_API}/molecule.json",
                params={
                    "max_phase": "4",
                    "limit": min(limit, 1000),
                    "offset": 0
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"❌ ChEMBL API failed: {resp.status}")
                    text = await resp.text()
                    logger.error(f"Response: {text[:200]}")
                    return []
                
                data = await resp.json()
                molecules = data.get("molecules", [])
                
                logger.info(f"📥 Processing {len(molecules)} molecules from ChEMBL...")
                
                # Process each molecule
                for i, mol in enumerate(molecules):
                    if i % 50 == 0 and i > 0:
                        logger.info(f"  ... processed {i}/{len(molecules)}")
                    
                    drug = self._process_chembl_molecule(mol)
                    if drug:
                        drugs.append(drug)
        
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error fetching from ChEMBL: {e}")
        except Exception as e:
            logger.error(f"❌ ChEMBL fetch failed: {e}")
            import traceback
            traceback.print_exc()
        
        return drugs

    def _process_chembl_molecule(self, molecule: Dict) -> Optional[Dict]:
        """Convert ChEMBL molecule to our drug format"""
        try:
            chembl_id = molecule.get("molecule_chembl_id")
            name = molecule.get("pref_name") or chembl_id
            
            # Skip if no name
            if not name or name == chembl_id:
                return None
            
            # Get structure
            structures = molecule.get("molecule_structures", {})
            smiles = structures.get("canonical_smiles", "")
            
            # Get basic info
            drug = {
                "id": chembl_id,
                "name": name,
                "indication": molecule.get("indication_class", "Various indications"),
                "mechanism": molecule.get("mechanism_of_action", ""),
                "approved": True,
                "smiles": smiles,
                "targets": [],  # Will be filled by DGIdb
                "pathways": []  # Will be inferred from targets
            }
            
            return drug
        
        except Exception:
            return None

    async def _enhance_with_dgidb(self, drugs: List[Dict]) -> List[Dict]:
        """
        Enhance drugs with gene targets from DGIdb.
        DGIdb has 50,000+ drug-gene interactions!
        """
        logger.info("🔗 Enhancing drugs with DGIdb interactions...")
        
        session = await self._get_session()
        
        # Batch query to DGIdb (limit to first 100 for speed)
        # Normalize names: DGIdb is case-sensitive, prefers Title Case
        drug_names = [d["name"].title() for d in drugs[:100]]
        
        try:
            # DGIdb GraphQL query
            query = """
            query DrugInteractions($names: [String!]!) {
              drugs(names: $names) {
                name
                interactions {
                  gene {
                    name
                  }
                  interactionTypes {
                    type
                  }
                }
              }
            }
            """
            
            async with session.post(
                self.DGIDB_API,
                json={"query": query, "variables": {"names": drug_names}},
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    dgidb_drugs = result.get("data", {}).get("drugs", [])
                    
                    # Map drug names to targets
                    drug_target_map = {}
                    for dgidb_drug in dgidb_drugs:
                        if dgidb_drug:
                            name = dgidb_drug.get("name", "").lower()
                            interactions = dgidb_drug.get("interactions", [])
                            targets = [i["gene"]["name"] for i in interactions if i.get("gene")]
                            drug_target_map[name] = targets
                    
                    # Update our drugs
                    for drug in drugs:
                        drug_name_lower = drug["name"].lower()
                        drug_name_title = drug["name"].title()
                        
                        # Try both lowercase and title case matching
                        if drug_name_lower in drug_target_map:
                            drug["targets"] = drug_target_map[drug_name_lower]
                            drug["pathways"] = self._infer_pathways_from_targets(drug["targets"])
                        elif drug_name_title.lower() in drug_target_map:
                            drug["targets"] = drug_target_map[drug_name_title.lower()]
                            drug["pathways"] = self._infer_pathways_from_targets(drug["targets"])
                    
                    logger.info(f"✅ Enhanced {len(drug_target_map)} drugs with DGIdb data")
                else:
                    logger.warning(f"⚠️  DGIdb returned status {resp.status}")
        
        except aiohttp.ClientError as e:
            logger.warning(f"⚠️  Network error with DGIdb: {e}")
        except Exception as e:
            logger.warning(f"⚠️  DGIdb enhancement failed: {e}")
            import traceback
            traceback.print_exc()
        
        return drugs

    def _infer_pathways_from_targets(self, targets: List[str]) -> List[str]:
        """Infer pathways from drug targets"""
        pathways = set()
        for target in targets[:20]:  # Limit to first 20 targets
            target_pathways = self._map_genes_to_pathways([target])
            pathways.update(target_pathways)
        return list(pathways)

    # ==================== CLEANUP ====================
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 Session closed")


# Maintain backward compatibility
DataFetcher = ProductionDataFetcher