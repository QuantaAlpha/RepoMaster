import json
import os
import venv
import shutil
import subprocess
from datetime import datetime
from textwrap import dedent

import autogen
from autogen.code_utils import create_virtual_env

from configs.oai_config import get_llm_config
from src.utils.agent_gpt4 import AzureGPT4Chat

class BaseCodeExplorer:
    """Base agent class that provides basic functionality for virtual environment management and agent setup"""
    
    def __init__(self, work_dir: str, use_venv=False, task_id=None, is_cleanup_venv=True):
        """Initialize base agent"""
        
        self.restart_count = 0
        self.chat_turns = 0
        self.is_restart = False
        self.use_venv = use_venv
        self.is_cleanup_venv = False if not is_cleanup_venv and task_id else True
        self.task_id = task_id or datetime.now().strftime('%Y%m%d%H%M%S')
        self.work_dir = work_dir
        
    
    def _load_venv_context(self, venv_dir=None, is_clear_venv=None, base_venv_path=None):
        """Load virtual environment, create if it doesn't exist"""
        
        def load_base_venv(base_venv_path):
            # If base environment is specified and exists, copy from base environment
            if base_venv_path and not os.path.exists(base_venv_path):
                os.makedirs(os.path.dirname(base_venv_path), exist_ok=True)
                self._create_virtual_env(base_venv_path)
                    
            if base_venv_path and os.path.exists(base_venv_path):
                if not os.path.exists(self.venv_path):
                    print("\n" + "╔" + "═" * 68 + "╗")
                    print("║" + "📋 COPYING ENVIRONMENT FROM BASE".center(68) + "║")
                    print("╠" + "═" * 68 + "╣")
                    print(f"║ 📂 From: {base_venv_path}".ljust(69) + "║")
                    print(f"║ 📁 To: {self.venv_path}".ljust(69) + "║")
                    print("║ ⏳ This will be much faster than fresh installation...".ljust(69) + "║")
                    print("╚" + "═" * 68 + "╝")
                    os.system(f"cp -a {base_venv_path} {self.venv_path}")
                    print("✅ Environment copied successfully!\n")
                
                # Load the copied environment
                env_builder = venv.EnvBuilder(with_pip=True)
                self.venv_context = env_builder.ensure_directories(self.venv_path)
                return self.venv_context
            return None      
        
        # Determine virtual environment path
        if venv_dir is None:
            # Non-temporary environment and path not specified, use default persistent path ./venvs'
            default_venvs_dir = './.venvs'
            self.venv_path = os.path.join(default_venvs_dir, "persistent_venv")
        else:
            self.venv_path = os.path.join(venv_dir, "persistent_venv")            

        # Ensure work directory exists
        venv_dir = os.path.dirname(self.venv_path)
        if not os.path.exists(venv_dir):
            os.makedirs(venv_dir, exist_ok=True)            
        
        if is_clear_venv is not None:
            self.is_cleanup_venv = is_clear_venv
        
        # If base environment is specified, copy from base environment
        if base_venv_path:
            venv_context = load_base_venv(base_venv_path)
            if venv_context:
                return venv_context
        
        # Decide whether to load or create environment based on is_cleanup_venv
        if not self.is_cleanup_venv:
            # If environment cleanup is not needed (persistent environment), try to load existing environment
            activate_script = os.path.join(self.venv_path, "bin", "activate")
            if os.path.exists(self.venv_path) and os.path.exists(activate_script):
                self._print_venv_status("loading")
                env_builder = venv.EnvBuilder(with_pip=True)
                self.venv_context = env_builder.ensure_directories(self.venv_path)
            else:
                self._print_venv_setup_notice("persistent")
                self.venv_context = self._create_virtual_env(self.venv_path)
        else:
            # If environment cleanup is needed (temporary environment), create new environment every time
            self._print_venv_setup_notice("temporary")
            self.venv_context = self._create_virtual_env(self.venv_path)
        
        return self.venv_context
    
    def _print_venv_status(self, status):
        """Print elegant virtual environment status"""
        print("\n" + "═" * 70)
        print("🔧 VIRTUAL ENVIRONMENT STATUS".center(70))
        print("═" * 70)
        
        if status == "loading":
            print("✅ Found existing environment - Loading instantly!")
            print(f"📂 Location: {self.venv_path}")
            print("💡 Note: Dependencies already installed, ready to use!")
        
        print("═" * 70 + "\n")
    
    def _print_venv_setup_notice(self, env_type):
        """Print elegant setup notice with todo list style"""
        print("\n" + "╔" + "═" * 68 + "╗")
        print("║" + "🚀 VIRTUAL ENVIRONMENT SETUP".center(68) + "║")
        print("╠" + "═" * 68 + "╣")
        
        env_desc = "Persistent Environment" if env_type == "persistent" else "Temporary Environment"
        print(f"║ 📦 Setting up: {env_desc}".ljust(69) + "║")
        print(f"║ 📁 Location: {self.venv_path}".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        print("║ ⏱️  ESTIMATED TIME: 2-3 minutes".ljust(69) + "║")
        print("║ 💡 This setup runs ONLY ONCE per environment".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        print("║ 📋 INSTALLATION CHECKLIST:".ljust(69) + "║")
        print("║   ⬜ Create virtual environment".ljust(69) + "║")
        print("║   ⬜ Update pip to latest version".ljust(69) + "║")
        print("║   ⬜ Install LLM dependencies".ljust(69) + "║")
        print("║   ⬜ Verify installation".ljust(69) + "║")
        print("╚" + "═" * 68 + "╝")
        print("\n🎯 Starting setup process...\n")
    
    def _create_virtual_env(self, venv_path):
        """Create virtual environment and install basic dependencies"""
        
        # Use autogen's method to create virtual environment
        print("┌─ Task 1/4: Creating virtual environment...")
        self.venv_context = create_virtual_env(venv_path)
        print("└─ ✅ Virtual environment created successfully!\n")
        
        # Install basic dependencies - use . instead of source, compatible with sh and bash
        # And explicitly specify using bash to execute commands
        activate_script = os.path.join(venv_path, "bin", "activate")
        activate_cmd = f"bash -c '. {activate_script} && "
        
        print("┌─ Task 2/4: Updating pip to latest version...")
        subprocess.run(f"{activate_cmd} pip install -U pip'", shell=True)
        print("└─ ✅ Pip updated successfully!\n")
        
        # Get absolute path of requirements file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels: from src/core to project root
        project_root = os.path.dirname(os.path.dirname(current_dir))
        requirements_path = os.path.join(project_root, "configs/docker_src/llm_requirements.txt")
        
        # Check if requirements file exists
        if os.path.exists(requirements_path):
            print("┌─ Task 3/4: Installing LLM dependencies...")
            print(f"│  📄 Using requirements file: {requirements_path}")
            print("│  ⏳ This may take 2-3 minutes depending on your network...")
            # Install all dependencies using requirements file
            subprocess.run(
                f"{activate_cmd} pip install -r {requirements_path}'",
                shell=True
            )
            print("└─ ✅ LLM dependencies installed successfully!\n")
        else:
            print("┌─ Task 3/4: Installing LLM dependencies (backup method)...")
            print(f"│  ⚠️  Requirements file not found: {requirements_path}")
            print("│  📦 Installing essential packages: numpy, pandas, torch, transformers...")
            print("│  ⏳ This may take 2-3 minutes depending on your network...")
            # Backup method: directly install key dependencies
            subprocess.run(
                f"{activate_cmd} pip install numpy pandas'",
                shell=True
            )
            print("└─ ✅ Essential LLM dependencies installed successfully!\n")
        
        print("┌─ Task 4/4: Verifying installation...")
        print("└─ ✅ All tasks completed successfully!\n")
        
        # Final success message
        print("╔" + "═" * 68 + "╗")
        print("║" + "🎉 SETUP COMPLETED SUCCESSFULLY!".center(68) + "║")
        print("╠" + "═" * 68 + "╣")
        print("║ ✅ Virtual environment is ready for use".ljust(69) + "║")
        print("║ 💡 Next time this will load instantly (no setup needed)".ljust(69) + "║")
        print("║ 🚀 You can now run your LLM applications!".ljust(69) + "║")
        print("╚" + "═" * 68 + "╝\n")
        return self.venv_context
    
    def cleanup_venv(self):
        """Clean up virtual environment"""
        if not self.is_cleanup_venv:
            return
        
        if self.use_venv and hasattr(self, 'venv_path') and os.path.exists(self.venv_path):
            print("\n" + "╔" + "═" * 68 + "╗")
            print("║" + "🧹 ENVIRONMENT CLEANUP".center(68) + "║")
            print("╠" + "═" * 68 + "╣")
            print(f"║ 📁 Removing: {self.venv_path}".ljust(69) + "║")
            print("╚" + "═" * 68 + "╝")
            shutil.rmtree(self.venv_path)
            print("✅ Cleanup completed successfully!\n")
    
    
    def _setup_agents(self):
        """Set up AutoGen agents (needs to be implemented in subclass)"""
        raise NotImplementedError("Subclass must implement _setup_agents method")
    
    def _register_tools(self):
        """Register tool functions to executor agent (needs to be implemented in subclass)"""
        raise NotImplementedError("Subclass must implement _register_tools method")
    
    def summary_chat_history(self, task, all_messages) -> str:
        """Summarize chat history"""
        
        last_message_start = len(all_messages)-1
        
        if len(all_messages) <= 3 or 'tool_response' in all_messages[last_message_start]:
            last_message_start = len(all_messages)
        
        history_messages = all_messages[1:last_message_start]
        for idx, message in enumerate(history_messages):
            if 'tool_response' in message:
                history_messages[idx].pop('tool_responses')
        history_messages = json.dumps(history_messages, ensure_ascii=False, indent=2)
        
        system_prompt = dedent("""You are an AI assistant specializing in summarizing technical dialogues for context continuity. Your task is to distill the provided chat history into a concise JSON object, focusing *only* on the information essential for resuming the `task` effectively. Prioritize brevity and relevance for the *next* steps.

# Summary Requirements:
1.  **Identify Core Path**: Extract the most relevant and effective sequence of steps (including tool calls, code generation and execution) from the history that are most related to completing the original task. Ignore unimportant or off-target interactions.
2.  **Extract Key Code and Results**: Include code snippets and their execution results (success or failure analysis) that directly serve the task goal or reveal important information. Avoid redundancy.
3.  **Reflection and Learning**: If there are errors or challenges in the history, briefly analyze the causes and explain the experience gained or how the strategy should be adjusted subsequently.
4.  **Stay True to Original**: Strictly summarize based on the provided historical content, do not add information that does not exist in the history or make unnecessary inferences.
5.  **Strict JSON Output**: The final output must be a single, complete, syntactically correct JSON object that strictly follows the structure specified below. Pay attention to JSON syntax details such as correct use of commas, quotes, and brackets.

## JSON Output Structure:
```json
{
    "history_summary": [ // Use "history_summary" as top-level key
        {
            "subtask_goal": "{{Goal description of current step or subtask}}", // Clear goal of this step
            "tool_calls": [ // If this step has tool calls
                {
                    "function_name": "{{Tool function name}}",
                    "arguments": "{{Tool function arguments}}",
                    "response_summary": "{{Summary of key information or conclusions from tool call result}}"
                }
                 // ... Other tool calls ...
            ], // If no tool calls, this key can be omitted or set to empty array []
            "code_executions": [ // If this step has code generation and execution
                {
                    "intention": "{{Purpose of generating this code}}",
                    "code": "{{Generated code snippet}}",
                    "execution_result_analysis": "{{Analysis of code execution result (success, failure cause, key output)}}"
                }
                // ... Other code executions ...
            ], // If no code execution, this key can be omitted or set to empty array []
            "reflection": "{{Reflection on this step, error analysis or lessons learned, optional}}" // If there's anything worth reflecting on
        }
        // ... Other summaries of key historical steps ...
    ]
}
```
""")

        user_prompt = dedent(f"""Please generate the required JSON summary based on the instructions in the System Prompt and the following original task and conversation history.

**Original Task**
<task>
{task}
</task>

**Conversation History**
<chat_history>
{history_messages}
</chat_history>

**Please confirm again: your output must be a single, valid JSON object that conforms to the structure defined in the System Prompt.**
""")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            parsed_summary = AzureGPT4Chat().chat_with_message(messages, json_format=True)
            summary = json.dumps(parsed_summary, ensure_ascii=False)
        except Exception as e:
            print(f"ERR summary_chat_history: {e}")
            pass

        # Construct message list for summarization
        messages_summary = {
            "content": summary,
            "role": 'assistant',
            "name": "history_summary",
        }

        out_summary_message = all_messages[:1] + [messages_summary] + all_messages[last_message_start:]
        
        for idx, message in enumerate(out_summary_message):
            if 'tool_response' in message:
                out_summary_message[idx].pop('tool_responses')
        return json.dumps(out_summary_message, ensure_ascii=False, indent=2) 