# backend/agents/query_kb_mapper_agent.py
from typing import List, Dict, Any
from dataclasses import dataclass
import json
from backend.kb_management.manager import KnowledgeBaseManager
from dsrag.llm import LLM

@dataclass
class KBMappingResult:
    kb_id: str
    relevance_score: float
    reasoning: str

class QueryKBMapper:
    """
    Agent responsable de mapper les questions utilisateur aux bases de connaissances pertinentes.
    Utilise une analyse sémantique pour déterminer la pertinence des bases.
    """
    
    def __init__(self, kb_manager: KnowledgeBaseManager, llm_service: LLM):
        self.kb_manager = kb_manager
        self.llm = llm_service
    
    def _build_mapping_prompt(self, query: str, available_kbs: List[Dict[str, Any]]) -> str:
        """
        Construit un prompt détaillé pour l'analyse de pertinence.
        
        Le prompt guide le LLM pour:
        1. Analyser les mots-clés et le contexte de la question
        2. Évaluer la pertinence thématique avec chaque base
        3. Fournir un raisonnement explicite
        """
        kb_descriptions = "\n".join([
            f"- Base '{kb['id']}' - {kb['title']}: {kb['description']}"
            for kb in available_kbs
        ])
        
        return f"""En tant qu'expert en analyse de documents, évalue la pertinence sémantique de la question pour chaque base de connaissances disponible.

Pour chaque base, analyse:
1. La correspondance thématique entre la question et la description de la base
2. Les mots-clés et concepts partagés
3. Le contexte implicite de la question

Question de l'utilisateur: "{query}"

Bases de connaissances disponibles:
{kb_descriptions}

Réponds au format JSON avec cette structure:
{{
    "analysis": {{
        "question_keywords": ["liste", "des", "mots-clés", "extraits"],
        "context": "brève analyse du contexte de la question"
    }},
    "mappings": [
        {{
            "kb_id": "identifiant_base",
            "relevance_score": 0.95,
            "reasoning": "explication détaillée du lien entre la question et la base"
        }}
    ]
}}

Notes:
- N'inclure que les bases avec un score de pertinence > 0.6
- Les scores doivent refléter précisément le niveau de correspondance thématique
- Le raisonnement doit expliquer clairement pourquoi la base est pertinente ou non
"""

    def _evaluate_kb_relevance(self, mapping_response: Dict) -> List[KBMappingResult]:
        """
        Traite la réponse du LLM et applique des règles de filtrage supplémentaires.
        """
        try:
            mappings = mapping_response.get("mappings", [])
            
            # Post-traitement et validation des scores
            results = []
            for mapping in mappings:
                # Normalisation des scores
                score = float(mapping["relevance_score"])
                score = max(0.0, min(1.0, score))  # Borner entre 0 et 1
                
                # Ajustement basé sur la qualité du raisonnement
                reasoning = mapping["reasoning"]
                if len(reasoning) < 20:  # Raisonnement trop court
                    score *= 0.8
                    
                results.append(KBMappingResult(
                    kb_id=mapping["kb_id"],
                    relevance_score=score,
                    reasoning=reasoning
                ))
            
            # Tri par score décroissant
            return sorted(results, key=lambda x: x.relevance_score, reverse=True)
            
        except (KeyError, ValueError) as e:
            print(f"Erreur dans l'analyse des mappings: {str(e)}")
            return []

    async def map_query_to_kbs(
        self, 
        query: str, 
        min_relevance: float = 0.3
    ) -> List[KBMappingResult]:
        """
        Mappe une question aux bases de connaissances pertinentes avec une analyse sémantique améliorée.
        
        Args:
            query: Question de l'utilisateur
            min_relevance: Seuil minimal de pertinence (défaut: 0.3)
            
        Returns:
            Liste triée des bases pertinentes avec leurs scores et raisonnements
        """
        try:
            # Récupération des bases disponibles
            available_kbs = self.kb_manager.list_knowledge_bases()
            if not available_kbs:
                return []
            
            # Construction et envoi du prompt
            prompt = self._build_mapping_prompt(query, available_kbs)
            response = self.llm.make_llm_call([{
                "role": "user", 
                "content": prompt
            }])
            
            # Analyse de la réponse JSON
            try:
                response_data = json.loads(response)
                mappings = self._evaluate_kb_relevance(response_data)
                
                # Filtrage par seuil de pertinence
                relevant_mappings = [
                    mapping for mapping in mappings 
                    if mapping.relevance_score >= min_relevance
                ]
                
                return relevant_mappings
                
            except json.JSONDecodeError:
                print("Erreur de décodage de la réponse JSON")
                # Fallback : retourner toutes les bases avec un score par défaut
                return [
                    KBMappingResult(
                        kb_id=kb["id"],
                        relevance_score=0.5,
                        reasoning="Analyse automatique indisponible - score par défaut"
                    )
                    for kb in available_kbs
                ]
        
        except Exception as e:
            print(f"Erreur lors du mapping: {str(e)}")
            return []