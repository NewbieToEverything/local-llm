#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$1"
MODEL="$2"

if [ -z "$PROJECT" ] || [ -z "$MODEL" ]; then
    echo "Usage: ./monitor.sh <project-name> <model-filename>"
    echo ""
    echo "Available projects:"
    echo "  gpt-oss-20b       - GPT-OSS 20B"
    echo "  gpt-oss-120b      - GPT-OSS 120B"
    echo "  qwen35-35BA3B     - Qwen3.5 35B"
    echo "  qwen36-35BA3B     - Qwen3.6 35B"
    echo "  gemma4-26BA4B     - Gemma4 26B"
    echo ""
    echo "Example:"
    echo "  ./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf"
    echo "  ./monitor.sh gemma4-26BA4B gemma-4-26B-A4B-it-Q4_K_M.gguf"
    exit 1
fi

TARGET_DIR="$SCRIPT_DIR/llama-$PROJECT/models"
TARGET_FILE="$TARGET_DIR/$MODEL"

echo "开始监控下载进度..."
echo "目标目录: $TARGET_DIR"
echo "目标文件: $MODEL"
echo "---"

while true; do
    if [ -f "$TARGET_FILE" ]; then
        CURRENT_SIZE=$(stat -c%s "$TARGET_FILE" 2>/dev/null)
        CURRENT_MB=$(echo "scale=1; $CURRENT_SIZE / 1024 / 1024" | bc)
        CURRENT_GB=$(echo "scale=1; $CURRENT_SIZE / 1024 / 1024 / 1024" | bc)
        echo "[$(date '+%H:%M:%S')] ${CURRENT_MB}MB (${CURRENT_GB}GB)"

        # 检查是否连续2次文件大小不变（下载完成）
        if [ "$LAST_SIZE" = "$CURRENT_SIZE" ]; then
            WAIT_COUNT=$((WAIT_COUNT + 1))
            if [ "$WAIT_COUNT" -ge 2 ]; then
                echo "[$(date '+%H:%M:%S')] 下载完成!"
                break
            fi
        else
            WAIT_COUNT=0
        fi
        LAST_SIZE=$CURRENT_SIZE
    else
        TEMP_FILES=$(find "$TARGET_DIR" -name "*.incomplete" 2>/dev/null | wc -l)
        echo "[$(date '+%H:%M:%S')] 等待下载开始... (临时文件: $TEMP_FILES)"
        WAIT_COUNT=0
    fi
    sleep 60
done
