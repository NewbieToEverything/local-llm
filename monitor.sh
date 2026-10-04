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
    echo "  agentworld-35b    - Qwen-AgentWorld 35B"
    echo "  strata            - Strata / Qwen3.8-Flash-Next（模型由容器内 setup.py 下载，见下方说明）"
    echo ""
    echo "Example:"
    echo "  ./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf"
    echo "  ./monitor.sh gemma4-26BA4B gemma-4-26B-A4B-it-Q4_K_M.gguf"
    exit 1
fi

# Strata 的模型不走 hfd.sh：setup.py 在容器内把约 85GB 下到 strata-data/ 并转换格式，
# 没有单个 GGUF 可盯。这里改为监控数据目录增长 + 容器状态。
if [ "$PROJECT" = "strata" ]; then
    DIR="$SCRIPT_DIR/strata-data"
    CONTAINER=strata
    echo "Strata 的模型由容器内 setup.py 下载（无单个 GGUF），监控数据目录增长..."
    echo "目标目录: $DIR"
    echo "提示: 也可直接看容器日志 ->  ./run.sh strata logs -f"
    echo "---"
    LAST=0
    STABLE=0
    while true; do
        CUR=$(du -sm "$DIR" 2>/dev/null | cut -f1); CUR=${CUR:-0}
        if [ "$CUR" = "$LAST" ]; then
            STABLE=$((STABLE + 1))
        else
            STABLE=0
        fi
        STATE=$(docker inspect -f '{{.State.Status}}{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo "未创建")
        printf "[%s] %s MB  容器: %s\n" "$(date '+%H:%M:%S')" "$CUR" "$STATE"
        LAST=$CUR
        # 连续 2 次无增长且容器在运行，说明下载/转换已结束
        if [ "$STABLE" -ge 2 ] && [ "$STATE" != "未创建" ] && [ "${STATE#*starting}" = "$STATE" ]; then
            echo "[$(date '+%H:%M:%S')] 数据目录已停止增长"
            break
        fi
        sleep 60
    done
    exit 0
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
