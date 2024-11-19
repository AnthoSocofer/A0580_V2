"""
Main chat agent implementation

Created: 2024-10-30

backend/agents/chat_agent.py
"""
# backend/agents/chat_agent.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class Message:
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatAgent:
    def __init__(self, llm_service: Any):
        self.llm = llm_service
        self.conversation_history: List[Message] = []

    async def format_response(self, content: str, metadata: Dict[str, Any]) -> Message:
        """Formate une réponse avec métadonnées"""
        message = Message(
            role="assistant",
            content=content,
            metadata=metadata
        )
        self.conversation_history.append(message)
        return message

    def get_conversation_context(self, window_size: int = 5) -> str:
        """Récupère le contexte récent de la conversation"""
        recent_messages = self.conversation_history[-window_size:] if self.conversation_history else []
        return "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in recent_messages
        ])