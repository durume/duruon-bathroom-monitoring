#!/bin/bash

# DuruOn Monitoring Script
# This script provides real-time monitoring and health checks for DuruOn

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 DuruOn Monitor v1.1${NC}"
echo "================================"

function show_status() {
    echo -e "\n${BLUE}📊 Service Status:${NC}"
    systemctl status bathguard --no-pager -l || echo -e "${RED}❌ Service not running${NC}"
}

function show_logs() {
    echo -e "\n${BLUE}📝 Recent Logs (last 20 lines):${NC}"
    journalctl -u bathguard -n 20 --no-pager -o short-iso
}

function show_live_logs() {
    echo -e "\n${BLUE}📺 Live Log Stream (Press Ctrl+C to exit):${NC}"
    journalctl -u bathguard -f --no-pager -o short-iso
}

function show_pose_monitor() {
    echo -e "\n${BLUE}🚿 Starting Real-time Pose Monitor...${NC}"
    python3 /opt/bathguard/pose_monitor.py
}

function health_check() {
    echo -e "\n${BLUE}🏥 Health Check:${NC}"
    
    # Check if service is active
    if systemctl is-active --quiet bathguard; then
        echo -e "  ✅ Service: ${GREEN}Active${NC}"
    else
        echo -e "  ❌ Service: ${RED}Inactive${NC}"
    fi
    
    # Check if camera device exists
    if [ -c /dev/video0 ]; then
        echo -e "  ✅ Camera: ${GREEN}Device available${NC}"
    else
        echo -e "  ❌ Camera: ${RED}Device not found${NC}"
    fi
    
    # Check if process is using camera
    if sudo lsof /dev/video* 2>/dev/null | grep -q bathguard; then
        echo -e "  ✅ Camera Use: ${GREEN}DuruOn has camera access${NC}"
    else
        echo -e "  ⚠️  Camera Use: ${YELLOW}Camera not in use by DuruOn${NC}"
    fi
    
    # Check config file
    if [ -f /opt/bathguard/config.yaml ]; then
        echo -e "  ✅ Config: ${GREEN}Found${NC}"
    else
        echo -e "  ❌ Config: ${RED}Missing${NC}"
    fi
    
    # Check .env file
    if [ -f /opt/bathguard/.env ]; then
        echo -e "  ✅ Environment: ${GREEN}Found${NC}"
    else
        echo -e "  ❌ Environment: ${RED}Missing .env file${NC}"
    fi
    
    # Check model file
    if [ -f /opt/bathguard/models/movenet_singlepose_lightning.tflite ]; then
        echo -e "  ✅ AI Model: ${GREEN}Found${NC}"
    else
        echo -e "  ❌ AI Model: ${RED}Missing${NC}"
    fi
    
    # Check recent activity
    recent_logs=$(journalctl -u bathguard --since="5 minutes ago" --no-pager -q 2>/dev/null | wc -l)
    if [ "$recent_logs" -gt 0 ]; then
        echo -e "  ✅ Activity: ${GREEN}Active (${recent_logs} log entries in last 5 min)${NC}"
    else
        echo -e "  ⚠️  Activity: ${YELLOW}No recent logs${NC}"
    fi
}

function show_performance() {
    echo -e "\n${BLUE}🚀 Performance:${NC}"
    
    # Get process info
    if pid=$(systemctl show --property MainPID --value bathguard 2>/dev/null) && [ "$pid" != "0" ]; then
        echo -e "  PID: $pid"
        
        # CPU and Memory usage
        if ps_info=$(ps -p "$pid" -o %cpu,%mem,etime,rss --no-headers 2>/dev/null); then
            echo -e "  CPU: $(echo $ps_info | awk '{print $1}')%"
            echo -e "  Memory: $(echo $ps_info | awk '{print $2}')% ($(echo $ps_info | awk '{printf "%.1f", $4/1024}')MB)"
            echo -e "  Uptime: $(echo $ps_info | awk '{print $3}')"
        fi
    else
        echo -e "  ${RED}Process not running${NC}"
    fi
}

function show_help() {
    echo -e "\n${BLUE}Available commands:${NC}"
    echo "  status    - Show service status"
    echo "  logs      - Show recent logs"
    echo "  live      - Show live log stream"
    echo "  pose      - Real-time pose detection monitor"
    echo "  health    - Run health check"
    echo "  perf      - Show performance metrics"
    echo "  restart   - Restart the service"
    echo "  stop      - Stop the service"
    echo "  start     - Start the service"
    echo "  help      - Show this help"
    echo ""
}

case "${1:-help}" in
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "live")
        show_live_logs
        ;;
    "pose")
        show_pose_monitor
        ;;
    "health")
        health_check
        ;;
    "perf")
        show_performance
        ;;
    "restart")
        echo -e "${YELLOW}🔄 Restarting DuruOn...${NC}"
        sudo systemctl restart bathguard
        sleep 2
        show_status
        ;;
    "stop")
        echo -e "${YELLOW}🛑 Stopping DuruOn...${NC}"
        sudo systemctl stop bathguard
        show_status
        ;;
    "start")
        echo -e "${GREEN}🚀 Starting DuruOn...${NC}"
        sudo systemctl start bathguard
        sleep 2
        show_status
        ;;
    "help"|*)
        show_help
        ;;
esac