#!/usr/bin/env python3
"""
RepoMaster Unified Launcher

This file is the main startup entry point for RepoMaster, supporting multiple running modes:
1. frontend: Frontend Streamlit interface mode
2. backend: Backend service mode
   - deepsearch: Deep search mode
   - general_assistant: General programming assistant mode  
   - repository_agent: Repository task processing mode

Usage:
    python launcher.py --mode frontend
    python launcher.py --mode backend --backend-mode deepsearch
    python launcher.py --mode backend --backend-mode general_assistant
    python launcher.py --mode backend --backend-mode repository_agent
    python launcher.py --help  # View all options
"""

import os
import sys
import logging
import asyncio
import subprocess
from pathlib import Path


from configs.mode_config import ModeConfigManager, create_argument_parser, print_config_info
from src.frontend.terminal_show import (
    print_repomaster_cli, print_startup_banner, print_environment_status, 
    print_api_config_status, print_launch_config, print_service_starting,
    print_unified_mode_welcome, print_mode_welcome, print_progressive_startup_panel, print_repomaster_title
)

def setup_logging(log_level: str):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Reduce warning messages from third-party libraries
    if log_level.upper() != 'DEBUG':
        logging.getLogger('autogen.oai.client').setLevel(logging.ERROR)
        logging.getLogger('langchain_community.utils.user_agent').setLevel(logging.ERROR)

def setup_environment():
    """Setup environment variables"""
    # Setup PYTHONPATH
    current_dir = Path(__file__).parent.absolute()
    python_path = os.environ.get('PYTHONPATH', '')
    if str(current_dir) not in python_path:
        os.environ['PYTHONPATH'] = f"{current_dir}:{python_path}" if python_path else str(current_dir)
    
    # Load environment variables
    from dotenv import load_dotenv
    env_files = [
        current_dir / "configs" / ".env",
    ]
    
    env_loaded = False
    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            if not os.environ.get('SERPER_API_KEY'):
                print("⚠️  SERPER_API_KEY not found, please check .env file")
                return False
            if not os.environ.get('JINA_API_KEY'):
                print("⚠️  JINA_API_KEY not found, please check .env file")
                return False
            # Will be displayed later with beautiful formatting
            env_loaded = True
            break
    
    if not env_loaded:
        print("⚠️  .env file not found, will use system environment variables")
        
    return env_loaded

def run_frontend_mode(config_manager: ModeConfigManager):
    """Run frontend mode"""
    config = config_manager.config
    
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "src/frontend/app_autogen_enhanced.py",
        "--server.port", str(config.streamlit_port),
        "--server.address", config.streamlit_host,
        "--server.fileWatcherType", config.file_watcher_type
    ]
    
    print(f"\n🌐 Access URL: http://{config.streamlit_host}:{config.streamlit_port}")
    print(f"⚡ Execute command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Frontend service stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Frontend startup failed: {e}")
        sys.exit(1)

def run_backend_mode(config_manager: ModeConfigManager):
    """Run backend mode"""
    config = config_manager.config
    
    if config.backend_mode == "deepsearch":
        run_deepsearch_mode(config_manager)
    elif config.backend_mode == "general_assistant":
        run_general_assistant_mode(config_manager)
    elif config.backend_mode == "repository_agent":
        run_repository_agent_mode(config_manager)
    elif config.backend_mode == "unified":
        run_unified_mode(config_manager)
    else:
        raise ValueError(f"Unsupported backend mode: {config.backend_mode}")

