# backend/agents/no_result_handler_agent.py
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re
from dsrag.llm import LLM

@dataclass
class SearchFailureAnalysis:
    """Structure de données pour l'analyse d'un échec de recherche"""
    failure_type: str  # "no_kb", "no_results", "low_relevance"
    possible_causes: List[str]
    suggested_actions: List[str]
    reformulated_queries: Optional[List[str]] = None

class NoResultsHandler:
    """
    Agent spécialisé dans l'analyse et la gestion des échecs de recherche
    """
    
    def __init__(self, llm_service: LLM):
        self.llm = llm_service
        
    async def analyze_failed_search(
        self,
        original_query: str,
        available_kbs: List[dict],
        search_contexts: List[Any] = None
    ) -> SearchFailureAnalysis:
        """
        Analyse une recherche ayant échoué et propose des solutions
        """
        # Déterminer le type d'échec
        if not available_kbs:
            return self._handle_no_kb_case()
        elif not search_contexts:
            return await self._handle_no_results_case(original_query, available_kbs)
        else:
            return await self._handle_low_relevance_case(original_query, search_contexts)
            
    def _handle_no_kb_case(self) -> SearchFailureAnalysis:
        """Gestion du cas où aucune base n'est disponible"""
        return SearchFailureAnalysis(
            failure_type="no_kb",
            possible_causes=[
                "Aucune base de connaissances n'a été créée",
                "Les bases existantes sont peut-être inaccessibles"
            ],
            suggested_actions=[
                "Créer une nouvelle base de connaissances",
                "Vérifier les permissions d'accès aux bases",
                "Contacter l'administrateur du système"
            ]
        )
            
    async def _handle_no_results_case(
        self, 
        query: str,
        available_kbs: List[dict]
    ) -> SearchFailureAnalysis:
        """
        Gestion du cas où la recherche ne donne aucun résultat
        """
        # Analyser la requête et suggérer des reformulations
        analysis_prompt = f"""
        Analyze this search query and suggest improvements. The query returned no results.
        
        Query: {query}
        
        Available knowledge bases and their content:
        {self._format_kb_info(available_kbs)}
        
        Return a JSON with this structure:
        {{
            "possible_causes": ["list of potential reasons for no results"],
            "suggested_actions": ["list of actions the user could take"],
            "reformulations": ["3-4 alternative ways to formulate the query"]
        }}
        """
        
        response = self.llm.make_llm_call([{"role": "user", "content": analysis_prompt}])
        try:
            import json
            analysis = json.loads(response)
            
            return SearchFailureAnalysis(
                failure_type="no_results",
                possible_causes=analysis["possible_causes"],
                suggested_actions=analysis["suggested_actions"],
                reformulated_queries=analysis["reformulations"]
            )
        except:
            # Fallback si l'analyse échoue
            return self._get_default_no_results_analysis(query)
            
    async def _handle_low_relevance_case(
        self, 
        query: str,
        search_contexts: List[Any]
    ) -> SearchFailureAnalysis:
        """
        Gestion du cas où les résultats ont une faible pertinence
        """
        # Calculer la moyenne des scores de pertinence
        all_scores = []
        for context in search_contexts:
            for result in context.results:
                all_scores.append(result.relevance_score)
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        return SearchFailureAnalysis(
            failure_type="low_relevance",
            possible_causes=[
                f"Score moyen de pertinence faible ({avg_score:.2f})",
                "Les termes de recherche sont peut-être trop généraux",
                "La requête contient peut-être des termes ambigus"
            ],
            suggested_actions=[
                "Essayer une recherche plus spécifique",
                "Utiliser des termes techniques précis",
                "Ajouter des filtres de recherche",
            ],
            reformulated_queries=await self._generate_specific_queries(query)
        )
    
    def _get_default_no_results_analysis(self, query: str) -> SearchFailureAnalysis:
        """Analyse par défaut quand l'analyse LLM échoue"""
        return SearchFailureAnalysis(
            failure_type="no_results",
            possible_causes=[
                "Les termes de recherche sont peut-être trop spécifiques",
                "Le contenu recherché n'est peut-être pas présent dans les bases"
            ],
            suggested_actions=[
                "Essayer des termes plus généraux",
                "Vérifier l'orthographe des mots-clés",
                "Utiliser des synonymes"
            ],
            reformulated_queries=[
                self._simplify_query(query),
                self._remove_specific_terms(query)
            ]
        )
    
    def _format_kb_info(self, kbs: List[dict]) -> str:
        """Formate l'information des bases pour le prompt"""
        return "\n".join([
            f"- {kb['title']}: {kb['description']}"
            for kb in kbs
        ])
    
    async def _generate_specific_queries(self, query: str) -> List[str]:
        """Génère des variantes plus spécifiques de la requête"""
        prompt = f"""
        Generate 3 more specific versions of this search query:
        {query}
        
        Return only the queries, one per line.
        """
        response = self.llm.make_llm_call([{"role": "user", "content": prompt}])
        return [q.strip() for q in response.split('\n') if q.strip()]
    
    def _simplify_query(self, query: str) -> str:
        """Simplifie une requête en retirant les termes complexes"""
        # Retirer les modificateurs complexes
        simplified = re.sub(r'(exactement|précisément|spécifiquement)', '', query)
        # Garder les 3-4 premiers mots significatifs
        words = simplified.split()
        return ' '.join(words[:4]).strip()
    
    def _remove_specific_terms(self, query: str) -> str:
        """Retire les termes très spécifiques d'une requête"""
        # Retirer les nombres, dates, codes, etc.
        return re.sub(r'\b\d+\b|\b[A-Z0-9-]+\b', '', query).strip()