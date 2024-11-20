# frontend/components/chat_window.py
import streamlit as st
from typing import Optional
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.no_result_handler_agent import SearchFailureAnalysis
from backend.utils.filter_utils import SearchFilter

class ChatWindow:
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
        if 'messages' not in st.session_state:
            st.session_state.messages = []

    async def process_message(
        self, 
        prompt: str, 
        search_filter: Optional[SearchFilter]
    ) -> None:
        """Traite un message utilisateur avec filtres optionnels"""
        # Ajouter le message utilisateur à l'historique
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Ensure filter_kb_select exists in session state to prevent errors
        if 'filter_kb_select' not in st.session_state:
            st.session_state.filter_kb_select = []
        
        # Obtenir la réponse de l'orchestrateur
        response = await self.orchestrator.process_message(prompt, search_filter)
        
        # Ajouter la réponse à l'historique
        st.session_state.messages.append({
            "role": "assistant",
            "content": response.content,
            "metadata": response.metadata
        })

    async def _retry_query(
        self, 
        query: str, 
        search_filter: Optional[SearchFilter]
    ) -> None:
        """Réessaie une recherche avec une requête reformulée"""
        await self.process_message(query, search_filter)
        st.rerun()

    def _display_failure_analysis(
        self, 
        analysis: SearchFailureAnalysis, 
        compact: bool = True
    ) -> None:
        """Affiche l'analyse d'échec de manière compacte ou détaillée"""
        if compact:
            with st.container():
                st.markdown(f"**{analysis.possible_causes[0]}**")
                
                if analysis.reformulated_queries:
                    st.markdown("Suggestions de reformulation :")
                    for query in analysis.reformulated_queries[:2]:
                        st.markdown(f"- `{query}`")
                
                st.markdown("---")
        else:
            with st.expander("📋 Analyse détaillée", expanded=True):
                st.markdown("### Causes possibles")
                for cause in analysis.possible_causes:
                    st.markdown(f"- {cause}")
                    
                st.markdown("### Actions suggérées")
                for action in analysis.suggested_actions:
                    st.markdown(f"- {action}")
                
                if analysis.reformulated_queries:
                    st.markdown("### Reformulations suggérées")
                    for query in analysis.reformulated_queries:
                        st.markdown(f"- `{query}`")

    async def render(self, search_filter: Optional[SearchFilter] = None) -> None:
        """Affiche l'interface de chat avec gestion enrichie des messages"""
        chat_container = st.container()
        
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    
                    # Traitement des métadonnées
                    metadata = message.get("metadata", {})
                    
                    # Affichage de l'analyse d'échec si présente
                    if "failure_analysis" in metadata:
                        analysis = SearchFailureAnalysis(
                            failure_type=metadata["failure_analysis"]["type"],
                            possible_causes=metadata["failure_analysis"]["causes"],
                            suggested_actions=metadata["failure_analysis"]["suggestions"],
                            reformulated_queries=metadata["failure_analysis"].get("reformulations")
                        )
                        
                        self._display_failure_analysis(analysis)
                        
                        # Boutons pour réessayer avec les reformulations suggérées
                        if analysis.reformulated_queries:
                            for query in analysis.reformulated_queries[:2]:
                                if st.button(f"🔄 Essayer : {query}", key=f"retry_{hash(query)}"):
                                    await self._retry_query(query, search_filter)
                    
                    # Affichage des informations de reformulation
                    elif "query_reformulation" in metadata:
                        reformulation = metadata["query_reformulation"]
                        st.info(
                            f"💡 Requête reformulée : \n"
                            f"'{reformulation['original']}' → '{reformulation['successful']}'"
                        )
                    
                    # Affichage des sources si disponibles
                    if "sources" in metadata:
                        with st.expander("📚 Sources"):
                            for source in metadata["sources"]:
                                st.write(f"**Base**: {source.get('kb_title', source['kb_id'])}")
                                for doc in source["documents"]:
                                    score = f"{doc['relevance']:.2f}"
                                    pages = ""
                                    if doc.get('page_numbers') and any(p is not None for p in doc['page_numbers']):
                                        start, end = doc['page_numbers']
                                        if start == end or end is None:
                                            pages = f" (page {start})"
                                        else:
                                            pages = f" (pages {start}-{end})"
                                            
                                    st.markdown(
                                        f"- {doc['title']}{pages} "
                                        f"*(pertinence: {score})*"
                                    )

        # Zone de saisie
        if prompt := st.chat_input("Posez votre question..."):
            # Traiter le message avec les filtres actifs
            with st.spinner("Recherche en cours..."):
                await self.process_message(prompt, search_filter)
            
            # Rafraîchir l'interface
            st.rerun()