#!/bin/bash
set -e

export HOST_UID=$(id -u)
export HOST_GID=$(id -g)

PROJECT="$1"
shift

if [ -z "$PROJECT" ]; then
    echo "Usage: ./run.sh <project-name> [docker-compose-args]"
    echo ""
    echo "Available projects:"
    echo "  gpt-oss-20b       - GPT-OSS 20B (port 8082, llama.cpp)"
    echo "  gpt-oss-120b      - GPT-OSS 120B (port 8081, llama.cpp)"
    echo "  qwen35-35BA3B     - Qwen3.5 35B (port 8083, llama.cpp)"
    echo "  qwen36-35BA3B     - Qwen3.6 35B (port 8084, llama.cpp)"
    echo "  gemma4-26BA4B     - Gemma4 26B (port 8085, llama.cpp)"
    echo "  gemma4-12b        - Gemma4 12B (port 8086, llama.cpp)"
    echo "  agentworld-35b    - Qwen-AgentWorld 35B (port 8088, llama.cpp)"
    echo ""
    echo "Example:"
    echo "  ./run.sh gpt-oss-20b up -d"
    echo "  ./run.sh gemma4-26BA4B down"
    exit 1
fi

BASE_DIR="$(dirname "$0")"
if [ -d "$BASE_DIR/$PROJECT" ]; then
    cd "$BASE_DIR/$PROJECT"
else
    cd "$BASE_DIR/llama-$PROJECT"
fi

echo "Running llama-$PROJECT with UID=$HOST_UID GID=$HOST_GID"

docker compose "$@"