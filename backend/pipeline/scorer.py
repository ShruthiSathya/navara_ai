import networkx as nx
from pipeline.data_fetcher import DRUG_DATABASE
from pipeline.graph_builder import KnowledgeGraphBuilder
from models import DrugCandidate

KNOWN_REPURPOSING = {
    ("DB00331", "diabetes"): 1.0, ("DB00331", "cancer"): 0.7, ("DB00331", "aging"): 0.6,
    ("DB00877", "cancer"): 0.8,   ("DB00877", "aging"): 0.7,
    ("DB00203", "hypertension"): 0.9,
    ("DB00945", "cardiovascular"): 0.9, ("DB00945", "cancer"): 0.5,
    ("DB00313", "epilepsy"): 0.9, ("DB00313", "cancer"): 0.6,
    ("DB01041", "myeloma"): 1.0,  ("DB01041", "cancer"): 0.7,
    ("DB01234", "covid"): 0.8,    ("DB01234", "inflammation"): 0.9,
    ("DB00619", "leukemia"): 1.0, ("DB00619", "cancer"): 0.7,
    ("DB01356", "alzheimer"): 0.5,("DB01356", "parkinson"): 0.4,
    ("DB01394", "gout"): 1.0,     ("DB01394", "cardiovascular"): 0.7,
    ("DB06273", "arthritis"): 0.9,("DB06273", "cytokine"): 0.8,
    ("DB00482", "cancer"): 0.6,
    ("DB01076", "cardiovascular"): 0.95, ("DB01076", "cancer"): 0.4,
}

WEIGHTS = {"gene_target": 0.35, "pathway_overlap": 0.35, "graph_centrality": 0.15, "literature": 0.15}


class RepurposingScorer:

    def __init__(self):
        self.graph_builder = KnowledgeGraphBuilder()

    def score_candidates(self, disease_data: dict, graph: nx.MultiDiGraph, top_k: int = 10, min_score: float = 0.3) -> list:
        disease_genes = set(disease_data.get("genes", []))
        disease_pathways = set(disease_data.get("pathways", []))
        disease_name = disease_data["name"].lower()
        candidates = []

        for drug_key, drug in DRUG_DATABASE.items():
            drug_id = drug["id"]
            drug_genes = set(drug.get("targets", []))
            drug_pathways = set(drug.get("pathways", []))

            shared_genes = disease_genes & drug_genes
            gene_target_score = min(len(shared_genes) / max(len(disease_genes), 1) * 3.0, 1.0)

            union_pathways = disease_pathways | drug_pathways
            if union_pathways:
                shared_pathways = disease_pathways & drug_pathways
                pathway_overlap_score = len(shared_pathways) / len(union_pathways)
                if len(shared_pathways) >= 1: pathway_overlap_score = max(pathway_overlap_score, 0.15)
                if len(shared_pathways) >= 2: pathway_overlap_score = max(pathway_overlap_score, 0.30)
            else:
                shared_pathways = set()
                pathway_overlap_score = 0.0

            graph_centrality_score = self._compute_graph_score(graph, disease_data["name"], drug_id)
            literature_score = self._compute_literature_score(drug_id, disease_name)

            composite_score = (
                WEIGHTS["gene_target"] * gene_target_score +
                WEIGHTS["pathway_overlap"] * pathway_overlap_score +
                WEIGHTS["graph_centrality"] * graph_centrality_score +
                WEIGHTS["literature"] * literature_score
            )

            if composite_score < min_score and not shared_genes and not shared_pathways:
                continue

            confidence = "High" if composite_score >= 0.65 else "Medium" if composite_score >= 0.40 else "Low"

            candidates.append(DrugCandidate(
                drug_name=drug["name"],
                drug_id=drug_id,
                original_indication=drug["indication"],
                composite_score=round(composite_score, 4),
                pathway_overlap_score=round(pathway_overlap_score, 4),
                gene_target_score=round(gene_target_score, 4),
                literature_score=round(literature_score, 4),
                shared_genes=sorted(shared_genes),
                shared_pathways=sorted(shared_pathways),
                mechanism=drug["mechanism"],
                explanation="",
                confidence=confidence
            ))

        candidates.sort(key=lambda x: x.composite_score, reverse=True)
        candidates = [c for c in candidates if c.composite_score >= min_score]
        return candidates[:top_k]

    def _compute_graph_score(self, G: nx.MultiDiGraph, disease_name: str, drug_id: str) -> float:
        try:
            UG = G.to_undirected()
            if not UG.has_node(disease_name) or not UG.has_node(drug_id):
                return 0.0
            length = nx.shortest_path_length(UG, disease_name, drug_id)
            return round(max(0.0, 1.0 - (length - 2) * 0.25), 4)
        except:
            return 0.0

    def _compute_literature_score(self, drug_id: str, disease_name: str) -> float:
        best_score = 0.0
        for (did, disease_pattern), score in KNOWN_REPURPOSING.items():
            if did == drug_id and disease_pattern in disease_name:
                best_score = max(best_score, score)
        return best_score