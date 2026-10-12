#!/usr/bin/with-contenv bashio
set -e

export BUDGET_BOOK_HOST="0.0.0.0"
export BUDGET_BOOK_PORT="8099"
export BUDGET_BOOK_DATA="/data/budget_book.json"
export BUDGET_BOOK_LOG_LEVEL="info"
if [ -f /data/options.json ]; then
  export BUDGET_BOOK_LOG_LEVEL="$(bashio::config 'log_level')"
fi

mkdir -p /data

bashio::log.info "Starting Budget Book add-on on port ${BUDGET_BOOK_PORT}"
exec python3 /app/server.py
