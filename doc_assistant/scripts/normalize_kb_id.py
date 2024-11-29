import os
import sys
import argparse
from pathlib import Path
import json
from typing import Dict, List, Any
import logging
from datetime import datetime
import shutil

# Ajouter le répertoire parent au PYTHONPATH pour les imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.append(project_root)

from backend.utils.string_nomalizer import StringNormalizer
from backend.kb_management.manager import KnowledgeBaseManager
from dsrag.knowledge_base import KnowledgeBase
from dotenv import load_dotenv

load_dotenv()
# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'kb_normalization_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

def create_backup(kb_path: Path, backup_dir: Path) -> bool:
    """
    Crée une sauvegarde des fichiers de la base de connaissances.
    """
    try:
        # Créer le dossier de backup avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copier tous les fichiers liés à la base
        if kb_path.exists():
            shutil.copytree(kb_path, backup_path / kb_path.name, dirs_exist_ok=True)
            logger.info(f"Backup créé avec succès dans {backup_path}")
            return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du backup: {str(e)}")
        return False
    
def get_id_mapping(kb: KnowledgeBase) -> Dict[str, str]:
    """
    Génère un mapping entre les anciens et nouveaux doc_ids.
    """
    id_mapping = {}
    doc_ids = kb.chunk_db.get_all_doc_ids()
    
    for old_id in doc_ids:
        # Récupérer les métadonnées pour voir si le doc_id a déjà été normalisé
        doc_info = kb.chunk_db.get_document(old_id)
        if doc_info and 'metadata' in doc_info and doc_info['metadata'].get('normalized_id'):
            # Si déjà normalisé, garder le même ID
            new_id = old_id
        else:
            # Sinon, générer un nouveau doc_id normalisé
            new_id = StringNormalizer.normalize_doc_id(old_id)
            
        id_mapping[old_id] = new_id
        
    return id_mapping

def normalize_kb_ids(kb_id: str, storage_dir: str, dry_run: bool = True) -> bool:
    """
    Normalise les doc_ids d'une base de connaissances.
    
    Args:
        kb_id: Identifiant de la base à normaliser
        storage_dir: Répertoire de stockage des bases
        dry_run: Si True, simule seulement les changements
    """
    try:
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Début de la normalisation de la base {kb_id}")
        
        # Initialiser le manager et charger la base
        kb_manager = KnowledgeBaseManager(storage_directory=storage_dir)
        kb = kb_manager.load_knowledge_base(kb_id)
        
        if not kb:
            logger.error(f"Base {kb_id} introuvable")
            return False
            
        # Créer un backup si ce n'est pas un dry run
        if not dry_run:
            kb_path = Path(storage_dir) / "vector_storage" / kb_id
            backup_dir = Path(storage_dir) / "backups"
            if not create_backup(kb_path, backup_dir):
                logger.error("Échec de la création du backup. Arrêt de la normalisation.")
                return False
        
        # Obtenir le mapping des IDs
        id_mapping = get_id_mapping(kb)
        
        # Afficher les changements prévus
        changes_detected = False
        for old_id, new_id in id_mapping.items():
            if old_id != new_id:
                changes_detected = True
                logger.info(f"Document à renommer: {old_id} -> {new_id}")
        
        if not changes_detected:
            logger.info("Aucune normalisation nécessaire")
            return True
            
        if dry_run:
            logger.info("Mode dry run - Aucune modification effectuée")
            return True
            
        # Effectuer les modifications
        success_count = 0
        error_count = 0
        
        for old_id, new_id in id_mapping.items():
            if old_id == new_id:
                continue
                
            try:
                # Récupérer le document complet
                doc_info = kb.chunk_db.get_document(old_id, include_content=True)
                if not doc_info:
                    logger.warning(f"Document {old_id} non trouvé, passage au suivant")
                    continue
                
                # Mettre à jour les métadonnées
                metadata = doc_info.get('metadata', {})
                metadata['original_doc_id'] = old_id
                metadata['normalized_id'] = True
                
                # Réinjecter le document avec le nouvel ID
                kb.add_document(
                    doc_id=new_id,
                    text=doc_info.get('content', ''),
                    metadata=metadata,
                    auto_context_config={"use_generated_title": False}
                )
                
                # Supprimer l'ancien document
                kb.delete_document(old_id)
                
                success_count += 1
                logger.info(f"Document {old_id} renommé avec succès en {new_id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Erreur lors du traitement de {old_id}: {str(e)}")
                
        # Rapport final
        logger.info(f"""
        Normalisation terminée:
        - Documents traités avec succès: {success_count}
        - Erreurs: {error_count}
        """)
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Erreur lors de la normalisation: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Normalise les doc_ids d\'une base de connaissances')
    parser.add_argument('kb_id', help='Identifiant de la base à normaliser')
    parser.add_argument('--storage-dir', default='~/dsRAG',
                       help='Répertoire de stockage des bases')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simule les changements sans les appliquer')
    
    args = parser.parse_args()
    
    # Expandre le chemin utilisateur
    storage_dir = os.path.expanduser(args.storage_dir)
    
    # Lancer la normalisation
    success = normalize_kb_ids(args.kb_id, storage_dir, args.dry_run)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()