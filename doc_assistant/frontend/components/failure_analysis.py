# frontend/components/failure_analysis.py

import streamlit as st
from typing import List, Optional, Callable
from backend.agents.no_result_handler_agent import SearchFailureAnalysis

class FailureAnalysisComponent:
    """Composant pour afficher l'analyse des échecs de recherche"""
    
    def __init__(self):
        # Initialisation des styles personnalisés
        self._init_styles()
        
    def _init_styles(self):
        """Initialise les styles CSS personnalisés"""
        st.markdown("""
            <style>
            .failure-box {
                border: 1px solid #ff4b4b;
                border-radius: 4px;
                padding: 1rem;
                margin: 1rem 0;
            }
            .suggestion-box {
                border: 1px solid #ffa726;
                border-radius: 4px;
                padding: 1rem;
                margin: 0.5rem 0;
                background-color: #fff3e0;
            }
            .retry-box {
                border: 1px solid #2196f3;
                border-radius: 4px;
                padding: 1rem;
                margin: 0.5rem 0;
                background-color: #e3f2fd;
            }
            </style>
        """, unsafe_allow_html=True)
    
    def render(
        self,
        analysis: SearchFailureAnalysis,
        on_retry_query: Optional[Callable[[str], None]] = None
    ):
        """
        Affiche l'analyse d'échec avec des options interactives
        
        Args:
            analysis: Analyse de l'échec de recherche
            on_retry_query: Callback pour réessayer avec une requête reformulée
        """
        # En-tête avec le type d'échec
        failure_titles = {
            "no_kb": "🚫 Aucune base de connaissances pertinente",
            "no_results": "❌ Aucun résultat trouvé",
            "low_relevance": "⚠️ Résultats peu pertinents"
        }
        
        st.error(failure_titles.get(analysis.failure_type, "Échec de la recherche"))
        
        # Section des causes possibles
        with st.expander("📋 Causes possibles", expanded=True):
            for cause in analysis.possible_causes:
                st.markdown(f"- {cause}")
        
        # Section des actions suggérées
        with st.expander("💡 Actions suggérées", expanded=True):
            for action in analysis.suggested_actions:
                st.markdown(f"- {action}")
        
        # Section des requêtes reformulées si disponibles
        if analysis.reformulated_queries:
            st.markdown("### 🔄 Essayer avec une reformulation")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                selected_query = st.selectbox(
                    "Sélectionner une reformulation",
                    analysis.reformulated_queries,
                    format_func=lambda x: f'"{x}"'
                )
            
            with col2:
                if st.button("🔍 Essayer", type="primary") and on_retry_query:
                    with st.spinner("Nouvelle recherche en cours..."):
                        on_retry_query(selected_query)
        
        # Affichage contextuel selon le type d'échec
        if analysis.failure_type == "no_kb":
            st.info("""
                💾 **Conseil**: Commencez par créer une base de connaissances et y ajouter des documents
                dans l'onglet "Créer Base" de la barre latérale.
            """)
        elif analysis.failure_type == "low_relevance":
            st.warning(
                "ℹ️ **Note**: Les résultats trouvés ont une pertinence faible. "
                "Essayez d'être plus spécifique dans votre recherche."
            )
    
    def render_mini(self, analysis: SearchFailureAnalysis):
        """Version compacte pour affichage dans le chat"""
        with st.container():
            st.markdown(f"**{analysis.possible_causes[0]}**")
            
            if analysis.reformulated_queries:
                st.markdown("Suggestions de reformulation :")
                for query in analysis.reformulated_queries[:2]:  # Limiter à 2 suggestions
                    st.markdown(f"- `{query}`")
            
            st.markdown("---")

def display_failure_analysis(
    analysis: SearchFailureAnalysis,
    on_retry_query: Optional[Callable[[str], None]] = None,
    compact: bool = False
):
    """
    Fonction utilitaire pour afficher l'analyse d'échec
    
    Args:
        analysis: Analyse de l'échec
        on_retry_query: Callback pour réessayer une requête
        compact: Utiliser l'affichage compact
    """
    component = FailureAnalysisComponent()
    if compact:
        component.render_mini(analysis)
    else:
        component.render(analysis, on_retry_query)