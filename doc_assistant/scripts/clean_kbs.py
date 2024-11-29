#!/usr/bin/env python3
"""
Script de nettoyage manuel des bases de connaissances.
Permet de normaliser les doc_id contenant des caractères spéciaux.

Usage:
    python clean_kbs.py [--kb-id KB_ID] [--dry-run] [--all] [--storage-dir DIR]
    
Voici quelques exemples d'utilisation :

Lister les bases disponibles :    
    python scripts/clean_kbs.py
    
Simuler le nettoyage d'une base spécifique :
    python scripts/clean_kbs.py --kb-id ma_base --dry-run
    
Nettoyer une base spécifique :
    python scripts/clean_kbs.py --kb-id ma_base
    
Nettoyer toutes les bases :
    python scripts/clean_kbs.py --all
    
Simuler le nettoyage de toutes les bases avec un dossier de stockage personnalisé :
    python scripts/clean_kbs.py --all --dry-run --storage-dir /path/to/storage
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from backend.kb_management.manager import KnowledgeBaseManager
from frontend.utils.doc_id_cleaner import DocIDCleaner
from dotenv import load_dotenv


def setup_argparse() -> argparse.ArgumentParser:
    """Configure le parser d'arguments en ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Nettoie les doc_id des bases de connaissances"
    )
    
    parser.add_argument(
        "--kb-id",
        type=str,
        help="ID de la base à nettoyer. Si non spécifié avec --all, liste les bases disponibles."
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Nettoie toutes les bases de connaissances"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule les changements sans les appliquer"
    )
    
    parser.add_argument(
        "--storage-dir",
        type=str,
        default="~/dsRAG",
        help="Dossier de stockage des bases (défaut: ~/dsRAG)"
    )
    
    return parser

def create_report(
    kb_id: str, 
    migration_map: Dict[str, str], 
    success: bool, 
    error: Optional[str] = None
) -> dict:
    """Crée un rapport de migration pour une base"""
    return {
        "kb_id": kb_id,
        "documents_processed": len(migration_map),
        "success": success,
        "error": error,
        "migrations": migration_map
    }

def save_report(reports: list, storage_dir: str):
    """Sauvegarde le rapport de migration"""
    reports_dir = os.path.join(os.path.expanduser(storage_dir), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(reports_dir, f"cleanup_report_{timestamp}.txt")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Rapport de nettoyage des bases - {datetime.now()}\n")
        f.write("-" * 50 + "\n\n")
        
        for report in reports:
            f.write(f"Base: {report['kb_id']}\n")
            f.write(f"Documents traités: {report['documents_processed']}\n")
            f.write(f"Statut: {'✅ Succès' if report['success'] else '❌ Échec'}\n")
            
            if report['error']:
                f.write(f"Erreur: {report['error']}\n")
                
            if report['migrations']:
                f.write("\nMigrations effectuées:\n")
                for old_id, new_id in report['migrations'].items():
                    f.write(f"  {old_id} -> {new_id}\n")
                    
            f.write("\n" + "-" * 50 + "\n\n")
            
    return report_path

def clean_knowledge_base(
    kb_manager: KnowledgeBaseManager,
    kb_id: str,
    dry_run: bool = True
) -> dict:
    """Nettoie une base de connaissances et retourne un rapport"""
    try:
        cleaner = DocIDCleaner(kb_manager)
        
        print(f"\n🔍 Analyse de la base {kb_id}...")
        migration_map, backup_path = cleaner.clean_knowledge_base(
            kb_id=kb_id,
            dry_run=dry_run
        )
        
        if not migration_map:
            print(f"✨ Aucun nettoyage nécessaire pour {kb_id}")
            return create_report(kb_id, {}, True)
            
        if dry_run:
            print(f"\n📋 Changements proposés pour {kb_id}:")
            for old_id, new_id in migration_map.items():
                print(f"  {old_id} -> {new_id}")
        else:
            print(f"\n✅ Base {kb_id} nettoyée avec succès")
            print(f"📦 Sauvegarde créée: {backup_path}")
            
        return create_report(kb_id, migration_map, True)
        
    except Exception as e:
        error_msg = f"Erreur lors du nettoyage de {kb_id}: {str(e)}"
        print(f"\n❌ {error_msg}")
        return create_report(kb_id, {}, False, error_msg)

def main():
    """Point d'entrée principal du script"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Initialiser le gestionnaire de bases
    storage_dir = os.path.expanduser(args.storage_dir)
    kb_manager = KnowledgeBaseManager(storage_directory=storage_dir)
    
    # Récupérer la liste des bases
    available_kbs = kb_manager.list_knowledge_bases()
    if not available_kbs:
        print("❌ Aucune base de connaissances trouvée")
        return
        
    # Mode liste si aucune base spécifiée
    if not args.kb_id and not args.all:
        print("\n📚 Bases de connaissances disponibles:")
        for kb in available_kbs:
            print(f"  - {kb['id']}: {kb['title']}")
        print("\nUtilisez --kb-id <ID> ou --all pour nettoyer une ou toutes les bases")
        return
        
    # Déterminer les bases à traiter
    kbs_to_clean = []
    if args.all:
        kbs_to_clean = [kb["id"] for kb in available_kbs]
    elif args.kb_id:
        if args.kb_id not in [kb["id"] for kb in available_kbs]:
            print(f"❌ Base {args.kb_id} introuvable")
            return
        kbs_to_clean = [args.kb_id]
        
    # Mode simulation
    if args.dry_run:
        print("\n🔍 MODE SIMULATION - Aucune modification ne sera effectuée")
        
    reports = []
    total_kbs = len(kbs_to_clean)
    
    # Traiter chaque base
    for idx, kb_id in enumerate(kbs_to_clean, 1):
        print(f"\n[{idx}/{total_kbs}] Traitement de {kb_id}")
        report = clean_knowledge_base(kb_manager, kb_id, args.dry_run)
        reports.append(report)
        
    # Sauvegarder le rapport si des changements ont été effectués
    if not args.dry_run and any(report['migrations'] for report in reports):
        report_path = save_report(reports, storage_dir)
        print(f"\n📝 Rapport détaillé sauvegardé: {report_path}")
        
    # Résumé final
    success_count = sum(1 for r in reports if r['success'])
    print(f"\n✅ {success_count}/{len(reports)} bases traitées avec succès")
    
    if not all(r['success'] for r in reports):
        print("⚠️ Certaines bases ont rencontré des erreurs, consultez le rapport pour plus de détails")

if __name__ == "__main__":
    try:
        load_dotenv()
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Opération annulée par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {str(e)}")
        sys.exit(1)