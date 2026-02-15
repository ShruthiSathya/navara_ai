"""
FIXED PRODUCTION DATA FETCHER
Uses: OpenTargets, ChEMBL, DGIdb, ClinicalTrials.gov

KEY FIX: DGIdb's `drugs()` query returns a DrugConnection.
         Access drug records via .nodes[].
         Drug.interactions is a flat [Interaction] list — no edges wrapping.
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
    FIXED: DGIdb integration uses the correct flat-list schema.
    """

    # API Endpoints
    OPENTARGETS_API = "https://api.platform.opentargets.org/api/v4/graphql"
    CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
    DGIDB_API = "https://dgidb.org/api/graphql"
    CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self, cache_dir: str = "/tmp/drug_repurposing_cache"):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # In-memory caches
        self.drug_cache: Dict = {}
        self.disease_cache: Dict = {}
        self.interaction_cache: Dict = {}

        # SSL context
        self.ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with certifi certificates."""
        try:
            ctx = ssl.create_default_context(cafile=certifi.where())
            logger.info("✅ Using certifi CA certificates")
            return ctx
        except Exception as e:
            logger.warning(f"⚠️  Certifi failed: {e}")
            return ssl.create_default_context()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(
                timeout=timeout, connector=connector
            )
        return self.session

    # ══════════════════════════════════════════════════════════════════════════
    #  DISEASE DATA
    # ══════════════════════════════════════════════════════════════════════════

    async def fetch_disease_data(self, disease_name: str) -> Optional[Dict]:
        """Fetch comprehensive disease data from OpenTargets."""
        logger.info(f"🔍 Fetching disease data for: {disease_name}")

        cache_key = disease_name.lower().strip()
        if cache_key in self.disease_cache:
            logger.info("✅ Using cached disease data")
            return self.disease_cache[cache_key]

        data = await self._fetch_from_opentargets(disease_name)

        if data:
            data = await self._enhance_with_pathways(data)
            data = await self._add_clinical_trials_count(data)
            data = self._mark_rare_disease(data)
            self.disease_cache[cache_key] = data
            logger.info(
                f"✅ Disease data ready: {data['name']} "
                f"({len(data['genes'])} genes, {len(data['pathways'])} pathways)"
            )

        return data

    async def _fetch_from_opentargets(self, disease_name: str) -> Optional[Dict]:
        """Fetch disease and associated genes from OpenTargets."""
        session = await self._get_session()

        search_query = """
        query SearchDisease($query: String!) {
          search(queryString: $query, entityNames: ["disease"],
                 page: {index: 0, size: 5}) {
            hits { id name description entity }
          }
        }
        """
        try:
            async with session.post(
                self.OPENTARGETS_API,
                json={"query": search_query, "variables": {"query": disease_name}},
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"❌ OpenTargets search failed: {resp.status}")
                    return None
                result = await resp.json()
                hits = result.get("data", {}).get("search", {}).get("hits", [])
                if not hits:
                    logger.warning(f"⚠️  Disease not found: {disease_name}")
                    return None
                disease = hits[0]
                disease_id = disease["id"]
                found_name = disease["name"]
                logger.info(f"✅ Found disease: {found_name} (ID: {disease_id})")

            targets_query = """
            query DiseaseTargets($efoId: String!) {
              disease(efoId: $efoId) {
                id name description
                associatedTargets(page: {index: 0, size: 200}) {
                  count
                  rows {
                    target {
                      id approvedSymbol approvedName biotype
                    }
                    score
                  }
                }
              }
            }
            """
            async with session.post(
                self.OPENTARGETS_API,
                json={
                    "query": targets_query,
                    "variables": {"efoId": disease_id},
                },
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    logger.error("❌ Failed to fetch disease targets")
                    return None
                result = await resp.json()
                disease_data = result.get("data", {}).get("disease", {})
                if not disease_data:
                    return None

                rows = disease_data.get("associatedTargets", {}).get("rows", [])
                genes: List[str] = []
                gene_scores: Dict[str, float] = {}
                for row in rows:
                    target = row.get("target", {})
                    symbol = target.get("approvedSymbol")
                    score = row.get("score", 0)
                    if symbol and score > 0.1:
                        genes.append(symbol)
                        gene_scores[symbol] = score

                logger.info(f"📊 Found {len(genes)} associated genes")
                return {
                    "name": found_name,
                    "id": disease_id,
                    "description": disease_data.get("description", "")[:500],
                    "genes": genes,
                    "gene_scores": gene_scores,
                    "pathways": [],
                    "source": "OpenTargets Platform",
                }

        except Exception as e:
            logger.error(f"❌ OpenTargets fetch failed: {e}")
            return None

    async def _enhance_with_pathways(self, disease_data: Dict) -> Dict:
        genes = disease_data.get("genes", [])[:50]
        disease_data["pathways"] = self._map_genes_to_pathways(genes) if genes else []
        return disease_data

    def _map_genes_to_pathways(self, genes: List[str]) -> List[str]:
        pathway_map = {
            "SNCA": ["Alpha-synuclein aggregation", "Dopamine metabolism", "Autophagy"],
            "LRRK2": ["Autophagy", "Mitochondrial function", "Vesicle trafficking"],
            "PRKN": ["Mitophagy", "Ubiquitin-proteasome system"],
            "PINK1": ["Mitophagy", "Mitochondrial quality control"],
            "PARK7": ["Oxidative stress response", "Mitochondrial function"],
            "DJ1":   ["Oxidative stress response", "Mitochondrial function"],
            "GBA":   ["Lysosomal function", "Sphingolipid metabolism", "Autophagy"],
            "GBA1":  ["Lysosomal function", "Sphingolipid metabolism", "Autophagy"],
            "MAOB":  ["Dopamine metabolism", "Monoamine oxidase"],
            "TH":    ["Dopamine biosynthesis", "Catecholamine synthesis"],
            "DDC":   ["Dopamine biosynthesis", "Neurotransmitter synthesis"],
            "LAMP1": ["Lysosomal function", "Autophagy"],
            "LAMP2": ["Autophagy", "Lysosomal membrane"],
            "ATP7B": ["Copper metabolism", "Metal ion homeostasis"],
            "NPC1":  ["Cholesterol trafficking", "Lysosomal function"],
            "NPC2":  ["Cholesterol metabolism", "Lipid transport"],
            "HTT":   ["Huntingtin aggregation", "Ubiquitin-proteasome system"],
            "APP":   ["Amyloid-beta production", "APP processing"],
            "MAPT":  ["Tau protein function", "Microtubule stability"],
            "PSEN1": ["Amyloid-beta production", "Gamma-secretase complex"],
            "PSEN2": ["Amyloid-beta production", "Gamma-secretase complex"],
            "APOE":  ["Lipid metabolism", "Amyloid-beta clearance"],
            "DMD":   ["Dystrophin-glycoprotein complex", "Muscle fiber integrity"],
            "CFTR":  ["Chloride ion transport", "CFTR trafficking"],
            "EGFR":  ["EGFR signaling", "MAPK signaling"],
            "KRAS":  ["RAS signaling", "MAPK signaling"],
            "PIK3CA":["PI3K-Akt signaling", "mTOR signaling"],
            "PTEN":  ["PI3K-Akt signaling", "Cell growth regulation"],
            "MTOR":  ["mTOR signaling", "Autophagy", "Protein synthesis"],
            "TP53":  ["p53 signaling", "Apoptosis", "DNA damage response"],
            "TNF":   ["TNF signaling", "NF-κB signaling", "Inflammatory response"],
            "IL6":   ["JAK-STAT signaling", "Cytokine signaling"],
            "NFKB1": ["NF-κB signaling", "Inflammatory response"],
        }
        pathways: Set[str] = set()
        for gene in genes:
            if gene in pathway_map:
                pathways.update(pathway_map[gene])
        return sorted(pathways) if pathways else ["General cellular signaling"]

    def _mark_rare_disease(self, disease_data: Dict) -> Dict:
        name = disease_data.get("name", "").lower()
        desc = disease_data.get("description", "").lower()
        rare_kw = [
            "rare", "orphan", "syndrome", "dystrophy", "atrophy",
            "familial", "congenital", "hereditary", "genetic disorder",
            "lysosomal storage", "mitochondrial", "metabolic disorder",
        ]
        disease_data["is_rare"] = any(k in name or k in desc for k in rare_kw)
        if disease_data["is_rare"]:
            logger.info(f"🔬 Identified as RARE DISEASE: {disease_data['name']}")
        return disease_data

    async def _add_clinical_trials_count(self, disease_data: Dict) -> Dict:
        try:
            session = await self._get_session()
            async with session.get(
                self.CLINICALTRIALS_API,
                params={
                    "query.cond": disease_data["name"],
                    "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
                    "pageSize": 1,
                    "format": "json",
                    "countTotal": "true",
                },
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

    # ══════════════════════════════════════════════════════════════════════════
    #  DRUG DATA
    # ══════════════════════════════════════════════════════════════════════════

    async def fetch_approved_drugs(self, limit: int = 500) -> List[Dict]:
        """Fetch approved drugs from ChEMBL then enrich via DGIdb."""
        logger.info(f"💊 Fetching approved drugs from ChEMBL (limit={limit})...")

        cache_file = self.cache_dir / "chembl_approved_drugs.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                if len(cached) >= limit:
                    logger.info("✅ Loading drugs from cache")
                    return cached[:limit]
            except Exception as e:
                logger.warning(f"⚠️  Cache read failed: {e}")

        drugs = await self._fetch_chembl_approved_drugs(limit)
        if not drugs:
            logger.error("❌ No drugs fetched from ChEMBL!")
            return []

        logger.info(f"🔗 Enhancing {len(drugs)} drugs with DGIdb targets...")
        drugs = await self._enhance_with_dgidb(drugs)

        try:
            with open(cache_file, "w") as f:
                json.dump(drugs, f, indent=2)
            logger.info(f"✅ Cached {len(drugs)} drugs")
        except Exception as e:
            logger.warning(f"⚠️  Cache write failed: {e}")

        return drugs

    async def _fetch_chembl_approved_drugs(self, limit: int) -> List[Dict]:
        """Fetch FDA-approved drugs from ChEMBL."""
        session = await self._get_session()
        drugs: List[Dict] = []
        try:
            async with session.get(
                f"{self.CHEMBL_API}/molecule.json",
                params={"max_phase": "4", "limit": min(limit, 1000), "offset": 0},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"❌ ChEMBL API failed: {resp.status}")
                    return []
                data = await resp.json()
                molecules = data.get("molecules", [])
                logger.info(f"📥 Processing {len(molecules)} molecules from ChEMBL...")
                for i, mol in enumerate(molecules):
                    if i % 50 == 0 and i > 0:
                        logger.info(f"  ... processed {i}/{len(molecules)}")
                    drug = self._process_chembl_molecule(mol)
                    if drug:
                        drugs.append(drug)
        except Exception as e:
            logger.error(f"❌ ChEMBL fetch failed: {e}")
        return drugs

    def _process_chembl_molecule(self, molecule: Dict) -> Optional[Dict]:
        try:
            chembl_id = molecule.get("molecule_chembl_id")
            name = molecule.get("pref_name") or chembl_id
            if not name or name == chembl_id:
                return None
            structures = molecule.get("molecule_structures", {})
            smiles = structures.get("canonical_smiles", "") if structures else ""
            return {
                "id": chembl_id,
                "name": name,
                "indication": molecule.get("indication_class", "Various indications"),
                "mechanism": molecule.get("mechanism_of_action", ""),
                "approved": True,
                "smiles": smiles,
                "targets": [],
                "pathways": [],
            }
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    #  FIXED DGIdb ENHANCEMENT
    #  The interactions field on Drug returns [Interaction] directly.
    #  There is NO edges/node wrapping.
    # ──────────────────────────────────────────────────────────────────────────

    async def _enhance_with_dgidb(self, drugs: List[Dict]) -> List[Dict]:
        """
        Enrich drugs with gene targets from DGIdb.

        Correct schema (as of current DGIdb API):
            drugs(names: [String!]) → DrugConnection
            DrugConnection.nodes     → [Drug]
            Drug.interactions        → [Interaction]     ← flat list, no edges
            Interaction.gene         → Gene
            Gene.name                → String
        """
        session = await self._get_session()

        # DGIdb GraphQL query — drugs() returns DrugConnection, use .nodes
        DGIDB_QUERY = """
        query DrugInteractions($names: [String!]!) {
          drugs(names: $names) {
            nodes {
              name
              conceptId
              approved
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
        }
        """

        # Build name list in batches of 100 (avoid huge payloads)
        BATCH_SIZE = 100
        all_drug_names_upper = [d["name"].upper() for d in drugs]
        all_drug_names_title = [d["name"].title() for d in drugs]

        # We'll try both UPPER and Title-case to maximise DGIdb matches
        name_variants = [all_drug_names_upper, all_drug_names_title]
        label       = ["UPPER", "Title"]

        # drug_target_map: lowercase_name → [gene, ...]
        drug_target_map: Dict[str, List[str]] = {}

        for variant_list, var_label in zip(name_variants, label):
            if drug_target_map:
                # Already populated from first pass; do second pass only for extras
                pass

            for batch_start in range(0, len(variant_list), BATCH_SIZE):
                batch = variant_list[batch_start : batch_start + BATCH_SIZE]
                logger.info(
                    f"🔗 DGIdb batch {batch_start//BATCH_SIZE + 1} "
                    f"({var_label} case, {len(batch)} drugs)…"
                )
                try:
                    async with session.post(
                        self.DGIDB_API,
                        json={"query": DGIDB_QUERY, "variables": {"names": batch}},
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            logger.warning(
                                f"⚠️  DGIdb returned {resp.status}: {text[:200]}"
                            )
                            continue

                        result = await resp.json()

                        if "errors" in result:
                            errs = [e.get("message") for e in result["errors"]]
                            logger.warning(f"⚠️  DGIdb GraphQL errors: {errs}")
                            continue

                        dgidb_drugs = (
                            result.get("data", {}).get("drugs", {}).get("nodes", []) or []
                        )
                        dgidb_drugs = [d for d in dgidb_drugs if d]

                        logger.info(
                            f"   DGIdb returned {len(dgidb_drugs)} drug records "
                            f"(batch {batch_start//BATCH_SIZE + 1})"
                        )

                        for dgidb_drug in dgidb_drugs:
                            raw_name = dgidb_drug.get("name", "")
                            key = raw_name.lower()

                            interactions = dgidb_drug.get("interactions") or []
                            targets = [
                                i["gene"]["name"]
                                for i in interactions
                                if i.get("gene") and i["gene"].get("name")
                            ]
                            if targets and key not in drug_target_map:
                                drug_target_map[key] = targets

                except Exception as e:
                    logger.error(f"❌ DGIdb batch failed: {e}")

        logger.info(
            f"📊 DGIdb mapping built: {len(drug_target_map)} drugs have targets"
        )

        # Apply targets back to ChEMBL drugs
        enhanced = 0
        for drug in drugs:
            # Try several name variants
            candidates = {
                drug["name"].lower(),
                drug["name"].upper().lower(),
                drug["name"].title().lower(),
            }
            for key in candidates:
                if key in drug_target_map:
                    drug["targets"] = drug_target_map[key]
                    drug["pathways"] = self._infer_pathways_from_targets(
                        drug["targets"]
                    )
                    enhanced += 1
                    break

        logger.info(f"✅ Enhanced {enhanced} drugs with DGIdb gene targets")
        return drugs

    def _infer_pathways_from_targets(self, targets: List[str]) -> List[str]:
        pathways: Set[str] = set()
        for target in targets[:20]:
            pathways.update(self._map_genes_to_pathways([target]))
        return list(pathways)

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 Session closed")


# Backward-compat alias
DataFetcher = ProductionDataFetcher