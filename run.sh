#!/usr/bin/env bash
# DuruOn helper launcher
# Usage:
#   ./run.sh                # start with default config.yaml
#   ./run.sh custom.yaml    # start with custom config
#   ./run.sh stop           # graceful stop (sends SIGTERM)
#   ./run.sh status         # show running PID & basic info
#   ./run.sh tail           # tail last 100 lines of latest log (if present)
#
# Notes:
# - Respects existing PID file (duruon.pid) to prevent duplicate instances
# - Writes stdout/stderr to logs/duruon-<timestamp>.log (rotates per start)
# - Does NOT daemonize; use systemd for robust service management

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VENV_DIR="./venv"
PY="$VENV_DIR/bin/python"
PID_FILE="duruon.pid"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

timestamp() { date +"%Y%m%d-%H%M%S"; }

exists_running() {
  if [[ -f $PID_FILE ]]; then
    local p
    p=$(tr -d '\n' < "$PID_FILE" || true)
    if [[ $p =~ ^[0-9]+$ ]] && [[ -d /proc/$p ]]; then
      echo "$p"
      return 0
    fi
  fi
  return 1
}

cmd=${1:-start}
case "$cmd" in
  stop)
    if pid=$(exists_running); then
      echo "Stopping DuruOn (PID $pid)..."
      kill "$pid" || true
      sleep 1
      if [[ -d /proc/$pid ]]; then
        echo "Process still alive; sending SIGKILL" >&2
        kill -9 "$pid" || true
      fi
      rm -f "$PID_FILE"
      echo "Stopped."
    else
      echo "No running instance." >&2
    fi
    exit 0
    ;;
  status)
    if pid=$(exists_running); then
      echo "Running (PID $pid)"
      echo "Uptime: $(ps -o etime= -p $pid | tr -d ' ')"
    else
      echo "Not running"
    fi
    exit 0
    ;;
  tail)
    last_log=$(ls -1t "$LOG_DIR"/duruon-*.log 2>/dev/null | head -n1 || true)
    if [[ -n "$last_log" ]]; then
      echo "Tailing $last_log (Ctrl-C to exit)" >&2
      tail -n 100 -f "$last_log"
    else
      echo "No log files yet." >&2
    fi
    exit 0
    ;;
esac

# Treat first arg not matching control words as config path
if [[ "$cmd" != start ]]; then
  CONFIG="$cmd"
else
  CONFIG="config.yaml"
fi

if [[ ! -x "$PY" ]]; then
  echo "Python venv not found ($PY). Run ./install.sh first." >&2
  exit 1
fi

if pid=$(exists_running); then
  echo "Already running (PID $pid). Use ./run.sh stop first." >&2
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "Config file '$CONFIG' not found." >&2
  exit 1
fi

# Proactive LED reset (clears any stuck LEDs from prior unclean shutdown)
if [[ -x scripts/led_reset.py ]]; then
  # Run quietly; ignore errors if GPIO/library absent
  "$PY" scripts/led_reset.py >/dev/null 2>&1 || true
fi

LOG_FILE="$LOG_DIR/duruon-$(timestamp).log"
echo "Starting DuruOn with $CONFIG → $LOG_FILE"
echo "(Ctrl-C stops foreground; use ./run.sh stop for background run)"

# Foreground execution with tee logging
exec "$PY" -u main_runner.py --config "$CONFIG" 2>&1 | tee -a "$LOG_FILE"
