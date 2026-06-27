# Local LLM Deployment

本地部署的开源 LLM 服务，基于 llama.cpp + Docker。

## 硬件环境

本目录下部署的所有开源 LLMs 已经在 NVIDIA RTX 5070 Ti (16GB VRAM) 上测试成功，理论上在更大显存的显卡上会有更好的表现。

## 可用模型及表现

下表中的速度和延迟均指在 NVIDIA RTX 5070 Ti (16GB VRAM) 上的表现。

| 指标 | GPT-OSS-20B | GPT-OSS-120B | Qwen3.5-35BA3B | Qwen3.6-35BA3B | Gemma4-26BA4B | Gemma4-26BA4B (QAT) | Gemma4-12B | Qwen-AgentWorld-35B-A3B |
|------|-------------|--------------|---------------|---------------|---------------|---------------------|------------|------------------------|
| API生成速度 (medium) | 154 tok/s | 12.62 tok/s | 57.77 tok/s | 57.03 tok/s | 44.06 tok/s | **52.6 tok/s** | 91.2 tok/s | 62.2 tok/s |
| 首Token延迟 | 48 ms | 726 ms | 73 ms | 80 ms | 160 ms | **76 ms** | 365 ms | 46 ms |
| Prefill 速度 (4K prompt) | **8198 tok/s** | **672 tok/s** | **1612 tok/s** | **1634 tok/s** | **2101 tok/s** | **2645 tok/s** | **3058 tok/s** | 1747 tok/s |
| 量化格式 | Q4_K_M | MXFP4 | Q4_K_M | Q4_K_M | Q4_K_M | UD-Q4_K_XL (QAT) | Q4_K_M | Q4_K_M |
| 发布日期 | 2025-08-05 | 2025-08-05 | 2026-02-24 | 2026-04-16 | 2026-04-02 | 2026-06-09 | 2026-06-03 | 2026-06-24 |
| 参数量 | 21B (3.6B活跃) | 117B (5.1B活跃) | 35B (3B活跃) | 35B (3B活跃) | 26B (3.8B活跃) | 26B (3.8B活跃) | 12B (dense) | 35B (3B活跃) |
| 模型架构 | MoE Transformer | MoE Transformer | Hybrid Gated DeltaNet + MoE | Hybrid Gated DeltaNet + MoE | MoE Transformer | MoE Transformer | Dense Unified | Hybrid Gated DeltaNet + MoE |
| 上下文长度 | 128K | 128K | 256K | 256K | 256K | 256K | 256K | 256K |
| 内存占用 | ~12GB | ~63GB | 22GB | 22GB | 17GB | ~15GB | ~13GB | ~21GB |
| 许可证 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| 多模态支持 | - | - | 图像 | 图像 | 图像 | 图像 | 图像+音频 | 图像 |
| thinking 模式 | ✅ Harmony | ✅ Harmony | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) |
| SWE-bench (代码问题) | 60.7% | ~62% | 69.2% | 73.4% | 71.0% | ~ | ~70% | - (world model) |
| AIME (竞赛数学) | 96%/98.7% | - | 91.0%/91.0% | 92.7%/92.7% | 88.3% | ~ | ~88% | - (world model) |
| MMLU (知识测试) | 85.3% | - | 85.3% | 86.1% | 85.2% | ~ | ~85.5% | - (world model) |

## 快速开始

### 下载模型文件

```bash
cd download-helper
docker build -t model-downloader:custom .

docker run --rm \
  --network host \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e HTTP_PROXY=http://127.0.0.1:10808 \
  -e HTTPS_PROXY=http://127.0.0.1:10808 \
  model-downloader:custom \
  bash -c "/hfd.sh unsloth/ModelRepoID --include ModelFileName --local-dir /models -x 10"
```

**参数**：
- `--network host`：必需，使容器能访问宿主的代理（`127.0.0.1` 指向宿主而非容器自身）
- `-x 10`：并发数（1-10）
- `HF_ENDPOINT=https://hf-mirror.com`：国内镜像加速，网络通畅时也可去掉直连 Hugging Face
- `HTTP_PROXY`/`HTTPS_PROXY`：若宿主机有代理，可显著加速国际下载

**下载后验证**：`ls -lh` 检查文件大小是否与 Hugging Face 页面一致。远小于预期则可能是 CDN 异常，加 `--network host` 重试。

```bash
# 监控下载进度（可选）
./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf
```

### 启动

| 项目 | 预设端口 | 预设上下文长度 | 启动命令 |
|------|------|-----------|----------|
| gpt-oss-20b | 8081 | 128K | `./run.sh gpt-oss-20b up -d` |
| gpt-oss-120b | 8082 | 128K | `./run.sh gpt-oss-120b up -d` |
| qwen35-35BA3B | 8083 | 256K | `./run.sh qwen35-35BA3B up -d` |
| qwen36-35BA3B | 8084 | 256K | `./run.sh qwen36-35BA3B up -d` |
| agentworld-35b | 8088 | 256K | `./run.sh agentworld-35b up -d` |
| gemma4-12b | 8086 | 256K | `./run.sh gemma4-12b up -d` |
| gemma4-26BA4B | 8085 | 256K | `./run.sh gemma4-26BA4B up -d` |
| gemma4-26b-qat | 8087 | 256K | `./run.sh gemma4-26b-qat up -d` |

