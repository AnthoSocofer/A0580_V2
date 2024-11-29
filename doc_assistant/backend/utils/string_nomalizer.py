import os
import re
import hashlib
import unicodedata
from typing import Optional

class StringNormalizer:
    """Utilitaire pour normaliser les chaînes de caractères"""
    
    @staticmethod
    def normalize_doc_id(filename: str, max_length: int = 100, use_hash: bool = True) -> str:
        """
        Normalise un nom de fichier pour créer un doc_id compatible avec SQLite.
        Remplace les caractères spéciaux problématiques comme les apostrophes et guillemets par des underscores.
    
        Args:
            filename: Le nom de fichier original
            max_length: Longueur maximale du doc_id final
            use_hash: Ajoute un hash pour garantir l'unicité
        
        Returns:
            str: Un doc_id normalisé et compatible avec SQLite
        """
        # Gestion des cas limites
        if not filename:
            return "unnamed_doc"
    
        name = filename
        
        # 1. Convertir en minuscules et supprimer l'extension
        #name = os.path.splitext(filename.lower())[0]
    
        # 2. Normaliser les caractères accentués
        #name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    
        # 3. Remplacer spécifiquement les apostrophes et guillemets par des underscores
        name = re.sub(r'[\'"]', '_', name)
    
        # 4. Remplacer les autres caractères spéciaux par des tirets
        #name = re.sub(r'[^a-z0-9_]+', '-', name)  # Modifié pour préserver les underscores
    
        # 5. Supprimer les tirets et underscores multiples
        #name = re.sub(r'[-_]+', '-', name)
    
        # 6. Supprimer les tirets aux extrémités
        #name = name.strip('-')
    
        # 7. Limiter la longueur de base pour laisser de la place au hash
        #max_base_length = max_length - 9 if use_hash else max_length
        #name = name[:max_base_length]
    
        # 8. Ajouter un hash si demandé
        #if use_hash:
        #    hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
        #    name = f"{name}-{hash_suffix}"
    
        # 9. S'assurer que l'ID commence par une lettre
        #if not name[0].isalpha():
        #    name = f"doc-{name}"
   
        return name

    @staticmethod
    def is_valid_doc_id(doc_id: str) -> bool:
        """
        Vérifie si un doc_id est valide pour SQLite.
        """
        if not doc_id:
            return False
            
        # Vérifier le format général avec une regex
        pattern = r'^[a-z][a-z0-9-]*$'
        return bool(re.match(pattern, doc_id))

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Nettoie un nom de fichier en conservant l'extension.
        """
        base, ext = os.path.splitext(filename)
        sanitized_base = StringNormalizer.normalize_doc_id(base, use_hash=False)
        return f"{sanitized_base}{ext.lower()}"