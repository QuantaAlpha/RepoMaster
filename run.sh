#!/bin/bash

# RepoMaster Unified Launch Script
# 
# Usage:
#   ./run.sh                          # Default startup frontend mode
#   ./run.sh frontend                 # Start frontend mode
#   ./run.sh backend unified          # Start unified backend mode (recommended)
#   ./run.sh backend deepsearch       # Start deep search mode
#   ./run.sh backend general_assistant # Start general programming assistant mode
#   ./run.sh backend repository_agent # Start repository task mode
#   ./run.sh daemon                   # Start frontend service in background
#   ./run.sh status                   # Check service status
#   ./run.sh stop                     # Stop all services
#   ./run.sh restart                  # Restart services
#   ./run.sh help                     # Show help information

# Set environment variables
export PYTHONPATH=$(pwd):$PYTHONPATH

# Create log directory
mkdir -p logs

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Help function
show_help() {
    echo -e "${CYAN}🚀 RepoMaster Launch Script${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run.sh [mode] [backend mode]"
    echo ""
    echo -e "${YELLOW}Available modes:${NC}"
    echo -e "  ${GREEN}frontend${NC}                 - Start Streamlit frontend interface (default)"
    echo -e "  ${GREEN}backend unified${NC}          - Unified backend mode ⭐ Recommended"
    echo -e "  ${GREEN}backend deepsearch${NC}       - Deep search mode"
    echo -e "  ${GREEN}backend general_assistant${NC} - General programming assistant mode"
    echo -e "  ${GREEN}backend repository_agent${NC} - Repository task processing mode"
    echo ""
    echo -e "${YELLOW}Service management:${NC}"
    echo -e "  ${GREEN}daemon${NC}                   - Start frontend service in background"
    echo -e "  ${GREEN}status${NC}                   - Check service status"
    echo -e "  ${GREEN}stop${NC}                     - Stop all services"
    echo -e "  ${GREEN}restart${NC}                  - Restart services"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./run.sh                          # Start frontend interface"
    echo "  ./run.sh backend unified          # Start unified backend mode"
    echo "  ./run.sh daemon                   # Start frontend in background"
    echo ""
    echo -e "${YELLOW}Advanced usage:${NC}"
    echo "  python launcher.py --help        # View all parameter options"
}

# Check process status
check_status() {
    echo -e "${CYAN}📊 Service Status Check${NC}"
    echo ""
    
    # Check Streamlit process
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${GREEN}✅ Streamlit frontend service is running${NC}"
        echo "   PID: $(pgrep -f 'streamlit run')"
        echo "   Port: 8501"
        echo "   Access: http://localhost:8501"
    else
        echo -e "${RED}❌ Streamlit frontend service is not running${NC}"
    fi
    
    # Check Python backend process
    if pgrep -f "launcher.py.*backend" > /dev/null; then
        echo -e "${GREEN}✅ Backend service is running${NC}"
        echo "   PID: $(pgrep -f 'launcher.py.*backend')"
    else
        echo -e "${RED}❌ Backend service is not running${NC}"
    fi
    
    echo ""
}

# Stop all services
stop_services() {
    echo -e "${YELLOW}🛑 Stopping all RepoMaster services...${NC}"
    
    # Stop Streamlit
    if pgrep -f "streamlit run" > /dev/null; then
        pkill -f "streamlit run"
        echo -e "${GREEN}✅ Stopped Streamlit service${NC}"
    fi
    
    # Stop backend Python process
    if pgrep -f "launcher.py.*backend" > /dev/null; then
        pkill -f "launcher.py.*backend"
        echo -e "${GREEN}✅ Stopped backend service${NC}"
    fi
    
    echo -e "${GREEN}🏁 All services have been stopped${NC}"
}

# Restart services
restart_services() {
    echo -e "${YELLOW}🔄 Restarting RepoMaster services...${NC}"
    stop_services
    sleep 2
    echo -e "${CYAN}Starting frontend service...${NC}"
    start_frontend_daemon
}

# Start frontend service (daemon mode)
start_frontend_daemon() {
    echo -e "${CYAN}🌐 Starting Streamlit frontend service (background mode)...${NC}"
    
    # Check if already running
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${YELLOW}⚠️  Streamlit service is already running${NC}"
        return
    fi
    
    nohup python launcher.py --mode frontend > logs/streamlit.log 2>&1 &
    
    # Wait for service to start
    sleep 3
    
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${GREEN}✅ Streamlit service started successfully${NC}"
        echo -e "${GREEN}   Access URL: http://localhost:8501${NC}"
        echo -e "${GREEN}   Log file: logs/streamlit.log${NC}"
    else
        echo -e "${RED}❌ Streamlit service failed to start${NC}"
        echo -e "${YELLOW}   Please check log: logs/streamlit.log${NC}"
    fi
}

# Start frontend service (interactive mode)
start_frontend() {
    echo -e "${CYAN}🌐 Starting Streamlit frontend interface...${NC}"
    python launcher.py --mode frontend
}

# Start backend service
start_backend() {
    local backend_mode=$1
    
    if [ -z "$backend_mode" ]; then
        backend_mode="unified"
    fi
    
    echo -e "${CYAN}🔧 Starting backend service - ${backend_mode} mode...${NC}"
    python launcher.py --mode backend --backend-mode "$backend_mode"
}

# Main logic
case "$1" in
    "help"|"-h"|"--help")
        show_help
        ;;
    "status")
        check_status
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "daemon")
        start_frontend_daemon
        ;;
    "frontend")
        start_frontend
        ;;
    "backend"|"")
        start_backend "$2"
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac