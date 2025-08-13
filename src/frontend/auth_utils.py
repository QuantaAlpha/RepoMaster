import streamlit as st
import hashlib
import joblib

DATA_DIR = 'data/'

def load_users():
    try:
        return joblib.load(f'{DATA_DIR}users')
    except FileNotFoundError:
        return {}

def save_users(users):
    joblib.dump(users, f'{DATA_DIR}users')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_user_id(username, password):
    return hashlib.sha256(f"{username}:{password}".encode()).hexdigest()

# Modified: Login interface
def login():
    st.write("# Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Login"):
            users = load_users()
            if username in users and users[username] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_id = generate_user_id(username, password)
                st.session_state.show_login = False
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    with col2:
        if st.button("Go to Register"):
            st.session_state.show_register = True
            st.rerun()
    
    with col3:
        if st.button("Back to Chat"):
            st.session_state.show_login = False
            st.rerun()

# Modified: Registration interface
def register():
    st.write("# Register")
    new_username = st.text_input("New Username", key="register_username")
    new_password = st.text_input("New Password", type="password", key="register_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Create Account"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                users = load_users()
                if new_username in users:
                    st.error("Username already exists")
                else:
                    users[new_username] = hash_password(new_password)
                    save_users(users)
                    st.success("Account created successfully. Please login.")
                    st.session_state.show_register = False
                    st.rerun()
    
    with col2:
        if st.button("Back to Login"):
            st.session_state.show_register = False
            st.rerun()