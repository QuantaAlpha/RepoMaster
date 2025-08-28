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
    print_unified_mode_welcome, print_mode_welcome
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
    
    print_service_starting("Frontend Web Interface", "Streamlit-based web interface for interactive usage")
    
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "src/frontend/app_autogen_enhanced.py",
        "--server.port", str(config.streamlit_port),
        "--server.address", config.streamlit_host,
        "--server.fileWatcherType", config.file_watcher_type
    ]
    
    print(f"   Access URL: http://{config.streamlit_host}:{config.streamlit_port}")
    print(f"   Execute command: {' '.join(cmd)}")
    
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
    
    # Display service starting message
    mode_descriptions = {
        'unified': 'Integrated AI assistant with all RepoMaster features',
        'deepsearch': 'Advanced search engine for deep information retrieval',
        'general_assistant': 'General purpose programming and coding assistant',
        'repository_agent': 'Specialized agent for GitHub and local repository tasks'
    }
    
    service_name = f"{config.backend_mode.title()} Mode"
    description = mode_descriptions.get(config.backend_mode, f"{config.backend_mode} backend service")
    print_service_starting(service_name, description)
    
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
    
    # Import deep search agent
    from src.services.agents.deep_search_agent import AutogenDeepSearchAgent
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create deep search agent
    agent = AutogenDeepSearchAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Display beautiful welcome message
    features = [
        "🔍 Advanced search algorithms based on task descriptions",
        "🔄 Multi-round query optimization",
        "📊 Automated repository relevance analysis",
        "🌐 Real-time web information retrieval"
    ]
    
    instructions = [
        "• Enter your search question or research topic",
        "• System will perform comprehensive information gathering",
        "• Enter 'quit', 'exit' or 'q' to exit"
    ]
    
    print_mode_welcome("Deep Search Engine Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            print_repomaster_cli()
            query = input("\n🤔 Please enter search question: ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            print("🔍 Searching...")
            result = asyncio.run(agent.deep_search(query))
            print(f"\n📋 Search results:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 Deep search service stopped")

def run_general_assistant_mode(config_manager: ModeConfigManager):
    """Run general programming assistant mode"""
    
    # Import RepoMaster agent
    from src.core.agent_scheduler import RepoMasterAgent
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Display beautiful welcome message
    features = [
        "💻 General purpose programming assistance",
        "🔧 Code writing, debugging and optimization",
        "📚 Algorithm implementation and explanation",
        "🛠️ Development tools and best practices guidance"
    ]
    
    instructions = [
        "• Describe your programming task or question",
        "• Ask for code examples, debugging help, or explanations",
        "• Enter 'quit', 'exit' or 'q' to exit"
    ]
    
    print_mode_welcome("Programming Assistant Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            print_repomaster_cli()
            task = input("\n💻 Please describe your programming task: ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                break
            
            if not task:
                continue
            
            print("🔧 Processing...")
            # Call run_general_code_assistant
            result = agent.run_general_code_assistant(
                task_description=task,
                work_directory=execution_config.get("work_dir")
            )
            print(f"\n📋 Task result:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 General programming assistant service stopped")

def run_repository_agent_mode(config_manager: ModeConfigManager):
    """Run repository task mode"""
    
    # Import RepoMaster agent
    from src.core.agent_scheduler import RepoMasterAgent
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Display beautiful welcome message
    features = [
        "📁 GitHub and local repository analysis",
        "🔍 Hierarchical repository structure modeling",
        "🏗️ Core component identification and mapping",
        "🔧 Autonomous code exploration and execution",
        "📊 Intelligent context initialization and selection"
    ]
    
    instructions = [
        "• Provide task description and repository path/URL",
        "• GitHub: https://github.com/user/repo",
        "• Local: /path/to/repo",
        "• Optional: input data files for processing",
        "• Enter 'quit', 'exit' or 'q' to exit"
    ]
    
    print_mode_welcome("Repository Agent Ready!", execution_config['work_dir'], features, instructions)
    
    try:
        while True:
            print_repomaster_cli()
            print("\n" + "="*50)
            task_description = input("📝 Please describe your task: ").strip()
            if task_description.lower() in ['quit', 'exit', 'q']:
                break
            
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
            
            print("🔧 Processing repository task...")
            
            # Call run_repository_agent
            result = agent.run_repository_agent(
                task_description=task_description,
                repository=repository,
                input_data=input_data
            )
            print(f"\n📋 Task result:\n{result}\n")
            
    except KeyboardInterrupt:
        print("\n👋 Repository task service stopped")

def run_unified_mode(config_manager: ModeConfigManager):
    """Run unified general mode"""
    
    # Import RepoMaster agent
    from src.core.agent_scheduler import RepoMasterAgent
    
    # Get configuration
    llm_config = config_manager.get_llm_config(config_manager.config.api_type)
    execution_config = config_manager.get_execution_config()
    
    # Create RepoMaster agent
    agent = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=execution_config
    )
    
    # Display beautiful welcome message
    print_unified_mode_welcome(execution_config['work_dir'])
    
    try:
        while True:
            print_repomaster_cli()
            print("\n" + "-"*50)
            task = input("🤖 Please describe your task: ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                break
            
            if not task:
                continue
            
            print("🔧 Intelligent task analysis...")
            print("   📊 Selecting optimal processing method...")
            
            # Use solve_task_with_repo method, it will automatically select the optimal mode
            try:
                result = agent.solve_task_with_repo(task)
                print("\n" + "="*50)
                print("📋 Task execution result:")
                print("="*50)
                print(result)
                print("="*50)
                
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
    # Print startup banner
    print_startup_banner()
    
    # Setup environment
    env_loaded = setup_environment()
    
    # Display environment status
    if env_loaded:
        env_file_path = str(Path(__file__).parent / "configs" / ".env")
        print_environment_status(env_file_path, True)
    else:
        print_environment_status(None, False)
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
        if not getattr(args, 'skip_config_check', False):
            api_config_success = check_api_configuration()
            if api_config_success:
                # Get config info for display
                try:
                    from configs.oai_config import validate_and_get_fallback_config
                    config_name, api_config = validate_and_get_fallback_config()
                    print_api_config_status(config_name, True, api_config)
                except Exception:
                    print_api_config_status(args.api_type, True, None)
            else:
                print_api_config_status(None, False, None)
                sys.exit(1)
        else:
            print("⚠️  Skip API configuration check (user choice)")
        
        # Create configuration manager
        config_manager = ModeConfigManager.from_args(args)
        
        # Print configuration information (using beautiful format)
        print_launch_config(config_manager.config)
        
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
