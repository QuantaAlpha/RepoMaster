#!/bin/bash

# RepoMaster 统一启动脚本
# 
# 使用方法:
#   ./run.sh                          # 默认启动前端模式
#   ./run.sh frontend                 # 启动前端模式
#   ./run.sh backend unified          # 启动统一后台模式 (推荐)
#   ./run.sh backend deepsearch       # 启动深度搜索模式
#   ./run.sh backend general_assistant # 启动通用编程助手模式
#   ./run.sh backend repository_agent # 启动仓库任务模式
#   ./run.sh daemon                   # 后台启动前端服务
#   ./run.sh status                   # 查看服务状态
#   ./run.sh stop                     # 停止所有服务
#   ./run.sh restart                  # 重启服务
#   ./run.sh help                     # 显示帮助信息

# 设置环境变量
export PYTHONPATH=$(pwd):$PYTHONPATH

# 创建日志目录
mkdir -p logs

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 帮助函数
show_help() {
    echo -e "${CYAN}🚀 RepoMaster 启动脚本${NC}"
    echo ""
    echo -e "${YELLOW}使用方法:${NC}"
    echo "  ./run.sh [模式] [后台模式]"
    echo ""
    echo -e "${YELLOW}可用模式:${NC}"
    echo -e "  ${GREEN}frontend${NC}                 - 启动Streamlit前端界面 (默认)"
    echo -e "  ${GREEN}backend unified${NC}          - 统一后台模式 ⭐ 推荐"
    echo -e "  ${GREEN}backend deepsearch${NC}       - 深度搜索模式"
    echo -e "  ${GREEN}backend general_assistant${NC} - 通用编程助手模式"
    echo -e "  ${GREEN}backend repository_agent${NC} - 仓库任务处理模式"
    echo ""
    echo -e "${YELLOW}服务管理:${NC}"
    echo -e "  ${GREEN}daemon${NC}                   - 后台启动前端服务"
    echo -e "  ${GREEN}status${NC}                   - 查看服务状态"
    echo -e "  ${GREEN}stop${NC}                     - 停止所有服务"
    echo -e "  ${GREEN}restart${NC}                  - 重启服务"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  ./run.sh                          # 启动前端界面"
    echo "  ./run.sh backend unified          # 启动统一后台模式"
    echo "  ./run.sh daemon                   # 后台启动前端"
    echo ""
    echo -e "${YELLOW}高级用法:${NC}"
    echo "  python launcher.py --help        # 查看所有参数选项"
}

# 检查进程状态
check_status() {
    echo -e "${CYAN}📊 服务状态检查${NC}"
    echo ""
    
    # 检查Streamlit进程
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${GREEN}✅ Streamlit前端服务正在运行${NC}"
        echo "   PID: $(pgrep -f 'streamlit run')"
        echo "   端口: 8501"
        echo "   访问: http://localhost:8501"
    else
        echo -e "${RED}❌ Streamlit前端服务未运行${NC}"
    fi
    
    # 检查Python后台进程
    if pgrep -f "launcher.py.*backend" > /dev/null; then
        echo -e "${GREEN}✅ 后台服务正在运行${NC}"
        echo "   PID: $(pgrep -f 'launcher.py.*backend')"
    else
        echo -e "${RED}❌ 后台服务未运行${NC}"
    fi
    
    echo ""
}

# 停止所有服务
stop_services() {
    echo -e "${YELLOW}🛑 停止所有RepoMaster服务...${NC}"
    
    # 停止Streamlit
    if pgrep -f "streamlit run" > /dev/null; then
        pkill -f "streamlit run"
        echo -e "${GREEN}✅ 已停止Streamlit服务${NC}"
    fi
    
    # 停止后台Python进程
    if pgrep -f "launcher.py.*backend" > /dev/null; then
        pkill -f "launcher.py.*backend"
        echo -e "${GREEN}✅ 已停止后台服务${NC}"
    fi
    
    echo -e "${GREEN}🏁 所有服务已停止${NC}"
}

# 重启服务
restart_services() {
    echo -e "${YELLOW}🔄 重启RepoMaster服务...${NC}"
    stop_services
    sleep 2
    echo -e "${CYAN}启动前端服务...${NC}"
    start_frontend_daemon
}

# 启动前端服务 (daemon模式)
start_frontend_daemon() {
    echo -e "${CYAN}🌐 启动Streamlit前端服务 (后台模式)...${NC}"
    
    # 检查是否已经运行
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${YELLOW}⚠️  Streamlit服务已在运行${NC}"
        return
    fi
    
    nohup python launcher.py --mode frontend > logs/streamlit.log 2>&1 &
    
    # 等待服务启动
    sleep 3
    
    if pgrep -f "streamlit run" > /dev/null; then
        echo -e "${GREEN}✅ Streamlit服务启动成功${NC}"
        echo -e "${GREEN}   访问地址: http://localhost:8501${NC}"
        echo -e "${GREEN}   日志文件: logs/streamlit.log${NC}"
    else
        echo -e "${RED}❌ Streamlit服务启动失败${NC}"
        echo -e "${YELLOW}   请查看日志: logs/streamlit.log${NC}"
    fi
}

# 启动前端服务 (交互模式)
start_frontend() {
    echo -e "${CYAN}🌐 启动Streamlit前端界面...${NC}"
    python launcher.py --mode frontend
}

# 启动后台服务
start_backend() {
    local backend_mode=$1
    
    if [ -z "$backend_mode" ]; then
        backend_mode="unified"
    fi
    
    echo -e "${CYAN}🔧 启动后台服务 - ${backend_mode}模式...${NC}"
    python launcher.py --mode backend --backend-mode "$backend_mode"
}

# 主逻辑
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
    "frontend"|"")
        start_frontend
        ;;
    "backend")
        start_backend "$2"
        ;;
    *)
        echo -e "${RED}❌ 未知模式: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac