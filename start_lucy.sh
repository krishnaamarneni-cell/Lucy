#!/usr/bin/env bash
LUCY_DIR="$HOME/Lucy"
PID_FILE="$LUCY_DIR/lucy.pid"
LOG_FILE="$LUCY_DIR/lucy.log"
PYTHON_BIN="$LUCY_DIR/venv/bin/python"
ENTRY="$LUCY_DIR/main.py"

cd "$LUCY_DIR" || { echo "Lucy dir not found"; exit 1; }

# Ensure audio sink is awake and unmuted (WSLg quirk)
pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null
pactl set-sink-volume @DEFAULT_SINK@ 80% 2>/dev/null

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
  if is_running; then
    echo "Lucy already running (PID $(cat "$PID_FILE"))."
    return 0
  fi
  nohup setsid "$PYTHON_BIN" -u "$ENTRY" >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 1
  if is_running; then
    echo "Lucy started (PID $(cat "$PID_FILE")). Logs: $LOG_FILE"
  else
    echo "Lucy failed to start. Check $LOG_FILE"
    rm -f "$PID_FILE"
    return 1
  fi
}

stop() {
  if ! is_running; then
    echo "Lucy not running."
    rm -f "$PID_FILE"
    return 0
  fi
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null
  for _ in {1..10}; do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.3
  done
  kill -9 "$PID" 2>/dev/null
  rm -f "$PID_FILE"
  echo "Lucy stopped."
}

status() {
  if is_running; then
    echo "Lucy is running (PID $(cat "$PID_FILE"))."
  else
    echo "Lucy is not running."
  fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  logs)    tail -f "$LOG_FILE" ;;
  *)       echo "Usage: $0 {start|stop|restart|status|logs}"; exit 1 ;;
esac
