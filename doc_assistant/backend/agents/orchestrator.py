from typing import List, Optional
from .chat_agent import Message
from .query_kb_mapper_agent import QueryKBMapper
from .search_agent import SearchAgent, SearchContext
from .no_result_handler_agent import NoResultsHandler, SearchFailureAnalysis
from backend.kb_management.manager import KnowledgeBaseManager
from backend.utils.filter_utils import SearchFilter
import streamlit as st
from typing import Any

class AgentOrchestrator:
    def __init__(
        self,
        kb_manager: KnowledgeBaseManager,
        query_mapper: QueryKBMapper,
        search_agent: SearchAgent,
        llm_service: Any
    ):
        self.kb_manager = kb_manager
        self.query_mapper = query_mapper
        self.search_agent = search_agent
        self.llm = llm_service
        self.no_results_handler = NoResultsHandler(llm_service)
        self.conversation_history: List[Message] = []

    async def process_message(self, message: str, search_filter: Optional[SearchFilter] = None) -> Message:
        """
        Traite un message utilisateur avec gestion améliorée des échecs de recherche
        """
        st.info("📨 Traitement du nouveau message")
        self.conversation_history.append(Message(role="user", content=message))

        # Obtenir la liste des bases disponibles
        available_kbs = self.kb_manager.list_knowledge_bases()

        # Si des filtres sont actifs, utiliser la recherche filtrée
        if search_filter and search_filter.has_filters():
            kb_ids = search_filter.get_kb_ids()
            st.info(f"🔎 Recherche filtrée sur {len(kb_ids)} bases: {kb_ids}")
            search_contexts = await self._filtered_search(message, search_filter)
            
            if not search_contexts:
                st.warning("❌ Aucun résultat pour la recherche filtrée")
                analysis = await self.no_results_handler.analyze_failed_search(
                    message, 
                    [], 
                    available_kbs
                )
                return self._create_failure_analysis_message(analysis)
                
        else:
            # Mapping automatique des bases pertinentes
            #st.info("🤖 Mapping automatique des bases pertinentes")
            kb_mappings = await self.query_mapper.map_query_to_kbs(message)
            
            if not kb_mappings:
                st.warning("❌ Aucune base pertinente trouvée")
                analysis = await self.no_results_handler.analyze_failed_search(
                    message, 
                    [], 
                    available_kbs
                )
                return self._create_failure_analysis_message(analysis)
                
            st.info(f"📚 {len(kb_mappings)} bases mappées - Lancement recherche")
            search_contexts = await self.search_agent.multi_kb_search(message, kb_mappings)

            # Si aucun résultat, essayer avec les requêtes reformulées
            if not search_contexts:
                st.warning("❌ Aucun résultat trouvé - Tentative de reformulation")
                analysis = await self.no_results_handler.analyze_failed_search(
                    message,
                    [],
                    available_kbs
                )
                
                if analysis.reformulated_queries:
                    for query in analysis.reformulated_queries:
                        st.info(f"🔄 Essai avec: {query}")
                        new_contexts = await self.search_agent.multi_kb_search(
                            query,
                            kb_mappings
                        )
                        if new_contexts:
                            st.success("✅ Résultats trouvés avec la requête reformulée")
                            return await self._create_reformulated_response(
                                message, 
                                query, 
                                new_contexts
                            )
                            
                return self._create_failure_analysis_message(analysis)

        #st.info(f"✅ {sum(len(ctx.results) for ctx in search_contexts)} segments trouvés")
        
        # Générer la réponse
        response = await self._generate_response(message, search_contexts)
        response_message = self._create_response_message(response, search_contexts)
        
        self.conversation_history.append(response_message)
        return response_message

    def _create_failure_analysis_message(self, analysis: SearchFailureAnalysis) -> Message:
        """Crée un message d'erreur enrichi avec l'analyse"""
        content = [
            "Je n'ai pas trouvé de résultats satisfaisants pour votre recherche.",
            "\nCauses possibles :",
            *[f"- {cause}" for cause in analysis.possible_causes],
            "\nSuggestions :",
            *[f"- {action}" for action in analysis.suggested_actions]
        ]
        
        if analysis.reformulated_queries:
            content.extend([
                "\nVous pourriez essayer de reformuler votre question, par exemple :",
                *[f"- {query}" for query in analysis.reformulated_queries]
            ])
        
        return Message(
            role="assistant",
            content="\n".join(content),
            metadata={
                "failure_analysis": {
                    "type": analysis.failure_type,
                    "causes": analysis.possible_causes,
                    "suggestions": analysis.suggested_actions,
                    "reformulations": analysis.reformulated_queries
                }
            }
        )

    async def _create_reformulated_response(
        self,
        original_query: str,
        successful_query: str,
        search_contexts: List[SearchContext]
    ) -> Message:
        """
        Crée une réponse pour une recherche réussie après reformulation
        """
        response = await self._generate_response(successful_query, search_contexts)
        
        formatted_response = (
            f"J'ai trouvé des informations pertinentes en reformulant votre question "
            f"\"{original_query}\" en \"{successful_query}\" :\n\n{response}"
        )
        
        return self._create_response_message(
            formatted_response, 
            search_contexts,
            metadata_extra={
                "query_reformulation": {
                    "original": original_query,
                    "successful": successful_query
                }
            }
        )

    async def _filtered_search(
        self, 
        query: str, 
        search_filter: SearchFilter
    ) -> List[SearchContext]:
        """Effectue une recherche dans les bases filtrées"""
        #st.info("🔍 Début recherche filtrée")
        search_contexts = []
        
        for kb_id in search_filter.get_kb_ids():
            st.info(f"📖 Recherche dans base: {kb_id}")
            kb = self.kb_manager.load_knowledge_base(kb_id)
            if not kb:
                st.warning(f"❌ Base {kb_id} non trouvée")
                continue

            metadata_filter = search_filter.to_metadata_filter(kb_id)
            if metadata_filter:
                st.info(f"📑 Filtrage sur {len(search_filter.get_doc_ids(kb_id))} documents")

            results = await self.search_agent.search(
                query=query, 
                kb=kb, 
                filters=metadata_filter
            )

            if results:
                search_contexts.append(SearchContext(
                    kb_id=kb_id,
                    results=results,
                    mapping_score=1.0
                ))
                st.info(f"✅ {len(results)} résultats trouvés dans {kb_id}")

        return search_contexts

    async def _generate_response(self, query: str, search_contexts: List[SearchContext]) -> str:
        """Génère une réponse à partir des contextes de recherche"""
        context = self._build_context(search_contexts)
        prompt = self._build_response_prompt(query, context)
        messages = [{"role": "user", "content": prompt}]
        return self.llm.make_llm_call(messages)

    def _build_context(self, search_contexts: List[SearchContext]) -> str:
        """Construit le contexte à partir des résultats de recherche"""
        context_parts = []
        for ctx in search_contexts:
            kb_info = next(
                (kb for kb in self.kb_manager.list_knowledge_bases() 
                 if kb["id"] == ctx.kb_id), 
                {"title": ctx.kb_id}
            )
            context_parts.append(f"\nContexte de la base '{kb_info['title']}':")
            
            for result in ctx.results:
                context_parts.append(
                    f"Document '{result.doc_title}':\n{result.text}\n"
                )
        return "\n".join(context_parts)

    def _build_response_prompt(self, query: str, context: str) -> str:
        """Construit le prompt pour la génération de réponse"""
        return f"""
        Utilise le contexte suivant pour répondre à la question de manière claire et précise.
        Cite les sources pertinentes dans ta réponse quand c'est approprié.
        
        Contexte:
        {context}

        Question: {query}

        Réponse:
        """

    def _create_response_message(
        self, 
        response: str, 
        search_contexts: List[SearchContext],
        metadata_extra: Optional[dict] = None
    ) -> Message:
        """Crée un message formaté avec métadonnées"""
        metadata = {
            "sources": [
                {
                    "kb_id": ctx.kb_id,
                    "kb_title": next(
                        (kb["title"] for kb in self.kb_manager.list_knowledge_bases() 
                         if kb["id"] == ctx.kb_id),
                        ctx.kb_id
                    ),
                    "documents": [
                        {
                            "doc_id": result.doc_id,
                            "title": result.doc_title,
                            "relevance": result.relevance_score,
                            "page_numbers": result.page_numbers
                        }
                        for result in ctx.results
                    ]
                }
                for ctx in search_contexts
            ]
        }
        
        if metadata_extra:
            metadata.update(metadata_extra)
        
        return Message(
            role="assistant",
            content=response,
            metadata=metadata
        )