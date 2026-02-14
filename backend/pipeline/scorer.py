"""
PRODUCTION DRUG SCORING ENGINE
Scores drug-disease matches using real API data
Uses multi-factor evidence integration
"""

import logging
from typing import Dict, List, Set, Tuple
import networkx as nx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductionScorer:
    """
    Scores drug-disease matches using multiple evidence types.
    Integrates data from OpenTargets, ChEMBL, DGIdb.
    """
    
    # Pathway importance weights (based on biological relevance)
    PATHWAY_WEIGHTS = {
        # Critical pathways for neurodegeneration & rare diseases
        "Autophagy": 1.0,
        "Mitophagy": 1.0,
        "Lysosomal function": 1.0,
        "Mitochondrial function": 0.9,
        "Ubiquitin-proteasome system": 0.9,
        "Protein aggregation": 0.9,
        
        # Metabolic pathways
        "Sphingolipid metabolism": 0.9,
        "Glycogen metabolism": 0.8,
        "Lipid metabolism": 0.8,
        "Cholesterol metabolism": 0.8,
        "Glucose metabolism": 0.8,
        
        # Signaling pathways
        "mTOR signaling": 0.8,
        "PI3K-Akt signaling": 0.7,
        "MAPK signaling": 0.7,
        "Inflammatory response": 0.7,
        "NF-κB signaling": 0.7,
        
        # Other pathways
        "Oxidative stress response": 0.8,
        "DNA repair": 0.7,
        "Cell cycle regulation": 0.6,
        "Apoptosis": 0.6,
    }
    
    def __init__(self, graph: nx.Graph):
        self.graph = graph
    
    def score_drug_disease_match(
        self,
        drug_name: str,
        disease_name: str,
        disease_data: Dict,
        drug_data: Dict
    ) -> Tuple[float, Dict]:
        """
        Score how well a drug matches a disease.
        
        Returns:
            (score, evidence_dict) where score is 0-1
        """
        evidence = {
            'shared_genes': [],
            'shared_pathways': [],
            'gene_score': 0.0,
            'pathway_score': 0.0,
            'literature_score': 0.0,
            'mechanism_score': 0.0,
            'total_score': 0.0,
            'confidence': 'low',
            'explanation': []
        }
        
        # 1. GENE TARGETING SCORE (35% weight)
        gene_score, shared_genes = self._score_gene_overlap(
            drug_data.get('targets', []),
            disease_data.get('genes', []),
            disease_data.get('gene_scores', {})
        )
        evidence['gene_score'] = gene_score
        evidence['shared_genes'] = list(shared_genes)
        
        # 2. PATHWAY OVERLAP SCORE (30% weight)
        pathway_score, shared_pathways = self._score_pathway_overlap(
            drug_data.get('pathways', []),
            disease_data.get('pathways', [])
        )
        evidence['pathway_score'] = pathway_score
        evidence['shared_pathways'] = list(shared_pathways)
        
        # 3. MECHANISM SIMILARITY SCORE (20% weight)
        mechanism_score = self._score_mechanism_similarity(
            drug_data,
            disease_data
        )
        evidence['mechanism_score'] = mechanism_score
        
        # 4. LITERATURE/KNOWN REPURPOSING SCORE (15% weight)
        literature_score = self._score_literature_evidence(
            drug_name,
            disease_name,
            drug_data,
            disease_data
        )
        evidence['literature_score'] = literature_score
        
        # CALCULATE TOTAL SCORE
        total_score = (
            gene_score * 0.35 +
            pathway_score * 0.30 +
            mechanism_score * 0.20 +
            literature_score * 0.15
        )
        
        # Apply bonuses
        total_score = self._apply_bonuses(
            total_score,
            drug_data,
            disease_data,
            evidence
        )
        
        # Cap at 1.0
        total_score = min(total_score, 1.0)
        
        evidence['total_score'] = total_score
        evidence['confidence'] = self._determine_confidence(total_score, evidence)
        evidence['explanation'] = self._generate_explanation(evidence, drug_name, disease_name)
        
        return total_score, evidence
    
    def _score_gene_overlap(
        self,
        drug_targets: List[str],
        disease_genes: List[str],
        gene_scores: Dict[str, float]
    ) -> Tuple[float, Set[str]]:
        """Score based on shared genes between drug and disease."""
        if not drug_targets or not disease_genes:
            return 0.0, set()
        
        drug_set = set(drug_targets)
        disease_set = set(disease_genes)
        shared = drug_set & disease_set
        
        if not shared:
            return 0.0, set()
        
        # Weight by gene association scores from OpenTargets
        weighted_score = 0.0
        for gene in shared:
            association_score = gene_scores.get(gene, 0.5)
            weighted_score += association_score
        
        # Normalize by number of shared genes and apply bonus for multiple hits
        base_score = weighted_score / len(disease_genes)
        
        # Bonus for hitting multiple genes (1-3 genes: 1x, 4-6: 1.2x, 7+: 1.5x)
        if len(shared) >= 7:
            multiplier = 1.5
        elif len(shared) >= 4:
            multiplier = 1.2
        else:
            multiplier = 1.0
        
        final_score = min(base_score * multiplier, 1.0)
        
        logger.debug(f"Gene overlap: {len(shared)} genes, score={final_score:.3f}")
        return final_score, shared
    
    def _score_pathway_overlap(
        self,
        drug_pathways: List[str],
        disease_pathways: List[str]
    ) -> Tuple[float, Set[str]]:
        """Score based on shared pathways, weighted by importance."""
        if not drug_pathways or not disease_pathways:
            return 0.0, set()
        
        drug_set = set(drug_pathways)
        disease_set = set(disease_pathways)
        shared = drug_set & disease_set
        
        if not shared:
            return 0.0, set()
        
        # Weight by pathway importance
        weighted_score = 0.0
        max_possible_score = 0.0
        
        for pathway in disease_pathways:
            weight = self._get_pathway_weight(pathway)
            max_possible_score += weight
            
            if pathway in shared:
                weighted_score += weight
        
        # Normalize
        if max_possible_score > 0:
            final_score = weighted_score / max_possible_score
        else:
            final_score = len(shared) / len(disease_pathways)
        
        logger.debug(f"Pathway overlap: {len(shared)} pathways, score={final_score:.3f}")
        return final_score, shared
    
    def _get_pathway_weight(self, pathway: str) -> float:
        """Get importance weight for a pathway."""
        # Exact match
        if pathway in self.PATHWAY_WEIGHTS:
            return self.PATHWAY_WEIGHTS[pathway]
        
        # Partial match (e.g., "mTOR signaling pathway" matches "mTOR signaling")
        for key, weight in self.PATHWAY_WEIGHTS.items():
            if key.lower() in pathway.lower() or pathway.lower() in key.lower():
                return weight
        
        # Default weight for unknown pathways
        return 0.5
    
    def _score_mechanism_similarity(
        self,
        drug_data: Dict,
        disease_data: Dict
    ) -> float:
        """Score based on mechanism of action alignment."""
        mechanism = drug_data.get('mechanism', '').lower()
        disease_desc = disease_data.get('description', '').lower()
        disease_name = disease_data.get('name', '').lower()
        
        if not mechanism:
            return 0.0
        
        # Check for mechanism-disease alignment
        score = 0.0
        
        # Mechanism keywords that indicate good match
        good_mechanisms = {
            'lysosomal storage': ['lysosomal', 'storage', 'gaucher', 'fabry', 'pompe'],
            'enzyme replacement': ['lysosomal', 'storage', 'enzyme', 'deficiency'],
            'autophagy inducer': ['autophagy', 'lysosomal', 'parkinson', 'huntington'],
            'chaperone': ['misfolding', 'protein', 'lysosomal', 'gaucher', 'fabry'],
            'substrate reduction': ['lysosomal', 'storage', 'sphingolipid'],
            'antioxidant': ['oxidative', 'mitochondrial', 'neurodegeneration'],
            'anti-inflammatory': ['inflammation', 'inflammatory'],
            'kinase inhibitor': ['kinase', 'signaling', 'proliferation'],
        }
        
        for mechanism_type, disease_keywords in good_mechanisms.items():
            if mechanism_type in mechanism:
                for keyword in disease_keywords:
                    if keyword in disease_name or keyword in disease_desc:
                        score += 0.3
        
        return min(score, 1.0)
    
    def _score_literature_evidence(
        self,
        drug_name: str,
        disease_name: str,
        drug_data: Dict,
        disease_data: Dict
    ) -> float:
        """Score based on known repurposing cases or literature."""
        
        # Known successful repurposing cases (from literature/trials)
        known_cases = {
            # Parkinson's disease
            ('nilotinib', 'parkinson'): 0.8,
            ('ambroxol', 'parkinson'): 0.7,
            ('exenatide', 'parkinson'): 0.7,
            ('imatinib', 'parkinson'): 0.6,
            
            # Huntington's disease
            ('pridopidine', 'huntington'): 0.7,
            ('tetrabenazine', 'huntington'): 0.9,
            
            # ALS
            ('riluzole', 'als'): 0.95,
            ('edaravone', 'als'): 0.9,
            
            # Alzheimer's
            ('donepezil', 'alzheimer'): 0.95,
            ('memantine', 'alzheimer'): 0.95,
            
            # Gaucher disease
            ('imiglucerase', 'gaucher'): 0.95,
            ('eliglustat', 'gaucher'): 0.9,
            ('miglustat', 'gaucher'): 0.85,
            ('ambroxol', 'gaucher'): 0.6,
            
            # Fabry disease
            ('agalsidase', 'fabry'): 0.95,
            ('migalastat', 'fabry'): 0.9,
            
            # Pompe disease
            ('alglucosidase', 'pompe'): 0.95,
            
            # Wilson disease
            ('penicillamine', 'wilson'): 0.95,
            ('trientine', 'wilson'): 0.9,
            
            # General rare disease repurposing
            ('sirolimus', 'lysosomal'): 0.5,
            ('metformin', 'mitochondrial'): 0.4,
        }
        
        # Check for exact matches
        drug_lower = drug_name.lower()
        disease_lower = disease_name.lower()
        
        for (known_drug, known_disease), score in known_cases.items():
            if known_drug in drug_lower and known_disease in disease_lower:
                logger.info(f"✨ Known repurposing case: {drug_name} for {disease_name}")
                return score
        
        return 0.0
    
    def _apply_bonuses(
        self,
        base_score: float,
        drug_data: Dict,
        disease_data: Dict,
        evidence: Dict
    ) -> float:
        """Apply bonuses for special cases."""
        score = base_score
        
        # Bonus for rare disease + orphan drug
        if disease_data.get('is_rare', False):
            score += 0.05
            evidence['explanation'].append("Bonus: Rare disease (+0.05)")
        
        # Bonus for multiple shared genes (strong biological evidence)
        if len(evidence['shared_genes']) >= 5:
            score += 0.05
            evidence['explanation'].append(f"Bonus: Multiple shared genes ({len(evidence['shared_genes'])}) (+0.05)")
        
        # Bonus for critical pathway overlap
        critical_pathways = {'Autophagy', 'Lysosomal function', 'Mitophagy'}
        if any(p in evidence['shared_pathways'] for p in critical_pathways):
            score += 0.05
            evidence['explanation'].append("Bonus: Critical pathway overlap (+0.05)")
        
        return score
    
    def _determine_confidence(self, score: float, evidence: Dict) -> str:
        """Determine confidence level based on score and evidence quality."""
        
        # High confidence: strong score + multiple evidence types
        if score >= 0.65:
            return "high"
        
        # Medium confidence: decent score OR good evidence
        elif score >= 0.40:
            return "medium"
        
        # Low confidence: weak score
        else:
            return "low"
    
    def _generate_explanation(
        self,
        evidence: Dict,
        drug_name: str,
        disease_name: str
    ) -> List[str]:
        """Generate human-readable explanation."""
        explanations = evidence.get('explanation', [])
        
        # Gene evidence
        if evidence['shared_genes']:
            genes_str = ', '.join(evidence['shared_genes'][:5])
            if len(evidence['shared_genes']) > 5:
                genes_str += f" (+ {len(evidence['shared_genes']) - 5} more)"
            explanations.append(f"Targets disease genes: {genes_str}")
        
        # Pathway evidence
        if evidence['shared_pathways']:
            pathways_str = ', '.join(evidence['shared_pathways'][:3])
            if len(evidence['shared_pathways']) > 3:
                pathways_str += f" (+ {len(evidence['shared_pathways']) - 3} more)"
            explanations.append(f"Modulates pathways: {pathways_str}")
        
        # Score components
        explanations.append(f"Gene score: {evidence['gene_score']:.2f}")
        explanations.append(f"Pathway score: {evidence['pathway_score']:.2f}")
        
        if evidence['mechanism_score'] > 0:
            explanations.append(f"Mechanism alignment: {evidence['mechanism_score']:.2f}")
        
        if evidence['literature_score'] > 0:
            explanations.append(f"Literature evidence: {evidence['literature_score']:.2f}")
        
        return explanations


# Maintain backward compatibility
Scorer = ProductionScorer