def run_deepsearch_mode(config_manager: ModeConfigManager):
    """Run deep search mode"""
    
    # Import deep search agent and conversation manager
    from src.services.agents.deep_search_agent import AutogenDeepSearchAgent
    from src.core.conversation_manager import ConversationManager, get_user_id_for_cli
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create deep search agent
    agent = AutogenDeepSearchAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Create conversation manager
    user_id = get_user_id_for_cli()
    conversation = ConversationManager(user_id, "deepsearch")
    
    # Display beautiful welcome message
    features = [
        "🔍 Advanced search & query optimization",
        "🌐 Real-time web information retrieval"
    ]
    
    instructions = [
        "• Enter search question or research topic",
        "• Enter 'quit' to exit, 'history'/'clear' to view/clear chat history"
    ]
    
    print_mode_welcome("Deep Search Engine Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            query = input("\n🤔 Please enter search question: ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if query.lower() in ['history', 'h']:
                conversation.show_history()
                continue
                
            if query.lower() in ['clear', 'c']:
                conversation.clear_conversation()
                continue
            
            if not query:
                continue
            
            # Get optimized prompt with conversation context
            optimized_query = conversation.get_optimized_prompt(query)
            conversation.add_message("user", query)
            
            print("🔍 Searching...")
            result = asyncio.run(agent.deep_search(optimized_query))
            conversation.add_message("assistant", result)
            print(f"\n📋 Search results:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 Deep search service stopped")

def run_general_assistant_mode(config_manager: ModeConfigManager):
    """Run general programming assistant mode"""
    
    # Import RepoMaster agent and conversation manager
    from src.core.agent_scheduler import RepoMasterAgent
    from src.core.conversation_manager import ConversationManager, get_user_id_for_cli
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Create conversation manager
    user_id = get_user_id_for_cli()
    conversation = ConversationManager(user_id, "general_assistant")
    
    # Display beautiful welcome message
    features = [
        "💻 General purpose programming assistance",
        "🔧 Code writing, debugging and optimization",
        "📚 Algorithm implementation & debugging help"
    ]
    
    instructions = [
        "• Describe programming task or ask questions",
        "• Enter 'quit' to exit, 'history'/'clear' to view/clear chat history"
    ]
    
    print_mode_welcome("Programming Assistant Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            task = input("\n💻 Please describe your programming task: ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                break
            
            if task.lower() in ['history', 'h']:
                conversation.show_history()
                continue
                
            if task.lower() in ['clear', 'c']:
                conversation.clear_conversation()
                continue
            
            if not task:
                continue
            
            # Get optimized prompt with conversation context
            optimized_task = conversation.get_optimized_prompt(task)
            conversation.add_message("user", task)
            
            print("🔧 Processing...")
            # Call run_general_code_assistant
            result = agent.run_general_code_assistant(
                task_description=optimized_task,
                work_directory=execution_config.get("work_dir")
            )
            conversation.add_message("assistant", result)
            print_repomaster_title()
            print(f"\n📋 Task result:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 General programming assistant service stopped")

def run_repository_agent_mode(config_manager: ModeConfigManager):
    """Run repository task mode"""
    
    # Import RepoMaster agent and conversation manager
    from src.core.agent_scheduler import RepoMasterAgent
    from src.core.conversation_manager import ConversationManager, get_user_id_for_cli
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Create conversation manager
    user_id = get_user_id_for_cli()
    conversation = ConversationManager(user_id, "repository_agent")
    
    # Display beautiful welcome message
    features = [
        "📁 Repository analysis & structure modeling",
        "🔧 Autonomous code exploration and execution"
    ]
    
    instructions = [
        "• Provide task description and repository (GitHub URL or local path)",
        "• Optional: add input data files | Enter 'quit' to exit, 'history' to view chat history, 'clear' to clear history"
    ]
    
    print_mode_welcome("Repository Agent Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            task_description = input("\n📝 Please describe your task: ").strip()
            if task_description.lower() in ['quit', 'exit', 'q']:
                break
            
            if task_description.lower() in ['history', 'h']:
                conversation.show_history()
                continue
                
            if task_description.lower() in ['clear', 'c']:
                conversation.clear_conversation()
                continue
            
            if not task_description:
                continue
            
            repository = input("📁 Please enter repository path or URL: ").strip()
            if not repository:
                print("❌ Repository path cannot be empty")
                continue
            
            # Optional: input data
            use_input_data = input("🗂️  Do you need to provide input data files? (y/N): ").strip().lower()
            input_data = None
            
            if use_input_data in ['y', 'yes']:
                input_path = input("📂 Please enter data file path: ").strip()
                if input_path and os.path.exists(input_path):
                    input_data = f'[{{"path": "{input_path}", "description": "User provided input data"}}]'
                else:
                    print("⚠️  Input path invalid, will ignore input data")
            
            # Get optimized prompt with conversation context
            optimized_task = conversation.get_optimized_prompt(task_description)
            conversation.add_message("user", f"Task: {task_description}\nRepository: {repository}")
            
            print("🔧 Processing repository task...")
            
            # Call run_repository_agent
            result = agent.run_repository_agent(
                task_description=optimized_task,
                repository=repository,
                input_data=input_data
            )
            conversation.add_message("assistant", result)
            print_repomaster_title()
            print(f"\n📋 Task result:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 Repository task service stopped")

def run_unified_mode(config_manager: ModeConfigManager):
    """Run unified general mode"""
    
    # Import RepoMaster agent and conversation manager
    from src.core.agent_scheduler import RepoMasterAgent
    from src.core.conversation_manager import ConversationManager, get_user_id_for_cli
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Create conversation manager
    user_id = get_user_id_for_cli()
    conversation = ConversationManager(user_id, "unified")
    
    # Display beautiful welcome message (unified mode specific)
    print_unified_mode_welcome(execution_config['work_dir'])
    
    try:
        while True:
            print("\n" + "-"*50)
            task = input("🤖 Please describe your task: ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                break
            
            if task.lower() in ['history', 'h']:
                conversation.show_history()
                continue
                
            if task.lower() in ['clear', 'c']:
                conversation.clear_conversation()
                continue
            
            if not task:
                continue
            
            # Get optimized prompt with conversation context
            optimized_task = conversation.get_optimized_prompt(task)
            conversation.add_message("user", task)
            
            print("🔧 Intelligent task analysis...")
            print("   📊 Selecting optimal processing method...")
            
            # Use solve_task_with_repo method, it will automatically select the optimal mode
            try:
                result = agent.solve_task_with_repo(optimized_task)
                conversation.add_message("assistant", result)
                print_repomaster_title()
                print("\n📋 Task execution result:")
                print(result)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                print(f"\n❌ Task execution error: {str(e)}")
                print("   💡 Please try to describe your task requirements in more detail")
            
    except KeyboardInterrupt:
        print("\n👋 Unified general assistant service stopped")

def check_api_configuration() -> bool:
    """Check API configuration status"""
    try:
        from configs.oai_config import validate_and_get_fallback_config
        config_name, api_config = validate_and_get_fallback_config()
        return True
            
    except ImportError:
        print("⚠️  oai_config not found, skip configuration check")
        return False
    except Exception as e:
        print(f"⚠️  Configuration check error: {e}")
        return False

def show_available_modes():
    """Display available running modes"""
    print("""
🚀 RepoMaster Available Running Modes:

1. frontend (Frontend Mode)
   - Launch Streamlit Web interface
   - Support interactive chat and file management
   - Command: python launcher.py --mode frontend

2. backend (Backend Mode)
   - unified: Unified General Mode ⭐ Recommended
     python launcher.py --mode backend --backend-mode unified
     Contains all features: deep search, programming assistant, repository processing, intelligent switching
     
   - deepsearch: Deep Search Mode
     python launcher.py --mode backend --backend-mode deepsearch
     
   - general_assistant: General Programming Assistant Mode
     python launcher.py --mode backend --backend-mode general_assistant
     
   - repository_agent: Repository Task Processing Mode
     python launcher.py --mode backend --backend-mode repository_agent

🔧 Advanced Options:
   --api-type: Specify API type (basic, openai, claude, deepseek, etc.)
   --temperature: Set model temperature (0.0-2.0)
   --work-dir: Specify working directory
   --log-level: Set log level (DEBUG, INFO, WARNING, ERROR)
   --skip-config-check: Skip API configuration check

📖 Get complete help: python launcher.py --help

💡 First time use? Reference: CONFIGURATION_GUIDE.md
""")

def main():
    """Main function"""
    # Print RepoMaster CLI logo first
    # print_repomaster_cli()
    
    # Setup environment
    env_loaded = setup_environment()
    
    # Prepare environment status
    env_status = {
        'success': env_loaded,
        'file': str(Path(__file__).parent / "configs" / ".env") if env_loaded else None
    }
    
    if not env_loaded:
        # Show error and exit
        dummy_config = type('Config', (), {
            'mode': 'error',
            'work_dir': Path(__file__).parent,
            'log_level': 'INFO'
        })()
        api_status = {'success': False}
        print_progressive_startup_panel(env_status, api_status, dummy_config)
        sys.exit(1)
    
    # Check if help or mode information is requested
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['--modes', '--list-modes']):
        show_available_modes()
        return
    
    try:
        # Parse command line arguments
        parser = create_argument_parser()
        args = parser.parse_args()
        
        setup_logging(args.log_level)
        
        # Configuration check (unless user explicitly skips)
        api_status = {'success': False}
        if not getattr(args, 'skip_config_check', False):
            api_config_success = check_api_configuration()
            if api_config_success:
                # Get config info for display
                try:
                    from configs.oai_config import validate_and_get_fallback_config
                    config_info = validate_and_get_fallback_config()
                    if config_info:
                        config_name, config_details = config_info
                        model = config_details.get('config_list', [{}])[0].get('model', 'N/A')
                        api_status = {
                            'success': True,
                            'provider': args.api_type.title(),
                            'model': model
                        }
                except Exception:
                    api_status = {'success': True, 'provider': args.api_type.title()}
            else:
                api_status = {'success': False}
                # Show error panel and exit
                dummy_config = type('Config', (), {
                    'mode': 'error',
                    'work_dir': Path(__file__).parent,
                    'log_level': args.log_level
                })()
                print_progressive_startup_panel(env_status, api_status, dummy_config)
                sys.exit(1)
        else:
            api_status = {'success': True, 'provider': 'Skipped (user choice)'}
        
        # Create configuration manager
        config_manager = ModeConfigManager.from_args(args)
        
        # Print optimized startup sequence  
        print_progressive_startup_panel(env_status, api_status, config_manager.config)
        
        # Start corresponding service based on mode
        if args.mode == 'frontend':
            run_frontend_mode(config_manager)
        elif args.mode == 'backend':
            run_backend_mode(config_manager)
        else:
            raise ValueError(f"Unsupported running mode: {args.mode}")
            
    except KeyboardInterrupt:
        print("\n👋 Program interrupted by user")
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"Startup failed: {e}")
        print(f"❌ Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
