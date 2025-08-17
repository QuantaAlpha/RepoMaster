import os
import time
import uuid
import random
import joblib
import streamlit as st
import hashlib
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, List
from auth_utils import login, register, generate_user_id
from src.utils.tool_streamlit import AppContext

# Constants
DATA_DIR = 'data/'
ENV_FILE = "../configs/.env"
PAST_CHATS_FILE = 'data/past_chats_list'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = '✨'
MODEL_NAME = "gpt-3.5-turbo"

# Configuration management
def load_config() -> Dict[str, str]:
    load_dotenv(ENV_FILE)
    return {
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
    }

# Data management
def initialize_data_directory():
    os.makedirs(DATA_DIR, exist_ok=True)

# Added: generate or get user ID
def get_user_id():
    if st.session_state.get('logged_in'):
        return st.session_state.user_id
    else:
        if 'guest_user_id' not in st.session_state:
            st.session_state.guest_user_id = str(uuid.uuid4())
        return st.session_state.guest_user_id

def load_past_chats(user_id: str) -> Dict[str, str]:
    try:
        return joblib.load(f'{DATA_DIR}{user_id}_past_chats')
    except FileNotFoundError:
        return {}

def save_past_chats(user_id: str, past_chats: Dict[str, str]):
    joblib.dump(past_chats, f'{DATA_DIR}{user_id}_past_chats')

def load_chat_messages(user_id: str, chat_id: str) -> List[Dict[str, str]]:
    try:
        return joblib.load(f'{DATA_DIR}{user_id}_{chat_id}_messages')
    except FileNotFoundError:
        return []

def save_chat_messages(user_id: str, chat_id: str, messages: List[Dict[str, str]]):
    joblib.dump(messages, f'{DATA_DIR}{user_id}_{chat_id}_messages')

# UI components
def setup_sidebar(user_id: str, past_chats: Dict[str, str]) -> str:
    with st.sidebar:
        st.write('# Chat Sessions')
        
        # Custom CSS for buttons
        st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: transparent;
            color: #4F8BF9;
            border: none;
            text-align: left;
            padding: 5px 10px;
            margin: 2px 0px;
            border-radius: 5px;
        }
        .stButton>button:hover {
            background-color: #E6F0FF;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Initialize chat_id if it doesn't exist
        if "chat_id" not in st.session_state:
            st.session_state.chat_id = f'{time.time()}'
         
        new_chat_id = None

        # Add "New Chat" button
        if st.button("➕ New Chat", key="new_chat_button"):
            new_chat_id = f'{time.time()}'
            st.session_state.chat_id = new_chat_id
            st.session_state.chat_title = f'ChatSession-{new_chat_id}'
            st.session_state.messages = []  # Clear messages for new chat
            past_chats[new_chat_id] = st.session_state.chat_title
            save_past_chats(user_id, past_chats)

        st.write('---')  # Add a separator
        st.write('## Chats History')
        
        def get_last_user_question(chat_id):
            messages = load_chat_messages(user_id, chat_id)
            for message in reversed(messages):
                if message['role'] == 'user':
                    content = message['content'][:50] + '...' if len(message['content']) > 50 else message['content']
                    return content + f'-{chat_id}'
            return past_chats.get(chat_id, f'ChatSession-{chat_id}')

        # Display chat history as buttons
        for chat_id in reversed(list(past_chats.keys())):
            if load_chat_messages(user_id, chat_id):
                button_label = get_last_user_question(chat_id)
                # Truncate and pad the label to ensure fixed length
                truncated_label = button_label[:30].ljust(30)
                if st.button(truncated_label, key=f"chat_button_{chat_id}"):
                    st.session_state.chat_id = chat_id
                    st.session_state.chat_title = past_chats.get(chat_id, f'ChatSession-{chat_id}')
                    st.session_state.messages = load_chat_messages(user_id, chat_id)
                    st.rerun()

    return st.session_state.chat_id

def display_chat_history(messages: List[Dict[str, str]]):
    for message in messages:
        with st.chat_message(name=message['role'], avatar=AI_AVATAR_ICON if message['role'] == MODEL_ROLE else None):
            st.markdown(message['content'])

# OpenAI interaction
def get_ai_response(client: OpenAI, messages: List[Dict[str, str]], prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages + [{"role": "user", "content": prompt}],
        stream=True,
    )
    
    with st.chat_message(name=MODEL_ROLE, avatar=AI_AVATAR_ICON):
        message_placeholder = st.empty()
        full_response = ''
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content
                time.sleep(0.05)
                message_placeholder.write(full_response + '▌')
        message_placeholder.write(full_response)
    
    return full_response

# Added: simulate web search function
def search_web(query):
    # This is just a simulation function, should be replaced with real search logic in actual application
    results = [
        f"Search result 1 for '{query}'",
        f"Search result 2 for '{query}'",
        f"Search result 3 for '{query}'",
    ]
    return random.sample(results, k=min(len(results), 2))

def expand_web_search(prompt):
    with st.expander("Web Search Module", expanded=False):
        results = search_web(prompt)
        for result in results:
            st.write(result)

# Modified: chat interface
def chat_interface():
    # Get user_id
    user_id = get_user_id()

    # Set work directory and streamlit
    AppContext.set_work_dir(work_dir)
    AppContext.set_streamlit(st)    

    # Initialize configuration and data
    config = load_config()
    initialize_data_directory()
    past_chats = load_past_chats(user_id)

    # Setup OpenAI client
    client = OpenAI(api_key=config['OPENAI_API_KEY'])

    # Setup UI
    st.write('# Chat with OpenAI')
    chat_id = setup_sidebar(user_id, past_chats)

    # If chat_id is empty, create a new chat
    if not chat_id:
        chat_id = f'{time.time()}'
        st.session_state.chat_id = chat_id
        st.session_state.chat_title = f'ChatSession-{chat_id}'
        st.session_state.messages = []
        past_chats[chat_id] = st.session_state.chat_title
        save_past_chats(user_id, past_chats)

    if 'messages' not in st.session_state:
        st.session_state.messages = load_chat_messages(user_id, chat_id)

    # Display chat history
    display_chat_history(st.session_state.messages)

    # Handle user input
    if prompt := st.chat_input('Your message here...'):
        # Display user message
        with st.chat_message('user'):
            st.markdown(prompt)

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Add web search module to the top of chat interface
        expand_web_search(prompt)

        # Get and display AI response
        ai_response = get_ai_response(client, st.session_state.messages, prompt)

        # Add AI response to chat history
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

        # Save updated chat messages
        save_chat_messages(user_id, chat_id, st.session_state.messages)

    # Add logout button
    if st.session_state.logged_in:
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
    else:
        if st.sidebar.button("Login"):
            st.session_state.show_login = True
            st.rerun()

# Modified: main application logic
def main():
    st.set_page_config(page_title="Chat with OpenAI", page_icon="✨")

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if 'show_register' not in st.session_state:
        st.session_state.show_register = False

    if 'show_login' not in st.session_state:
        st.session_state.show_login = False

    if st.session_state.show_login:
        if st.session_state.show_register:
            register()
        else:
            login()
    else:
        chat_interface()

if __name__ == "__main__":
    main()