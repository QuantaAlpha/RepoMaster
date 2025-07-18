import json
import streamlit as st
import configs.config
import os
from services.agents.deepsearch_2agents import AutogenDeepSearchAgent
from utils.tool_optimizer_dialog import optimize_dialogue, optimize_execution
from utils.tool_streamlit import random_string
from frontend_st.user_memory_manager import UserMemoryManager
from streamlit_extras.colored_header import colored_header

from core.agent_scheduler import RepoMasterAgent

class AgentCaller:
    def __init__(self):
        self.llm_config = configs.config.get_llm_config()
        self.code_execution_config = {
            "work_dir": st.session_state.work_dir
                if 'work_dir' in st.session_state else os.path.join(os.getcwd(), f"coding/{random_string(8)}"),
            "use_docker": False,
        }
        if 1: os.system(f"cp /data/huacan/Code/workspace/RepoMaster/data/DeepResearcher.pdf {self.code_execution_config['work_dir']}")
        
        self.repo_master = RepoMasterAgent(
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
        )
        self.memory_manager = UserMemoryManager()
        
    
    # 优化对话
    def _optimize_dialogue(self, messages):
        if 'messages' in st.session_state:
            if len(messages) > 5:
                history_message = json.dumps(messages, ensure_ascii=False)
                optimize_history_message = optimize_execution(history_message)
                if isinstance(optimize_history_message, list):
                    return optimize_history_message
                else:
                    return messages
        return messages
    
    def preprocess_message(self, prompt):
        if len(st.session_state.messages) <= 1:
            st.session_state.messages.append({"role": "user", "content": prompt})
            return prompt

        optimize_history_message = self._optimize_dialogue(st.session_state.messages)

        # Add user message to chat history
        st.session_state.messages = optimize_history_message + [{"role": "user", "content": prompt}]

        out_prompt = ""
        if len(optimize_history_message) > 0:
            out_prompt += f"[History Message]:\n{json.dumps(optimize_history_message, ensure_ascii=False)}\n"
        out_prompt += f"[Current User Question]:\n{prompt}\n"
        return out_prompt
    
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

    def create_chat_completion(self, messages, user_id, chat_id, file_paths=None, active_user_memory=False):
        # print(f"Prompt: {prompt}")
        # print(f"Messages1: {type(st.session_state.messages)} | {st.session_state.messages}")
        if 'messages' in st.session_state:
            messages = self.preprocess_message(messages)
        # print(f"Messages2: {type(messages)} | {messages}")
        
        origin_question = messages

        # 处理文件路径信息
        if file_paths:
            file_info = "\n".join([f"- {path}" for path in file_paths])
            messages = f"{messages}\n\n[upload files]:\n{file_info}"
        
        if active_user_memory:
            messages = self.retrieve_user_memory(user_id, messages)

        ai_response = self.repo_master.solve_task_with_repo(messages)
        
        if isinstance(ai_response, tuple):
            ai_response, chat_history = ai_response
                
        from services.agents.agent_client import EnhancedMessageProcessor
            
        if hasattr(st.session_state, 'messages'):
            # 保存到基础消息
            EnhancedMessageProcessor.add_message_to_session(
                st=st,
                role="assistant",
                content=ai_response,
                check_duplicate=True
            )
        if hasattr(st.session_state, 'display_messages'):
            # 保存到显示消息
            EnhancedMessageProcessor.add_display_message_to_session(
                st=st,
                message_content=ai_response,
                sender_name="Digital Ray Researcher",
                receiver_name="User",
                sender_role="assistant",
                llm_config={},
                check_duplicate=True,
            )       

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