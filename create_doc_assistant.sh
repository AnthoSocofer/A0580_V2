#!/bin/bash

# Nom du projet
PROJECT_NAME="doc_assistant"

# Couleurs pour le terminal
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Fonction pour créer un fichier Python avec un header basique
create_py_file() {
    local file=$1
    local description=$2
    echo "\"\"\"
$description

Created: $(date '+%Y-%m-%d')
\"\"\"

" > "$file"
}

# Fonction pour créer un fichier Markdown
create_md_file() {
    local file=$1
    local title=$2
    echo "# $title

## Description

## Installation

## Usage
" > "$file"
}

echo -e "${GREEN}Création de la structure du projet ${PROJECT_NAME}...${NC}"

# Création du répertoire principal
mkdir -p $PROJECT_NAME

# Création de la structure
cd $PROJECT_NAME

# Frontend
mkdir -p frontend/components
mkdir -p frontend/pages
mkdir -p frontend/styles

# Backend
mkdir -p backend/kb_management
mkdir -p backend/agents
mkdir -p backend/core
mkdir -p backend/utils

# Data
mkdir -p data/knowledge_bases
mkdir -p data/conversations
mkdir -p data/cache

# Tests
mkdir -p tests/frontend
mkdir -p tests/backend
mkdir -p tests/integration

# Création des fichiers Frontend
create_py_file "frontend/__init__.py" "Frontend package initialization"
create_py_file "frontend/components/__init__.py" "UI Components initialization"
create_py_file "frontend/components/chat_window.py" "Chat interface component"
create_py_file "frontend/components/kb_sidebar.py" "Knowledge base sidebar component"
create_py_file "frontend/components/document_viewer.py" "Document viewer component"
create_py_file "frontend/components/search_bar.py" "Search bar component"
create_py_file "frontend/components/settings_panel.py" "Settings panel component"

create_py_file "frontend/pages/__init__.py" "Pages initialization"
create_py_file "frontend/pages/chat_page.py" "Main chat page"
create_py_file "frontend/pages/kb_management.py" "Knowledge base management page"
create_py_file "frontend/pages/settings_page.py" "Settings page"

create_py_file "frontend/styles/theme.py" "UI theme and constants"
create_py_file "frontend/styles/components.py" "Component styles"

# Création des fichiers Backend
create_py_file "backend/__init__.py" "Backend package initialization"

create_py_file "backend/kb_management/__init__.py" "Knowledge base management initialization"
create_py_file "backend/kb_management/manager.py" "Knowledge base manager main class"
create_py_file "backend/kb_management/document_processor.py" "Document processing utilities"
create_py_file "backend/kb_management/metadata_handler.py" "Metadata management utilities"

create_py_file "backend/agents/__init__.py" "Agents package initialization"
create_py_file "backend/agents/chat_agent.py" "Main chat agent implementation"
create_py_file "backend/agents/search_agent.py" "Search agent implementation"
create_py_file "backend/agents/kb_agent.py" "Knowledge base agent implementation"
create_py_file "backend/agents/agent_factory.py" "Agent factory implementation"

create_py_file "backend/core/__init__.py" "Core package initialization"
create_py_file "backend/core/conversation.py" "Conversation management"
create_py_file "backend/core/context.py" "Context management"
create_py_file "backend/core/memory.py" "Conversation memory management"

create_py_file "backend/utils/__init__.py" "Utilities package initialization"
create_py_file "backend/utils/config.py" "Configuration utilities"
create_py_file "backend/utils/logger.py" "Logging utilities"
create_py_file "backend/utils/exceptions.py" "Custom exceptions"

# Création des fichiers de test
create_py_file "tests/__init__.py" "Tests package initialization"
create_py_file "tests/frontend/test_components.py" "UI components tests"
create_py_file "tests/backend/test_kb_manager.py" "Knowledge base manager tests"
create_py_file "tests/backend/test_agents.py" "Agents tests"
create_py_file "tests/integration/test_end_to_end.py" "End-to-end integration tests"

# Création des fichiers racine
create_py_file "main.py" "Application entry point"
create_md_file "README.md" "Document Assistant Application"

# Création du fichier requirements.txt avec les dépendances de base
echo "# Core dependencies
streamlit
dsrag
chromadb
openai
anthropic
cohere
voyageai
numpy
pandas

# UI dependencies
streamlit-chat

# Testing
pytest
pytest-asyncio

# Development
black
flake8
mypy" > requirements.txt

# Création du fichier .env avec des variables d'exemple
echo "# API Keys
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
COHERE_API_KEY=your-key-here
VOYAGE_API_KEY=your-key-here

# Application settings
DEBUG=True
LOG_LEVEL=INFO
STORAGE_PATH=./data" > .env

# Création du fichier .gitignore
echo "# Python
__pycache__/
*.py[cod]
*$py.class
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.venv
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Data
data/
*.db
*.sqlite3

# Logs
*.log
logs/
" > .gitignore

echo -e "${GREEN}Structure du projet créée avec succès!${NC}"
echo -e "${GREEN}Pour commencer:${NC}"
echo "1. cd $PROJECT_NAME"
echo "2. python -m venv venv"
echo "3. source venv/bin/activate  # Sur Windows: venv\\Scripts\\activate"
echo "4. pip install -r requirements.txt"
echo "5. Configurez le fichier .env avec vos clés API"