"""
LLMExplainer: uses OpenAI API to generate explanations for drug repurposing candidates.
Free tier: $5 credit for new accounts
"""

import asyncio
from typing import Optional
import openai
from models import DrugCandidate


class LLMExplainer:
    """Generate AI-powered explanations for repurposing candidates."""

    def __init__(self):
        self.model = "gpt-3.5-turbo"  # Cheapest model, good quality

    async def explain_candidates(
        self,
        disease_name: str,
        candidates: list[DrugCandidate],
        api_key: Optional[str] = None
    ) -> list[DrugCandidate]:
        """
        Generate explanations for each candidate using OpenAI API.
        If no API key provided, uses fallback heuristic explanations.
        """
        if not api_key:
            # Fallback to rule-based explanations
            return self._generate_fallback_explanations(disease_name, candidates)
        
        try:
            # Set API key
            openai.api_key = api_key
            
            # Process in batches to avoid rate limits
            batch_size = 5
            explained_candidates = []
            
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i + batch_size]
                tasks = [
                    self._explain_single_candidate(disease_name, candidate)
                    for candidate in batch
                ]
                batch_results = await asyncio.gather(*tasks)
                explained_candidates.extend(batch_results)
            
            return explained_candidates
            
        except Exception as e:
            print(f"LLM explanation failed: {e}, falling back to heuristic explanations")
            return self._generate_fallback_explanations(disease_name, candidates)

    async def _explain_single_candidate(
        self,
        disease_name: str,
        candidate: DrugCandidate
    ) -> DrugCandidate:
        """Generate explanation for a single candidate."""
        
        prompt = f"""You are a drug repurposing expert. Generate a concise scientific explanation (2-3 sentences) for why {candidate.drug_name} might be repurposed for {disease_name}.

Current indication: {candidate.original_indication}
Mechanism: {candidate.mechanism}
Shared genes: {', '.join(candidate.shared_genes) if candidate.shared_genes else 'None'}
Shared pathways: {', '.join(candidate.shared_pathways) if candidate.shared_pathways else 'None'}
Confidence: {candidate.confidence}

Focus on the biological rationale based on shared molecular targets and pathways. Be specific and scientific."""

        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a drug repurposing expert."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            explanation = response.choices[0].message.content.strip()
            candidate.explanation = explanation
            
        except Exception as e:
            print(f"Failed to explain {candidate.drug_name}: {e}")
            candidate.explanation = self._generate_fallback_explanation(disease_name, candidate)
        
        return candidate

    def _generate_fallback_explanations(
        self,
        disease_name: str,
        candidates: list[DrugCandidate]
    ) -> list[DrugCandidate]:
        """Generate rule-based explanations when API is unavailable."""
        for candidate in candidates:
            candidate.explanation = self._generate_fallback_explanation(disease_name, candidate)
        return candidates

    def _generate_fallback_explanation(self, disease_name: str, candidate: DrugCandidate) -> str:
        """Generate a heuristic explanation based on available data."""
        
        parts = []
        
        if candidate.shared_genes:
            genes_str = ", ".join(candidate.shared_genes[:3])
            if len(candidate.shared_genes) > 3:
                genes_str += f" and {len(candidate.shared_genes) - 3} others"
            parts.append(f"{candidate.drug_name} targets {genes_str}, which are implicated in {disease_name}")
        
        if candidate.shared_pathways:
            pathways_str = ", ".join(candidate.shared_pathways[:2])
            if len(candidate.shared_pathways) > 2:
                pathways_str += f" and {len(candidate.shared_pathways) - 2} other pathways"
            parts.append(f"modulates {pathways_str}")
        
        if candidate.mechanism:
            parts.append(f"Its mechanism as a {candidate.mechanism.lower()} may address underlying pathological processes")
        
        if not parts:
            return f"{candidate.drug_name} shows potential based on computational analysis of molecular signatures associated with {disease_name}."
        
        explanation = ". ".join(parts) + "."
        return explanation