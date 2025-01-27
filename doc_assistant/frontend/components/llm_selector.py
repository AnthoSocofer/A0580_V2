# doc_assistant/frontend/components/llm_selector.py
import streamlit as st
from pathlib import Path
from dsrag.llm import OpenAIChatAPI, AnthropicChatAPI, LLM

class LLMSelector:
    LLM_CONFIGS = {
        "OpenAI": {
            "class": OpenAIChatAPI,
            "color": "#74AA9C",
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
            "default_max_tokens": 1000
        },
        "Anthropic": {
            "class": AnthropicChatAPI,
            "color": "#000000",
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
            "default_max_tokens": 1000
        }
    }

    def __init__(self):
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = "OpenAI"
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = self.LLM_CONFIGS["OpenAI"]["default_model"]
        if 'llm_temperature' not in st.session_state:
            st.session_state.llm_temperature = self.LLM_CONFIGS["OpenAI"]["default_temp"]
        if 'llm_max_tokens' not in st.session_state:
            st.session_state.llm_max_tokens = self.LLM_CONFIGS["OpenAI"]["default_max_tokens"]
        
        # Charger le CSS
        css_path = Path(__file__).parent.parent / "styles" / "llm_selector.css"
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    def render(self) -> LLM:
        # Remplacer les boutons individuels par un selectbox pour le provider
        provider = st.selectbox(
            "Provider",
            options=list(self.LLM_CONFIGS.keys()),
            index=list(self.LLM_CONFIGS.keys()).index(st.session_state.llm_provider)
        )
        
        if provider != st.session_state.llm_provider:
            st.session_state.llm_provider = provider
            st.session_state.llm_model = self.LLM_CONFIGS[provider]["default_model"]
        
        # Utiliser un radio pour les modèles au lieu de boutons
        current_config = self.LLM_CONFIGS[st.session_state.llm_provider]
        model_options = {m["id"]: f"{m['name']} - {m['description']}" 
                        for m in current_config["models"]}
        
        selected_model = st.radio(
            "Modèle",
            options=list(model_options.keys()),
            format_func=lambda x: model_options[x],
            index=list(model_options.keys()).index(st.session_state.llm_model)
        )
        
        if selected_model != st.session_state.llm_model:
            st.session_state.llm_model = selected_model
        # Configuration avancée
        with st.expander("⚙️ Configuration avancée"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.llm_temperature = st.slider(
                    "🌡️ Température",
                    0.0, 1.0,
                    st.session_state.llm_temperature,
                    0.1
                )
            with col2:
                st.session_state.llm_max_tokens = st.number_input(
                    "📝 Tokens Maximum",
                    100, 4000,
                    st.session_state.llm_max_tokens,
                    100
                )

        # Affichage de la configuration active
        selected_model_name = next(
            (m['name'] for m in current_config['models'] if m['id'] == st.session_state.llm_model),
            st.session_state.llm_model
        )

        st.markdown("<div class='config-summary'>", unsafe_allow_html=True)
        st.markdown("### 📊 Configuration actuelle")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
                - **Provider**: {st.session_state.llm_provider}
                - **Modèle**: {selected_model_name}
            """)
        with col2:
            st.markdown(f"""
                - **Température**: {st.session_state.llm_temperature}
                - **Tokens max**: {st.session_state.llm_max_tokens}
            """)
        st.markdown("</div>", unsafe_allow_html=True)

        return current_config["class"](
            model=st.session_state.llm_model,
            temperature=st.session_state.llm_temperature,
            max_tokens=st.session_state.llm_max_tokens
        )