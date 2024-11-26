#doc_assistant/frontend/components/llm_selector.py
from typing import Optional, Dict, Any
import streamlit as st
from dsrag.llm import OpenAIChatAPI, AnthropicChatAPI, LLM

class LLMSelector:
    """Composant pour la sélection du client LLM et du modèle"""
    
    # Configuration des modèles disponibles par client
    LLM_CONFIGS = {
        "OpenAI": {
            "class": OpenAIChatAPI,
            "models": [
                "gpt-4-0125-preview",
                "gpt-4-turbo-preview",
                "gpt-4",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k"
            ],
            "default_model": "gpt-4-turbo-preview",
            "default_temp": 0.2,
            "default_max_tokens": 1000
        },
        "Anthropic": {
            "class": AnthropicChatAPI,
            "models": [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0"
            ],
            "default_model": "claude-3-sonnet-20240229",
            "default_temp": 0.2,
            "default_max_tokens": 1000
        }
    }

    def __init__(self):
        # Initialisation des états de session si nécessaire
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = "OpenAI"
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = self.LLM_CONFIGS["OpenAI"]["default_model"]
        if 'llm_temperature' not in st.session_state:
            st.session_state.llm_temperature = self.LLM_CONFIGS["OpenAI"]["default_temp"]
        if 'llm_max_tokens' not in st.session_state:
            st.session_state.llm_max_tokens = self.LLM_CONFIGS["OpenAI"]["default_max_tokens"]

    def _update_model_defaults(self):
        """Met à jour les paramètres par défaut en fonction du provider"""
        provider = st.session_state.llm_provider
        st.session_state.llm_model = self.LLM_CONFIGS[provider]["default_model"]
        st.session_state.llm_temperature = self.LLM_CONFIGS[provider]["default_temp"]
        st.session_state.llm_max_tokens = self.LLM_CONFIGS[provider]["default_max_tokens"]

    def render(self) -> LLM:
        """
        Affiche l'interface de sélection du LLM et retourne l'instance configurée
        
        Returns:
            LLM: Instance configurée du client LLM sélectionné
        """
        # Sélection du provider avec radio buttons
        provider = st.radio(
            "Sélectionner le fournisseur LLM",
            options=list(self.LLM_CONFIGS.keys()),
            key="llm_provider",
            on_change=self._update_model_defaults,
            horizontal=True
        )

        st.markdown("---")

        # Configuration du modèle
        col1, col2 = st.columns(2)

        with col1:
            model = st.selectbox(
                "Modèle",
                options=self.LLM_CONFIGS[provider]["models"],
                key="llm_model"
            )

            temperature = st.slider(
                "Température",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.llm_temperature,
                step=0.1,
                key="llm_temperature",
                help="Contrôle la créativité des réponses"
            )

        with col2:
            max_tokens = st.number_input(
                "Tokens maximum",
                min_value=100,
                max_value=4000,
                value=st.session_state.llm_max_tokens,
                step=100,
                key="llm_max_tokens",
                help="Limite la longueur des réponses"
            )

            # Affichage du fournisseur et modèle sélectionnés
            st.info(f"Configuration actuelle: {provider} - {model}")

        # Création de l'instance du LLM
        llm_class = self.LLM_CONFIGS[provider]["class"]
        llm = llm_class(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return llm

    def get_current_config(self) -> Dict[str, Any]:
        """Retourne la configuration actuelle du LLM"""
        return {
            "provider": st.session_state.llm_provider,
            "model": st.session_state.llm_model,
            "temperature": st.session_state.llm_temperature,
            "max_tokens": st.session_state.llm_max_tokens
        }