# backend/agents/query_kb_mapper_agent.py
from typing import List, Dict, Any
from dataclasses import dataclass
import json
from backend.kb_management.manager import KnowledgeBaseManager

@dataclass
class KBMappingResult:
    kb_id: str
    relevance_score: float
    reasoning: str

class QueryKBMapper:
    """
    Agent responsable de mapper les questions utilisateur aux bases de connaissances pertinentes.
    """
    
    def __init__(self, kb_manager: KnowledgeBaseManager, llm_service: Any):
        self.kb_manager = kb_manager
        self.llm = llm_service
    
    def _build_mapping_prompt(self, query: str, available_kbs: List[Dict[str, Any]]) -> str:
        kb_descriptions = "\n".join([
            f"Base '{kb['id']}': {kb['title']} - {kb['description']}"
            for kb in available_kbs
        ])
        
        return f"""En tant qu'expert en analyse de requêtes, évalue la pertinence de la question suivante pour chacune des bases de connaissances disponibles.
        Elimine les bases de connaissance dont la description ne correspond pas aux éléments de la question.
        Retourne une liste au format JSON avec la structure suivante pour chaque base pertinente (score > 0.6):
        {{"mappings": [
            {{"kb_id": "id_de_la_base",
            "relevance_score": 0.8,
            "reasoning": "explication"}}
        ]}}

        Question: {query}

        Bases disponibles:
        {kb_descriptions}
        """
    
    async def map_query_to_kbs(self, query: str, min_relevance: float = 0.6) -> List[KBMappingResult]:
        """Mappe une question aux bases de connaissances pertinentes"""
        available_kbs = self.kb_manager.list_knowledge_bases()
        prompt = self._build_mapping_prompt(query, available_kbs)
        
        response = self.llm.make_llm_call([{"role": "user", "content": prompt}])
        try:
            # Extraire le JSON de la réponse
            response_json = json.loads(response)
            mappings = response_json.get("mappings", [])
            
            relevant_kbs = [
                KBMappingResult(
                    kb_id=mapping["kb_id"],
                    relevance_score=mapping["relevance_score"],
                    reasoning=mapping["reasoning"]
                )
                for mapping in mappings
                if mapping["relevance_score"] >= min_relevance
            ]
            
            return sorted(relevant_kbs, key=lambda x: x.relevance_score, reverse=True)
            
        except (json.JSONDecodeError, KeyError):
            # Fallback si le parsing JSON échoue - retourner toutes les bases
            return [
                KBMappingResult(
                    kb_id=kb["id"],
                    relevance_score=1.0,
                    reasoning="Fallback: analyse automatique indisponible"
                )
                for kb in available_kbs
            ]    
    # async def map_query_to_kbs(self, query: str, min_relevance: float = 0.6) -> List[KBMappingResult]:
    #     available_kbs = self.kb_manager.list_knowledge_bases()
    #     prompt = self._build_mapping_prompt(query, available_kbs)
        
    #     analysis = await self.llm.generate_structured_output(prompt, {
    #         "mappings": [
    #             {
    #                 "kb_id": "str",
    #                 "relevance_score": "float",
    #                 "reasoning": "str"
    #             }
    #         ]
    #     })
        
    #     relevant_kbs = [
    #         KBMappingResult(
    #             kb_id=mapping["kb_id"],
    #             relevance_score=mapping["relevance_score"],
    #             reasoning=mapping["reasoning"]
    #         )
    #         for mapping in analysis["mappings"]
    #         if mapping["relevance_score"] >= min_relevance
    #     ]
        
    #     return sorted(relevant_kbs, key=lambda x: x.relevance_score, reverse=True)
    
    # def _build_mapping_prompt(self, query: str, available_kbs: List[dict]) -> str:
    #     kb_descriptions = "\n".join([
    #         f"Base '{kb['id']}': {kb['title']} - {kb['description']}"
    #         for kb in available_kbs
    #     ])
        
    #     return f"""
    #     En tant qu'expert en analyse de requêtes, évalue la pertinence de la question suivante 
    #     pour chacune des bases de connaissances disponibles.

    #     Question: {query}

    #     Bases de connaissances disponibles:
    #     {kb_descriptions}

    #     Pour chaque base, évalue sa pertinence et explique ton raisonnement.
    #     Retourne uniquement les bases pertinentes (score > 0.6).
    #     """