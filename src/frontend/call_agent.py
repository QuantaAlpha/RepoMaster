import json
import streamlit as st
from configs.oai_config import get_llm_config
import os
from configs.oai_config import get_llm_config
from src.services.agents.deep_search_agent import AutogenDeepSearchAgent
from src.services.agents.agent_client import EnhancedMessageProcessor
from src.utils.tool_optimizer_dialog import optimize_dialogue, optimize_execution
from src.utils.tool_streamlit import random_string
from streamlit_extras.colored_header import colored_header

from src.core.agent_scheduler import RepoMasterAgent

class AgentCaller:
    def __init__(self):
        self.llm_config = get_llm_config()
        self.code_execution_config = {
            "work_dir": st.session_state.work_dir
                if 'work_dir' in st.session_state else os.path.join(os.getcwd(), f"coding/{random_string(8)}"),
            "use_docker": False,
        }
        
        self.repo_master = RepoMasterAgent(
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
        )
    
    # Optimize dialogue
    def _optimize_dialogue(self, messages):
        if 'messages' in st.session_state:
            history_message = json.dumps(messages, ensure_ascii=False)
            optimize_history_message = optimize_execution(history_message)
            if optimize_history_message is None:
                return None
            return optimize_history_message
        return None
    
    def preprocess_message(self, prompt):
        if len(st.session_state.messages) <= 1:
            st.session_state.messages.append({"role": "user", "content": prompt})
            return prompt

        try:
            optimize_history_message = self._optimize_dialogue(st.session_state.messages)
        except Exception as e:
            print(f"Error optimizing dialogue: {str(e)}")
            optimize_history_message = ''
        if optimize_history_message:
            out_prompt = f"[History Message]:\n{optimize_history_message}\n[Current User Question]:\n{prompt}\n"
            st.session_state.messages = [{"role": "user", "content": out_prompt}]
            return out_prompt
        else:
            return prompt
    
    def postprocess_message(self, ai_response):
        # Add AI response to chat history
        if ai_response == "":
            ai_response = "TERMINATE"
        # st.session_state.messages.append({"role": "assistant", "content": ai_response})        
        return ai_response
    
    def retrieve_user_memory(self, user_id, query):
        return self.memory_manager.retrieve_user_memory(user_id, query)
    
    def store_experience(self, user_id, query):

        if 'messages' in st.session_state:
            messages = st.session_state.messages
            self.memory_manager.store_experience(user_id, query, messages)
    
    def store_user_memory(self, user_id, query, answer):
        return self.memory_manager.store_user_memory(user_id, query, answer)
    
    def save_chat_query_and_answer(self, content, role, sender_name, receiver_name, sender_role):

        EnhancedMessageProcessor.add_message_to_session(
            st=st,
            role=role,
            content=content,
            check_duplicate=True
        )

        EnhancedMessageProcessor.add_display_message_to_session(
            st=st,
            message_content=content,
            sender_name=sender_name,
            receiver_name=receiver_name,
            sender_role=sender_role,
            llm_config={},
            check_duplicate=True,
        )          

    def create_chat_completion(self, messages, user_id, chat_id, file_paths=None, active_user_memory=False):
        self.save_chat_query_and_answer(messages, "user", "User", "Researcher", "user")

        origin_question = messages

        if 'messages' in st.session_state:
            messages = self.preprocess_message(messages)        
                
        # Process file path information
        if file_paths:
            file_info = "\n".join([f"- {path}" for path in file_paths])
            messages = f"{messages}\n\n[upload files]:\n{file_info}"
        
        if active_user_memory:
            from src.frontend.user_memory_manager import UserMemoryManager
            self.memory_manager = UserMemoryManager()
            
            messages = self.retrieve_user_memory(user_id, messages)

        ai_response = self.repo_master.solve_task_with_repo(messages)
        
        if isinstance(ai_response, tuple):
            ai_response, chat_history = ai_response
        
        self.save_chat_query_and_answer(ai_response, "assistant", "Researcher", "User", "assistant")
                            
        if active_user_memory:
            # self.store_user_memory(user_id, origin_question, ai_response)
            self.store_experience(user_id, origin_question)               
        
        ai_response = self.postprocess_message(ai_response)
        return ai_response

def main():
    agent_caller = AgentCaller()
    message = "Hello, how can I help you today?"
    response = agent_caller.create_chat_completion(message)
    print(f"Message: {message}")
    print(f"Response: {response}")

if __name__ == "__main__":
    main()
