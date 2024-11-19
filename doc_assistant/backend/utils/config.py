"""
Configuration utilities

Created: 2024-10-30
"""
# backend/utils/config.py
import os
import sys
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

class ConfigurationError(Exception):
    pass

class ConfigManager:
    REQUIRED_ENV_VARS = {
        'OPENAI_API_KEY': 'OpenAI API key is required',
        'ANTHROPIC_API_KEY': 'Anthropic API key is required',
        'CO_API_KEY': 'Cohere API key is required',
    }
    
    @classmethod
    def validate_environment(cls) -> Dict[str, str]:
        """Vérifie que toutes les variables d'environnement requises sont définies"""
        missing_vars = []
        env_vars = {}
        
        # Charger les variables d'environnement
        env_path = Path.cwd() / '.env'
        load_dotenv(env_path)
        
        for var, message in cls.REQUIRED_ENV_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_vars.append(f"{message} ({var})")
            else:
                env_vars[var] = value
                
        if missing_vars:
            error_message = "\n".join(missing_vars)
            raise ConfigurationError(
                f"Configuration incomplète. Variables manquantes:\n{error_message}\n"
                "Veuillez créer un fichier .env avec les variables requises."
            )
            
        return env_vars

    @classmethod
    def setup_environment(cls) -> None:
        """Configure l'environnement pour l'application"""
        try:
            env_vars = cls.validate_environment()
            
            # Configurer les clés API pour les différents services
            os.environ.update(env_vars)
            
        except ConfigurationError as e:
            print(f"Erreur de configuration:\n{str(e)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Erreur inattendue lors de la configuration:\n{str(e)}", file=sys.stderr)
            sys.exit(1)

