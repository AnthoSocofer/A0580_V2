import streamlit as st
from pathlib import Path
from dsrag.llm import OpenAIChatAPI, AnthropicChatAPI, LLM

class LLMSelector:
    LLM_CONFIGS = {
        "OpenAI": {
            "class": OpenAIChatAPI,
            "models": [
                {
                    "id": "gpt-4-0125-preview",
                    "name": "GPT-4 Turbo Preview",
                    "description": "Version la plus récente et performante"
                },
                {
                    "id": "gpt-4-turbo-preview",
                    "name": "GPT-4 Turbo",
                    "description": "Excellent rapport performance/coût"
                },
                {
                    "id": "gpt-4",
                    "name": "GPT-4",
                    "description": "Modèle stable et fiable"
                },
                {
                    "id": "gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                    "description": "Rapide et économique"
                }
            ],
            "default_model": "gpt-4-turbo-preview",
            "default_temp": 0.2,
            "default_max_tokens": 1000,
            "color": "#74AA9C"
        },
        "Anthropic": {
            "class": AnthropicChatAPI,
            "models": [
                {
                    "id": "claude-3-opus-20240229",
                    "name": "Claude 3 Opus",
                    "description": "Le plus performant des modèles Claude"
                },
                {
                    "id": "claude-3-sonnet-20240229",
                    "name": "Claude 3 Sonnet",
                    "description": "Bon compromis performance/rapidité"
                },
                {
                    "id": "claude-3-haiku-20240307",
                    "name": "Claude 3 Haiku",
                    "description": "Version rapide et économique"
                }
            ],
            "default_model": "claude-3-sonnet-20240229",
            "default_temp": 0.2,
            "default_max_tokens": 1000,
            "color": "#000000"
        }
    }

    def __init__(self):
        # Initialisation des états de session
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = "OpenAI"
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = self.LLM_CONFIGS["OpenAI"]["default_model"]
        if 'llm_temperature' not in st.session_state:
            st.session_state.llm_temperature = self.LLM_CONFIGS["OpenAI"]["default_temp"]
        if 'llm_max_tokens' not in st.session_state:
            st.session_state.llm_max_tokens = self.LLM_CONFIGS["OpenAI"]["default_max_tokens"]

    def _render_provider_selection(self):
        """Affiche les boutons de sélection du provider"""
        st.write("#### Sélection du provider")
        cols = st.columns(len(self.LLM_CONFIGS))
        
        for idx, (provider, config) in enumerate(self.LLM_CONFIGS.items()):
            with cols[idx]:
                selected = st.session_state.llm_provider == provider
                if st.button(
                    provider,
                    key=f"provider_{provider}",
                    type="primary" if selected else "secondary",
                    use_container_width=True
                ):
                    st.session_state.llm_provider = provider
                    st.session_state.llm_model = config["default_model"]
                    st.rerun()

    def _render_model_selection(self):
        """Affiche les cartes de sélection des modèles"""
        current_config = self.LLM_CONFIGS[st.session_state.llm_provider]
        st.write("#### Sélection du modèle")
        
        for model in current_config["models"]:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"**{model['name']}**")
                st.write(model['description'])
            with col2:
                selected = st.session_state.llm_model == model["id"]
                if st.button(
                    "Sélectionner" if not selected else "✓",
                    key=f"model_{model['id']}",
                    type="primary" if selected else "secondary",
                ):
                    st.session_state.llm_model = model["id"]
                    st.rerun()
            st.write("---")

    def render(self) -> LLM:
        st.markdown("### 🤖 Configuration du modèle")
        
        # Sélection du provider
        self._render_provider_selection()
        st.write("---")
        
        # Sélection du modèle
        self._render_model_selection()

        # Configuration avancée
        with st.expander("⚙️ Configuration avancée"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.llm_temperature = st.slider(
                    "Température",
                    0.0, 1.0, 
                    st.session_state.llm_temperature,
                    0.1,
                    help="Contrôle la créativité des réponses"
                )
            with col2:
                st.session_state.llm_max_tokens = st.number_input(
                    "Tokens Maximum",
                    100, 4000,
                    st.session_state.llm_max_tokens,
                    100
                )

        # Création de l'instance LLM
        current_config = self.LLM_CONFIGS[st.session_state.llm_provider]
        llm_class = current_config["class"]
        return llm_class(
            model=st.session_state.llm_model,
            temperature=st.session_state.llm_temperature,
            max_tokens=st.session_state.llm_max_tokens
        )