## API 调用

### 多模态（图像）

启用多模态需在 `docker-compose.yml` 中配置 mmproj：

```yaml
- LLAMA_ARG_MMPROJ=/models/mmproj-F16.gguf
- LLAMA_ARG_MMPROJ_OFFLOAD=off
```

测试命令：
```bash
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "描述这张图片"},
        {"type": "image_url", "image_url": {"url": "https://..."}}
      ]
    }]
  }'
```

### thinking 模式

Gemma 4 / Qwen 3.x 默认开启 thinking，会在回答前输出 `reasoning_content`。如需关闭，需使用如下命令：
```bash
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

### GPT-OSS 系列的 reasoning_effort

GPT-OSS 20B/120B 使用 OpenAI 独有的 **Harmony** chat format，行为与其他模型不同：

- 始终会生成内部推理（`reasoning_content`），**不能完全关闭**
- 推理强度通过 `reasoning_effort: "low" | "medium" | "high"` 控制，`reasoning_effort` **不影响生成速度**（GPU 算力是瓶颈），只影响 reasoning 长度
- 响应分三个 channel：`analysis`（内部思考）、`commentary`（工具调用）、`final`（最终回复）
- 若需要"快速回答"，用 `low` + 较小 `max_tokens`（如 100）；复杂任务用 `high` + 较大 `max_tokens`（如 800）

测试命令：
```bash
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 300,
    "chat_template_kwargs": {"reasoning_effort": "low"}
  }'
```

## opencode 集成

### 关键：thinking/reasoning_effort 通过服务端参数控制

opencode `models.<id>.options` 中的字段不再传递到 API 调用（[Issue #20815](https://github.com/anomalyco/opencode/issues/20815)），所有 thinking/reasoning_effort 控制必须在 `docker-compose.yml` 中通过 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS` 环境变量来控制（见下表）。好处是不依赖 opencode 版本，所有请求（curl、opencode、agent-browser）行为一致，代价是调整需重启容器。

| 模型 | 环境变量值 | 含义 |
|------|-----------|------|
| `llama-gpt-oss-20b` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"reasoning_effort": "high"}` | 推理深度 high |
| `llama-gemma4-26BA4B` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": true}` | 开启 thinking |

> `enable_thinking` 在 llama.cpp 9519+ 开始废弃，改用 `--reasoning on/off`。当前仍生效。

**注意**：JSON 值必须用**外层单引号**包裹，否则 docker compose 会解析为 map：

```yaml
environment:
  - 'LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}'   # ✅
  - LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}    # ❌ 被解析为 map
```

### opencode 端配置

> ⚠️ opencode 默认认为自定义 provider 只支持 text 输入。**不声明 `modalities` 无法开启多模态**（[Issue #9897](https://github.com/anomalyco/opencode/issues/9897)）。

添加到 `~/.config/opencode/opencode.json`。模板（替换端口和模型名即可）：

```json
"llama-cpp-xxxx": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "llama.cpp (模型名称)",
  "options": { "baseURL": "http://localhost:PORT/v1", "apiKey": "anything" },
  "models": {
    "模型文件名.gguf": {
      "name": "模型ID",
      "modalities": { "input": ["text"]       , "output": ["text"] },
      "limit": { "context": 262144, "output": 8192 }
    }
  }
}
```

多模态模型需改 `modalities.input` 为 `["text", "image"]`。以下快速对照：

| provider_id | port | model file | model name | context | modalities |
|------------|------|-----------|------------|---------|------------|
| `llama-cpp-20b` | 8081 | `gpt-oss-20b-Q4_K_M.gguf` | `gpt-oss-20b` | 131072 | text |
| `llama-cpp-120b` | 8082 | `gpt-oss-120b-mxfp4-00001-of-00003.gguf` | `gpt-oss-120b` | 131072 | text |
| `llama-cpp-qwen35` | 8083 | `Qwen3.5-35B-A3B-Q4_K_M.gguf` | `qwen35-35b-a3b` | 262144 | text+image |
| `llama-cpp-qwen36` | 8084 | `Qwen3.6-35B-A3B-Q4_K_M.gguf` | `qwen36-35b-a3b` | 262144 | text+image |
| `llama-cpp-gemma4` | 8085 | `gemma-4-26B-A4B-it-Q4_K_M.gguf` | `gemma4-26b-a4b` | 262144 | text+image |
| `llama-cpp-gemma4-12b` | 8086 | `gemma-4-12b-it-Q4_K_M.gguf` | `gemma-4-12b` | 131072 | text+image |
| `llama-cpp-gemma4-26b-qat` | 8087 | `gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf` | `gemma4-26b-qat` | 262144 | text+image |
| `llama-cpp-agentworld-35b` | 8088 | `Qwen-AgentWorld-35B-A3B-Q4_K_M.gguf` | `agentworld-35b` | 262144 | text+image |

## 注意事项

- 不要同时运行多个大模型，需按需启动/停止
- `run.sh` 会自动匹配宿主机的 UID:GID
- 镜像 `ghcr.io/ggml-org/llama.cpp:server-cuda` 需保持较新版本
