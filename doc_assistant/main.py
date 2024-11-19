import streamlit as st
from pathlib import Path
import asyncio
from frontend.components.filter_tab import FilterTab
from frontend.components.kb_creation_tab import KBCreationComponent
from frontend.components.document_ingestion_tab import DocumentIngestionComponent
from frontend.components.delete_docs_tab import DeleteDocsComponent
from frontend.components.delete_kb_tab import DeleteKBComponent  # Nouveau composant
from frontend.components.chat_window import ChatWindow
from backend.kb_management.manager import KnowledgeBaseManager
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.query_kb_mapper_agent import QueryKBMapper
from backend.agents.search_agent import SearchAgent
from backend.utils.config import ConfigManager
from dsrag.llm import OpenAIChatAPI

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
        # Initialisation des services
        kb_manager = KnowledgeBaseManager(storage_directory=str(storage_dir))
        llm_service = OpenAIChatAPI()
        query_mapper = QueryKBMapper(kb_manager, llm_service)
        search_agent = SearchAgent(kb_manager)
        orchestrator = AgentOrchestrator(kb_manager, query_mapper, search_agent, llm_service)

        st.title("Assistant Documentaire")

        with st.sidebar:
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "Filtrer", 
                "Créer Base", 
                "Ajouter Documents",
                "Supprimer Documents",
                "Supprimer Base"
            ])
            
            with tab1:
                filter_tab = FilterTab(kb_manager)
                active_filters = filter_tab.render()
                
            with tab2:
                kb_creation = KBCreationComponent(kb_manager)
                kb_creation.render()
                
            with tab3:
                doc_ingestion = DocumentIngestionComponent(kb_manager)
                doc_ingestion.render()
                
            with tab4:
                delete_docs = DeleteDocsComponent(kb_manager)
                delete_docs.render()

            with tab5:
                delete_kb = DeleteKBComponent(kb_manager)
                delete_kb.render()
        chat_window = ChatWindow(orchestrator)
        await chat_window.render(active_filters)

    except Exception as e:
        st.error(f"Erreur lors de l'initialisation de l'application: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())