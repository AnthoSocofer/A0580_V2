import streamlit as st
from pathlib import Path
import asyncio
from frontend.components.filter_tab import FilterTab
from frontend.components.kb_creation_tab import KBCreationComponent
from frontend.components.document_ingestion_tab import DocumentIngestionComponent
from frontend.components.delete_docs_tab import DeleteDocsComponent
from frontend.components.delete_kb_tab import DeleteKBComponent
from frontend.components.chat_window import ChatWindow
from frontend.components.document_viewer_tab import DocumentViewerComponent
from backend.kb_management.manager import KnowledgeBaseManager
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.query_kb_mapper_agent import QueryKBMapper
from backend.agents.search_agent import SearchAgent
from backend.utils.config import ConfigManager
from frontend.components.llm_selector import LLMSelector

async def main():
    # Configuration initiale
    try:
        ConfigManager.setup_environment()
    except Exception as e:
        st.error(f"Erreur de configuration: {str(e)}")
        return

    st.set_page_config(
        page_title="Assistant Documentaire",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Configuration des chemins
    base_dir = Path(__file__).parent
    storage_dir = base_dir / "data/knowledge_bases/chromadb"
    storage_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialisation des gestionnaires
        kb_manager = KnowledgeBaseManager(storage_directory=str(storage_dir))
        llm_selector = LLMSelector()

        # Organisation de la sidebar avec tabs
        with st.sidebar:
            st.title("🛠️ Configuration")
            
            # Création des onglets principaux
            tab_docs, tab_llm, tab_filter, tab_kb = st.tabs([
                "📚 Documents",
                "🤖 Modèle LLM",
                "🔍 Filtres",
                "⚙️ Gestion Bases"
            ])
            # Onglet visualisation des documents
            with tab_docs:
                doc_viewer = DocumentViewerComponent(kb_manager)
                doc_viewer.render()
                
            # Onglet configuration LLM
            with tab_llm:
                llm = llm_selector.render()

            # Onglet filtres de recherche
            with tab_filter:
                filter_tab = FilterTab(kb_manager)
                active_filters = filter_tab.render()
                
            # Onglet gestion des bases de connaissances
            with tab_kb:
                kb_tabs = st.tabs([
                    "Créer Base",
                    "Ajouter Docs",
                    "Supprimer Docs",
                    "Supprimer Base"
                ])
                
                with kb_tabs[0]:
                    kb_creation = KBCreationComponent(kb_manager)
                    kb_creation.render()
                
                with kb_tabs[1]:
                    doc_ingestion = DocumentIngestionComponent(kb_manager)
                    doc_ingestion.render()
                
                with kb_tabs[2]:
                    delete_docs = DeleteDocsComponent(kb_manager)
                    delete_docs.render()

                with kb_tabs[3]:
                    delete_kb = DeleteKBComponent(kb_manager)
                    delete_kb.render()

        # Interface de chat principale
        st.title("💬 Assistant Documentaire Demo")
        
        # Initialisation des agents avec le LLM sélectionné
        query_mapper = QueryKBMapper(kb_manager, llm)
        search_agent = SearchAgent(kb_manager)
        orchestrator = AgentOrchestrator(kb_manager, query_mapper, search_agent, llm)
        
        chat_window = ChatWindow(orchestrator)
        await chat_window.render(active_filters)

    except Exception as e:
        st.error(f"Erreur lors de l'initialisation de l'application: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())