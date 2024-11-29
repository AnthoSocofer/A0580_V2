#doc_assistant/backend/kb_managment/manager.py
"""
Knowledge base manager main class

Created: 2024-10-30
"""
from pathlib import Path
import json
from typing import Optional, List, Dict, Any, Literal
import os
import chromadb
from dsrag.knowledge_base import KnowledgeBase 
from dsrag.database.vector.chroma_db import ChromaDB
from dsrag.database.chunk.sqlite_db import SQLiteDB
from dsrag.embedding import (
    Embedding,
    OpenAIEmbedding,
    CohereEmbedding,
    VoyageAIEmbedding
)
from dsrag.reranker import (
    Reranker,
    CohereReranker,
    VoyageReranker,
    NoReranker
)
from dsrag.llm import OpenAIChatAPI, AnthropicChatAPI

class KnowledgeBaseManager:
    """Gestionnaire de bases de connaissances utilisant ChromaDB comme stockage vectoriel"""
    
    # Définition des modèles d'embedding supportés
    SUPPORTED_EMBEDDING_MODELS = {
        "openai": {
            "class": OpenAIEmbedding,
            "models": ["text-embedding-3-small", "text-embedding-3-large"],
            "default_dimensions": {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072
            }
        },
        "cohere": {
            "class": CohereEmbedding,
            "models": ["embed-english-v3.0", "embed-multilingual-v3.0"],
            "default_dimensions": {
                "embed-english-v3.0": 1024,
                "embed-multilingual-v3.0": 1024
            }
        },
        "voyage": {
            "class": VoyageAIEmbedding,
            "models": ["voyage-large-2", "voyage-code-2"],
            "default_dimensions": {
                "voyage-large-2": 1536,
                "voyage-code-2": 1536
            }
        }
    }

    # Définition des modèles de reranking supportés
    SUPPORTED_RERANKERS = {
        "cohere": {
            "class": CohereReranker,
            "models": ["rerank-english-v3.0", "rerank-multilingual-v3.0"]
        },
        "voyage": {
            "class": VoyageReranker,
            "models": ["rerank-1"]
        },
        "none": {
            "class": NoReranker,
            "models": ["default"]
        }
    }

    def __init__(self, storage_directory: str = "~/dsRAG"):
        self.storage_directory = os.path.expanduser(storage_directory)
        self.vector_storage_path = os.path.join(self.storage_directory, "vector_storage")
        self.metadata_dir = os.path.join(self.storage_directory, "metadata")
        os.makedirs(self.metadata_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.vector_storage_path)

    def _create_embedding_model(
        self,
        provider: str,
        model_name: str,
        dimension: Optional[int] = None
    ) -> Embedding:
        """
        Crée une instance du modèle d'embedding selon la configuration
        """
        if provider not in self.SUPPORTED_EMBEDDING_MODELS:
            raise ValueError(f"Provider d'embedding non supporté: {provider}")
            
        if model_name not in self.SUPPORTED_EMBEDDING_MODELS[provider]["models"]:
            raise ValueError(f"Modèle d'embedding non supporté pour {provider}: {model_name}")

        model_class = self.SUPPORTED_EMBEDDING_MODELS[provider]["class"]
        
        if dimension is None:
            dimension = self.SUPPORTED_EMBEDDING_MODELS[provider]["default_dimensions"][model_name]

        return model_class(model=model_name, dimension=dimension)

    def _create_reranker(
        self,
        provider: str,
        model_name: str
    ) -> Reranker:
        """
        Crée une instance du modèle de reranking selon la configuration
        """
        if provider not in self.SUPPORTED_RERANKERS:
            raise ValueError(f"Provider de reranking non supporté: {provider}")
            
        if model_name not in self.SUPPORTED_RERANKERS[provider]["models"]:
            raise ValueError(f"Modèle de reranking non supporté pour {provider}: {model_name}")

        model_class = self.SUPPORTED_RERANKERS[provider]["class"]
        return model_class(model=model_name)

    def create_knowledge_base(
        self,
        kb_id: str,
        title: str = "",
        description: str = "",
        language: str = "en",
        embedding_config: Optional[dict] = None,  # Nouveau paramètre
        embedding_provider: str = "openai",
        embedding_model: str = "text-embedding-3-small",
        embedding_dimension: Optional[int] = None,
        reranker_provider: str = "cohere",
        reranker_model: str = "rerank-multilingual-v3.0",
        llm_provider: Literal["openai", "anthropic"] = "anthropic",
    ) -> KnowledgeBase:
        """
        Crée une nouvelle base de connaissances avec configuration personnalisée
        
        Args:
            kb_id: Identifiant unique de la base
            title: Titre de la base
            description: Description de la base
            language: Langue des documents ("en", "fr", etc.)
            embedding_config: Modèle d'embedding utilisé
            embedding_provider: Fournisseur du modèle d'embedding
            embedding_model: Nom du modèle d'embedding
            embedding_dimension: Dimension des vecteurs (optionnel)
            reranker_provider: Fournisseur du modèle de reranking
            reranker_model: Nom du modèle de reranking
            llm_provider: Fournisseur du LLM pour l'auto-contexte
        """
        # Création des composants avec la configuration spécifiée
        embedding_model = self._create_embedding_model(
            embedding_provider,
            embedding_model,
            embedding_dimension
        )
        
        reranker = self._create_reranker(
            reranker_provider,
            reranker_model
        )
        
        vector_db = ChromaDB(kb_id, storage_directory=self.storage_directory)
        chunk_db = SQLiteDB(kb_id, storage_directory=self.storage_directory)

        # Sélection du modèle LLM pour l'auto-contexte
        if llm_provider == "openai":
            auto_context_model = OpenAIChatAPI()
        else:
            auto_context_model = AnthropicChatAPI()

        # Création de la base de connaissances
        kb = KnowledgeBase(
            kb_id=kb_id,
            title=title,
            description=description,
            language=language,
            storage_directory=self.storage_directory,
            embedding_model=embedding_model,
            vector_db=vector_db,
            chunk_db=chunk_db,
            reranker=reranker,
            auto_context_model=auto_context_model,
            exists_ok=False
        )
        
        # Les métadonnées sont correctement sauvegardées avec la config d'embedding
        metadata = {
            'title': title,
            'description': description,
            'language': language,
            'embedding_config': embedding_config or {
                'provider': embedding_provider,
                'model': embedding_model,
                'dimension': embedding_dimension 
            }
        }
        
        # Sauvegarde dans un fichier JSON séparé
        metadata_path = os.path.join(self.metadata_dir, f"{kb_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
                
        return kb

    def load_knowledge_base(
        self,
        kb_id: str,
        reranker_provider: Optional[str] = None,
        reranker_model: Optional[str] = None
    ) -> Optional[KnowledgeBase]:
        """
        Charge une base de connaissances existante avec possibilité de modifier le reranker
        
        Args:
            kb_id: Identifiant de la base à charger
            reranker_provider: Optionnel, nouveau provider de reranking
            reranker_model: Optionnel, nouveau modèle de reranking
        """
        try:
            metadata_path = os.path.join(self.storage_directory, "metadata", f"{kb_id}.json")
            
            if not os.path.exists(metadata_path):
                return None
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            embedding_config = metadata.get('embedding_config')
            
            if not embedding_config:
                raise ValueError(f"Configuration d'embedding manquante pour la base {kb_id}")

            # Créer le modèle d'embedding
            embedding_model = self._create_embedding_model(
                provider=embedding_config['provider'],
                model_name=embedding_config['model'],
                dimension=embedding_config['dimension']
            )
            # Si un nouveau reranker est spécifié, on le crée
            reranker = None
            if reranker_provider and reranker_model:
                reranker = self._create_reranker(reranker_provider, reranker_model)
            
            # Créer la base avec le bon modèle d'embedding
            kb = KnowledgeBase(
                kb_id=kb_id,
                storage_directory=self.storage_directory,
                embedding_model=embedding_model,  # Utiliser le modèle correct
                reranker=reranker,
                exists_ok=True
            )
            return kb
        
        except Exception as e:
            print(f"Erreur lors du chargement de la base {kb_id}: {str(e)}")
            return None

    def add_document(
        self,
        kb_id: str,
        file_path: str = "",
        text: str = "",
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,  # <= Changé ici
        embedding_model: Optional[Embedding] = None,  # Ajout du paramètre
        auto_context_config: Optional[Dict[str, Any]] = None,
        semantic_sectioning_config: Optional[Dict[str, Any]] = None,
        chunk_size: int = 800,
        min_length_for_chunking: int = 1600,
    ) -> bool:
        try:
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                raise Exception(f"Base de connaissances {kb_id} introuvable")
            
            # Si un modèle d'embedding est fourni, l'utiliser
            if embedding_model:
                kb.embedding_model = embedding_model
                
            # Initialisation des dictionnaires par défaut    
            metadata = metadata or {}
            auto_context_config = auto_context_config or {}
            semantic_sectioning_config = semantic_sectioning_config or {}
                
            if not doc_id:
                if file_path:
                    doc_id = os.path.basename(file_path)
                else:
                    doc_id = f"doc_{len(kb.chunk_db.get_all_doc_ids())}"

            # Ajout du document avec des paramètres valides
            kb.add_document(
                doc_id=doc_id,
                text=text,
                file_path=file_path,
                auto_context_config=auto_context_config,
                semantic_sectioning_config=semantic_sectioning_config,
                chunk_size=chunk_size,
                min_length_for_chunking=min_length_for_chunking,
                metadata=metadata
            )
            return True
                
        except Exception as e:
            raise Exception(f"Erreur lors de l'ajout du document dans {kb_id}: {str(e)}")

    def delete_document(self, kb_id: str, doc_id: str) -> bool:
        """
        Supprime un document d'une base de connaissances
        """
        try:
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                return False
            kb.delete_document(doc_id)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du document {doc_id}: {str(e)}")
            return False

    def get_document(self, kb_id: str, doc_id: str, include_content: bool = True) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations complètes d'un document
        """
        try:
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                return None
            
            doc = kb.chunk_db.get_document(doc_id, include_content=include_content)
            if not doc:
                return None
            
            return {
                'id': doc['id'],
                'title': doc['title'],
                'content': doc['content'],
                'summary': doc['summary'],
                'created_on': doc['created_on'],
                'metadata': doc.get('metadata', {}),
            }
        except Exception as e:
            print(f"Erreur lors de la récupération du document {doc_id}: {str(e)}")
            return None

    def list_documents(self, kb_id: str) -> List[Dict[str, Any]]:
        """
        Liste tous les documents d'une base de connaissances
        """
        try:
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                return []
            
            documents = []
            for doc_id in kb.chunk_db.get_all_doc_ids():
                doc = self.get_document(kb_id, doc_id, include_content=False)
                if doc:
                    documents.append(doc)
            
            return documents
        except Exception as e:
            print(f"Erreur lors de la liste des documents de {kb_id}: {str(e)}")
            return []

    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
            """
            Liste toutes les bases de connaissances disponibles
            
            Returns:
                List[Dict[str, Any]]: Liste des bases avec leurs métadonnées
            """
            kb_list = []
            
            # Parcourir tous les fichiers de métadonnées
            for filename in os.listdir(self.metadata_dir):
                if filename.endswith('.json'):
                    kb_id = filename[:-5]  # Enlever l'extension .json
                    try:
                        with open(os.path.join(self.metadata_dir, filename), 'r') as f:
                            metadata = json.load(f)
                            kb_list.append({
                                'id': kb_id,
                                'title': metadata.get('title', kb_id),
                                'description': metadata.get('description', ''),
                                'language': metadata.get('language', 'en'),
                                'created_on': metadata.get('created_on'),
                            })
                    except Exception as e:
                        print(f"Erreur lors de la lecture des métadonnées de {kb_id}: {str(e)}")
                        continue
                        
            return kb_list
        
    def delete_knowledge_base(self, kb_id: str) -> bool:
        """
        Supprime une base de connaissances et tous ses documents
        
        Args:
            kb_id: Identifiant de la base à supprimer
            
        Returns:
            bool: True si la suppression a réussi, False sinon
        """
        try:
            # Vérifier si la base existe
            metadata_path = os.path.join(self.storage_directory, "metadata", f"{kb_id}.json")
            if not os.path.exists(metadata_path):
                return False
                
            # Charger la base pour la supprimer proprement
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                return False
            
            # Supprimer la base via dsRAG
            kb.delete()
            
            # Supprimer les métadonnées
            os.remove(metadata_path)
            
            # Supprimer la collection ChromaDB
            try:
                self.chroma_client.delete_collection(kb_id)
            except ValueError:
                # La collection peut déjà avoir été supprimée par kb.delete()
                pass
                
            return True
            
        except Exception as e:
            print(f"Erreur lors de la suppression de la base {kb_id}: {str(e)}")
            return False
            
# # Création avec OpenAI embeddings et Cohere reranking
# kb1 = manager.create_knowledge_base(
#     kb_id="base1",
#     embedding_provider="openai",
#     embedding_model="text-embedding-3-small",
#     reranker_provider="cohere",
#     reranker_model="rerank-english-v3.0"
# )

# # Création avec Cohere embeddings et Voyage reranking
# kb2 = manager.create_knowledge_base(
#     kb_id="base2",
#     embedding_provider="cohere",
#     embedding_model="embed-english-v3.0