# doc_assistant/frontend/chat_window.py
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
        
        self._init_styles()

    def _init_styles(self):
        """Initialise les styles CSS pour un thème sombre"""
        st.markdown("""
            <style>
            .source-container {
                border: 1px solid #333;
                border-radius: 8px;
                padding: 10px;
                margin: 10px 0;
                background-color: #1e1e1e;  /* Fond sombre */
                color: #ffffff;  /* Texte blanc */
            }
            .source-header {
                font-weight: bold;
                color: #64B5F6;  /* Bleu plus clair pour meilleur contraste */
                margin-bottom: 5px;
                font-size: 1.1em;
            }
            .document-item {
                padding: 12px;
                margin: 5px 0;
                border-left: 3px solid #4CAF50;
                background-color: #2d2d2d;  /* Fond légèrement plus clair */
                color: #ffffff;
                border-radius: 4px;
            }
            .document-item:hover {
                background-color: #363636;  /* Effet hover subtil */
                transition: background-color 0.2s ease;
            }
            .relevance-badge {
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8em;
                font-weight: 500;
            }
            .page-info {
                color: #aaaaaa;  /* Gris clair pour info secondaire */
                font-size: 0.9em;
                font-style: italic;
                margin-top: 4px;
            }
            .source-divider {
                margin: 10px 0;
                border-top: 1px solid #333;
            }
            /* Style pour l'expander de Streamlit */
            .streamlit-expanderHeader {
                background-color: #1e1e1e !important;
                color: #ffffff !important;
            }
            /* Style pour le contenu de l'expander */
            .streamlit-expanderContent {
                background-color: #1e1e1e !important;
                border: none !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
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
        
    def _display_sources(self, sources: list):
        """Affiche les sources avec un thème sombre"""
        with st.expander("📚 Sources", expanded=False):
            for source in sources:
                st.markdown(f"""
                    <div class="source-container">
                        <div class="source-header">
                            🗄️ Base: {source.get('kb_title', source['kb_id'])}
                        </div>
                """, unsafe_allow_html=True)
                
                for doc in source['documents']:
                    # Calcul du niveau de pertinence avec des couleurs adaptées au thème sombre
                    relevance = float(doc['relevance'])
                    if relevance >= 0.8:
                        relevance_color = "#00C853"  # Vert vif
                        relevance_text_color = "#000000"  # Texte noir
                    elif relevance >= 0.6:
                        relevance_color = "#FFD600"  # Jaune vif
                        relevance_text_color = "#000000"  # Texte noir
                    else:
                        relevance_color = "#FF3D00"  # Orange vif
                        relevance_text_color = "#000000"  # Texte noir
                    
                    # Formatage des pages
                    page_info = ""
                    if doc.get('page_numbers') and any(p is not None for p in doc['page_numbers']):
                        start, end = doc['page_numbers']
                        if start == end or end is None:
                            page_info = f"📄 page {start}"
                        else:
                            page_info = f"📄 pages {start}-{end}"
                    
                    st.markdown(f"""
                        <div class="document-item">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: 500;">{doc['title']}</span>
                                <span class="relevance-badge" 
                                      style="background-color: {relevance_color}; color: {relevance_text_color}">
                                    {relevance:.2f}
                                </span>
                            </div>
                            <div class="page-info">{page_info}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('<div class="source-divider"></div>', unsafe_allow_html=True)


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
                        
                        if analysis.reformulated_queries:
                            cols = st.columns(len(analysis.reformulated_queries[:2]))
                            for idx, query in enumerate(analysis.reformulated_queries[:2]):
                                with cols[idx]:
                                    if st.button(f"🔄 Essayer : {query}", key=f"retry_{hash(query)}"):
                                        await self._retry_query(query, search_filter)
                    
                    # Affichage des informations de reformulation
                    elif "query_reformulation" in metadata:
                        reformulation = metadata["query_reformulation"]
                        st.info(
                            f"💡 Requête reformulée : \n"
                            f"'{reformulation['original']}' → '{reformulation['successful']}'"
                        )
                    
                    # Affichage des sources avec le nouveau design
                    if "sources" in metadata:
                        self._display_sources(metadata["sources"])

        # Zone de saisie
        if prompt := st.chat_input("Posez votre question..."):
            with st.spinner("Recherche en cours..."):
                await self.process_message(prompt, search_filter)
            st.rerun()