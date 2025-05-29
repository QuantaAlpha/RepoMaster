import random
import string
import asyncio
from contextvars import ContextVar

# 定义 ContextVar
session_var = ContextVar("session", default=None)

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class AppConfig:
    _instance = None

    def __init__(self):
        self.sessions = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_session(self, user_id):
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'queue': asyncio.Queue(),
                'work_dir': f"coding/{random_string()}",
                'message_history': [],
                'user_id': user_id
            }
        session_var.set(self.sessions[user_id])
        return self.sessions[user_id]

    def get_current_session(self):
        return session_var.get()

    def is_initialized(self):
        return bool(self.sessions)    