import re
import hashlib
import unicodedata
from typing import Optional
import os

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
   
    # 1. Convertir en minuscules et supprimer l'extension
    name = os.path.splitext(filename.lower())[0]
   
    # 2. Normaliser les caractères accentués
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
   
    # 3. Remplacer spécifiquement les apostrophes et guillemets par des underscores
    name = re.sub(r'[\'"]', '_', name)
   
    # 4. Remplacer les autres caractères spéciaux par des tirets
    name = re.sub(r'[^a-z0-9_]+', '-', name)  # Modifié pour préserver les underscores
   
    # 5. Supprimer les tirets et underscores multiples
    name = re.sub(r'[-_]+', '-', name)
   
    # 6. Supprimer les tirets aux extrémités
    name = name.strip('-')
   
    # 7. Limiter la longueur de base pour laisser de la place au hash
    max_base_length = max_length - 9 if use_hash else max_length
    name = name[:max_base_length]
   
    # 8. Ajouter un hash si demandé
    if use_hash:
        hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
        name = f"{name}-{hash_suffix}"
   
    # 9. S'assurer que l'ID commence par une lettre
    if not name[0].isalpha():
        name = f"doc-{name}"
   
    return name

# Tests de validation
def test_normalize_doc_id():
    test_cases = [
        ("B.01.04_PN1424_16_ACT_004307_03_CPE_CC'-SMI.pdf",
         "b-01-04-pn1424-16-act-004307-03-cpe-cc_smi"),
        ("A.02.06_CCAP_Annexe 6_DREX_02_HPH_DRF_000001_1_S-PRINT_Convention d'utilisation.pdf",
         "a-02-06-ccap-annexe-6-drex-02-hph-drf-000001-1-s-print-convention-d_utilisation"),
        ('Test"file\'with"quotes.pdf',
         "test_file_with_quotes"),
        ("A.01.06_AE_Annexe6_Attestation d'assurance.pdf",
         "a-01-06-ae-annexe6-attestation-d_assurance")
    ]

    for input_name, expected_output in test_cases:
        result = normalize_doc_id(input_name, use_hash=False)
        # Vérifier si les apostrophes et guillemets sont remplacés par des underscores
        assert "'" not in result and '"' not in result
        print(f"\nInput: {input_name}")
        print(f"Result: {result}")
        print(f"Expected: {expected_output}")
        print(f"Test passed: {result.startswith(expected_output)}")

if __name__ == "__main__":
    test_normalize_doc_id()