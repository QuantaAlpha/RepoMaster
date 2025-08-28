#!/usr/bin/env python3
"""
Simple Conversation Manager for RepoMaster CLI modes

This module provides context management for command-line interactions,
allowing users to maintain conversation history across multiple inputs.
"""

import os
import json
import joblib
from pathlib import Path
from typing import List, Dict, Optional


class ConversationManager:
    """Simple conversation manager for CLI interactions"""
    
    def __init__(self, user_id: str, mode: str, persistent: bool = False):
        """Initialize conversation manager
        
        Args:
            user_id: User identifier  
            mode: Backend mode (deepsearch, general_assistant, repository_agent, unified)
            persistent: Whether to load/save conversation history across sessions
        """
        self.user_id = user_id
        self.mode = mode
        self.persistent = persistent
        self.messages: List[Dict[str, str]] = []
        self.data_dir = Path("data/cli_conversations")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing conversation only if persistent mode is enabled
        if self.persistent:
            self._load_conversation()
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history
        
        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        if not content.strip():
            return
            
        message = {
            "role": role,
            "content": content.strip()
        }
        self.messages.append(message)
        
        # Auto-save after adding message only if persistent mode is enabled
        if self.persistent:
            self._save_conversation()
    
    def get_optimized_prompt(self, current_input: str) -> str:
        """Get optimized prompt with conversation context
        
        Args:
            current_input: Current user input
            
        Returns:
            Optimized prompt with history context
        """
        # If no history, return current input as-is
        if len(self.messages) <= 1:
            return current_input
        
        # Try to optimize dialogue history
        try:
            optimized_history = self._optimize_dialogue()
            if optimized_history:
                return f"[History Message]:\n{optimized_history}\n[Current User Question]:\n{current_input}\n"
        except Exception as e:
            print(f"⚠️  Warning: Failed to optimize dialogue history: {e}")
        
        # Fallback: return current input
        return current_input
    
    def _optimize_dialogue(self) -> Optional[str]:
        """Optimize dialogue history (simplified version from call_agent.py)"""
        if not self.messages:
            return None
        
        try:
            # Import the optimization function
            from src.utils.tool_optimizer_dialog import optimize_execution
            
            # Convert messages to JSON and optimize
            history_message = json.dumps(self.messages, ensure_ascii=False)
            optimized = optimize_execution(history_message)
            return optimized
        except ImportError:
            # If optimization module not available, use simple truncation
            return self._simple_history_summary()
        except Exception:
            return None
    
    def _simple_history_summary(self) -> str:
        """Simple history summary when optimization is not available"""
        if len(self.messages) <= 2:
            return ""
        
        # Get last few messages for context
        recent_messages = self.messages[-4:]  # Last 4 messages
        summary_parts = []
        
        for msg in recent_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                summary_parts.append(f"{role.title()}: {content}")
        
        return "\n".join(summary_parts)
    
    def _load_conversation(self):
        """Load existing conversation from disk"""
        try:
            file_path = self.data_dir / f"{self.user_id}_{self.mode}_conversation.pkl"
            if file_path.exists():
                self.messages = joblib.load(file_path)
        except Exception as e:
            print(f"⚠️  Warning: Failed to load conversation history: {e}")
            self.messages = []
    
    def _save_conversation(self):
        """Save conversation to disk"""
        try:
            file_path = self.data_dir / f"{self.user_id}_{self.mode}_conversation.pkl"
            joblib.dump(self.messages, file_path)
        except Exception as e:
            print(f"⚠️  Warning: Failed to save conversation history: {e}")
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.messages = []
        # Only save to disk if persistent mode is enabled
        if self.persistent:
            self._save_conversation()
        print("✅ Conversation history cleared")
    
    def show_history(self):
        """Show conversation history summary"""
        if not self.messages:
            print("📝 No conversation history")
            return
        
        print(f"\n📚 Conversation History ({len(self.messages)} messages):")
        print("-" * 50)
        
        for i, msg in enumerate(self.messages[-6:], 1):  # Show last 6 messages
            role = msg.get('role', 'unknown').title()
            content = msg.get('content', '')
            if len(content) > 100:
                content = content[:100] + "..."
            print(f"{i}. {role}: {content}")
        
        if len(self.messages) > 6:
            print(f"... and {len(self.messages) - 6} earlier messages")
        print("-" * 50)


def get_user_id_for_cli() -> str:
    """Get user ID for CLI usage (simplified version)"""
    import uuid
    import tempfile
    
    # Try to get user ID from temp file (persistent across sessions)
    temp_dir = Path(tempfile.gettempdir())
    user_id_file = temp_dir / "repomaster_cli_user_id"
    
    try:
        if user_id_file.exists():
            return user_id_file.read_text().strip()
        else:
            # Generate new user ID
            user_id = str(uuid.uuid4())[:8]  # Short ID
            user_id_file.write_text(user_id)
            return user_id
    except Exception:
        # Fallback to session-based ID
        return f"cli_user_{os.getpid()}"
