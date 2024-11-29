# backend/agents/query_kb_mapper_agent.py

from dataclasses import dataclass
from typing import List
from dsrag.llm import LLM
from backend.kb_management.manager import KnowledgeBaseManager
import json
from dsrag.llm import AnthropicChatAPI

@dataclass
class KBMappingResult:
    """Résultat du mapping entre une requête et une base de connaissances"""
    kb_id: str
    reasoning: str

class QueryKBMapper:
    """
    Agent responsable de mapper les questions utilisateur aux bases de connaissances pertinentes.
    Version simplifiée retournant maximum 2 bases, avec priorité à la base de normes en second choix.
    """
    
    def __init__(self, kb_manager: KnowledgeBaseManager, llm_service: LLM):
        self.kb_manager = kb_manager
        self.llm = AnthropicChatAPI(model="claude-3-sonnet-20240229") #llm_service

    def _build_prompt(self, query: str, available_kbs: List[dict]) -> str:
        """Construit un prompt simple pour sélectionner les bases pertinentes"""
        kb_descriptions = "\n".join([
            f"\n\n###############################################\nBase {kb['id']}:\n- kb_id: {kb['id']}\n- Titre: {kb['title']}\n- Description: {kb['description']}\n###############################################\n\n"
            for i, kb in enumerate(available_kbs)
        ])
        print(kb_descriptions)
        print("end description")
        return f"""En tant qu'expert documentaire, sélectionne la ou les bases de connaissances les plus pertinentes pour répondre à cette question.

Question de l'utilisateur:
{query}

Bases de connaissances disponibles:
{kb_descriptions}

INSTRUCTIONS:
1. Analyse la question et les "kb_id", "Description" et "Titre" des bases
2. Si le nom de la base de connaissance est spécifiquement cité dans la question ne pas inclure d'autre base, à part normes si c'est pertinent.
3. Sélectionne maximum 2 bases qui contiennent les informations les plus pertinentes en lien avec la qestion de l'utilisateur
4. Si deux bases sont nécessaires et qu'une base "normes" existe, privilégie-la en second choix si elle a un minimum de pertinence avec la question

Réponds au format JSON:
{{
    "selected_kbs": [
        {{
            "kb_id": "kb_id",
            "reason": "brève explication de la pertinence"
        }}
    ]
}}

Note: Ne sélectionne une deuxième base que si elle est vraiment pertinente pour la question."""

    def _process_llm_response(self, response: str) -> List[KBMappingResult]:
        """Traite la réponse du LLM et construit la liste des bases sélectionnées"""
        try:
            data = json.loads(response)
            selected = data.get("selected_kbs", [])
            
            # Convertir en KBMappingResult
            results = []
            for selection in selected[:2]:  # Limitation à 2 bases maximum
                if "kb_id" in selection and "reason" in selection:
                    results.append(KBMappingResult(
                        kb_id=selection["kb_id"],
                        reasoning=selection["reason"]
                    ))
                    
            return results
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Erreur de traitement de la réponse LLM: {str(e)}")
            return []

    async def map_query_to_kbs(self, query: str) -> List[KBMappingResult]:
        try:
            available_kbs = self.kb_manager.list_knowledge_bases()
            if not available_kbs:
                return []
            
            prompt = self._build_prompt(query, available_kbs)
            response = self.llm.make_llm_call([{
                "role": "user", 
                "content": prompt
            }])
            
            mapping_results = self._process_llm_response(response)
            
            # Correction ici : retourner un KBMappingResult par défaut si aucun résultat
            if not mapping_results:
                # Chercher si une base "normes" existe
                normes_kb = next((kb for kb in available_kbs if "normes" in kb["id"].lower()), None)
                if normes_kb:
                    return [KBMappingResult(
                        kb_id=normes_kb["id"],
                        reasoning="Base de normes sélectionnée par défaut"
                    )]
            return mapping_results
                
        except Exception as e:
            print(f"Erreur lors du mapping: {str(e)}")
            return []