# Local LLM Deployment

本地部署的开源 LLM 服务，基于 llama.cpp + Docker。

## 硬件环境

本目录下部署的所有开源 LLMs 已经在 NVIDIA RTX 5070 Ti (16GB VRAM) 上测试成功，理论上在更大显存的显卡上会有更好的表现。

## 可用模型及表现

下表中的速度和延迟均指在 NVIDIA RTX 5070 Ti (16GB VRAM) 上的表现。

| 指标 | GPT-OSS-20B | GPT-OSS-120B | Qwen3.5-35BA3B | Qwen3.6-35BA3B | Gemma4-26BA4B | Gemma4-12B |
|------|-------------|--------------|---------------|---------------|---------------|------------|
| API生成速度 (low) | 155 tok/s | 12.72 tok/s | - | - | - | - |
| API生成速度 (medium) | 154 tok/s | 12.62 tok/s | 57.77 tok/s | 57.03 tok/s | 44.06 tok/s | 91.2 tok/s |
| API生成速度 (high) | 150 tok/s | 12.54 tok/s | - | - | - | - |
| 首Token延迟 | 48 ms | 726 ms | 73 ms | 80 ms | 160 ms | 365 ms |
| Prefill 速度 (4K prompt) | **8198 tok/s** | **672 tok/s** | **1612 tok/s** | **1634 tok/s** | **2101 tok/s** | **3058 tok/s** |
| 量化格式 | Q4_K_M | MXFP4 | Q4_K_M | Q4_K_M | Q4_K_M | Q4_K_M |
| 发布日期 | 2025-08-05 | 2025-08-05 | 2026-02-24 | 2026-04-16 | 2026-04-02 | 2026-06-03 |
| 参数量 | 21B (3.6B活跃) | 117B (5.1B活跃) | 35B (3B活跃) | 35B (3B活跃) | 26B (3.8B活跃) | 12B (dense) |
| 模型架构 | MoE Transformer | MoE Transformer | Hybrid Gated DeltaNet + MoE | Hybrid Gated DeltaNet + MoE | MoE Transformer | Dense Unified |
| 上下文长度 | 128K | 128K | 256K | 256K | 256K | 256K |
| 内存占用 | ~12GB | ~63GB | 22GB | 22GB | 17GB | ~13GB |
| 许可证 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| 多模态支持 | - | - | 图像 | 图像 | 图像 | 图像+音频 |
| thinking 模式 | ✅ Harmony | ✅ Harmony | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) | ✅(可禁用) |
| SWE-bench (代码问题) | 60.7% | ~62% | 69.2% | 73.4% | 71.0% | ~70% |
| AIME (竞赛数学) | 96%/98.7% | - | 91.0%/91.0% | 92.7%/92.7% | 88.3% | ~88% |
| MMLU (知识测试) | 85.3% | - | 85.3% | 86.1% | 85.2% | ~85.5% |

## 下载模型文件

### 方案 A：hfd
`download-helper/` 目录提供下载容器，该容器使用 python:3.11-slim 为基础的自定义镜像，使用 hfd 脚本支持断点续传和多线程高速下载。下载前需确认模型文件的正确名称。容器启动模板如下：

```bash
cd download-helper
docker build -t model-downloader:custom.

docker run --rm \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  model-downloader:custom \
  bash -c "/hfd.sh unsloth/ModelRepoID --include ModelFileName --local-dir /models -x 10"
```

**参数说明**：
- `-x 10`：10 并发连接（官方建议 1-10）
- `HF_ENDPOINT`：使用 hf-mirror.com 镜像源加速下载

### 方案 B：curl 容器下载命令
- **用途**：避免 huggingface-cli lock 问题
- **命令格式**：
```bash
docker run --rm \
  -v /home/liyujun/projects/local-llm/xxx/models:/models \
  -u "1000:1001" \
  curlimages/curl:8.5.0 \
  -L -C - -o /models/模型文件名.gguf \
  https://hf-mirror.com/路径/模型文件名.gguf
```
- **参数说明**：
  - `-L`: 跟随重定向
  - `-C -`: 断点续传
  - `-o`: 输出文件路径
- **实际示例**：
```bash
docker run --rm -v /home/liyujun/projects/local-llm/llama-gemma4-26BA4B/models:/models -u "1000:1001" curlimages/curl:8.5.0 -L -C - -o /models/gemma-4-26B-A4B-it-Q4_K_M.gguf https://hf-mirror.com/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf
```

### 监控下载进度

```bash
./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf
```

- 参数1：项目名称
- 参数2：模型文件名

## 启动命令

| 项目 | 预设端口 | 预设上下文长度 | 启动命令 |
|------|------|-----------|----------|
| gpt-oss-20b | 8081 | 128K | `./run.sh gpt-oss-20b up -d` |
| gpt-oss-120b | 8082 | 128K | `./run.sh gpt-oss-120b up -d` |
| qwen35-35BA3B | 8083 | 256K | `./run.sh qwen35-35BA3B up -d` |
| qwen36-35BA3B | 8084 | 256K | `./run.sh qwen36-35BA3B up -d` |
| gemma4-26BA4B | 8085 | 256K | `./run.sh gemma4-26BA4B up -d` |
| gemma4-12b | 8086 | 256K | `./run.sh gemma4-12b up -d` |


## 注意事项

- 不要同时运行多个大模型，需按需启动/停止
- `run.sh` 已自动匹配宿主机的 UID:GID，避免权限问题
- 不要同时启动 `gemma4-12b` (≈13GB) 和 `gemma4-26BA4B` (≈17GB)，单卡 16GB 显存不足
- `ghcr.io/ggml-org/llama.cpp:server-cuda` 镜像需保持较新版本，新模型（如 Gemma 4）使用了较新的 GGUF 特性，旧镜像会报 `unknown projector type` 错误。更新命令：`docker pull ghcr.io/ggml-org/llama.cpp:server-cuda`

## 多模态与 thinking 模式

### 多模态支持

启用多模态（图像/音频）需额外下载 `mmproj-F16.gguf` 投影器文件，并在 `docker-compose.yml` 中配置：

```yaml
- LLAMA_ARG_MMPROJ=/models/mmproj-F16.gguf
- LLAMA_ARG_MMPROJ_OFFLOAD=off   # 投影器放 CPU，节省显存
```

多模态调用示例（OpenAI 兼容格式）：

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

Gemma 4 系列默认开启 `thinking`（思维链推理）模式，模型会在回答前先输出 `reasoning_content`，消耗大量 token，可能导致最终 `content` 为空。

如需**直接获得最终答案**（推荐用于多模态或简单问答），在请求中传：

```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

完整示例：

```bash
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

> **opencode 用户注意**：本仓库的 llama.cpp 容器已通过 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}` 服务端参数全局启用，**无需在 opencode 请求中传递**。详见 [opencode 集成配置](#opencode-集成配置) 章节。

启用 thinking 模式可获得更高质量的复杂推理结果（数学、代码、规划任务），但需相应增大 `max_tokens`。

### GPT-OSS 系列（Harmony 格式）

GPT-OSS 20B/120B 使用 OpenAI 独有的 **Harmony** chat format，行为与其他模型不同：

- **架构上是推理模型**，始终会生成内部推理（`reasoning_content`），**不能完全关闭**
- 推理强度通过 `reasoning_effort: "low" | "medium" | "high"` 控制（默认 `medium`）
- 响应分三个 channel：
  - `analysis` — 内部思考（不直接返回给用户）
  - `commentary` — 工具调用
  - `final` — 用户可见的最终回复
- 调用时通过 `chat_template_kwargs` 传递参数（不要用 `enable_thinking`）：

```bash
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 300,
    "chat_template_kwargs": {"reasoning_effort": "low"}
  }'
```

> **opencode 用户注意**：本仓库的 llama.cpp 容器已通过 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"reasoning_effort": "medium"}` 服务端参数设默认值。临时切换档位需重启容器。详见 [opencode 集成配置](#opencode-集成配置) 章节。

实测性能对比（"用一句话介绍你自己" prompt，warmup 后取 3 次平均）：

| 模型 | low | medium (默认) | high | reasoning 长度差异 |
|------|-----|---------------|------|---------------------|
| GPT-OSS-20B  | 155 tok/s | 154 tok/s | 150 tok/s | 30 → 310 → 650 字符 |
| GPT-OSS-120B | 12.72 tok/s | 12.62 tok/s | 12.54 tok/s | 38 → 284 → 659 字符 |

**关键观察**：
- `reasoning_effort` **不影响生成速度**（GPU 算力是瓶颈），只影响 reasoning 长度
- 三个等级的速度差异 < 3%
- 若需要"快速回答"，用 `low` + 较小 `max_tokens`（如 100）可避免过度推理
- 复杂任务用 `high` + 较大 `max_tokens`（如 800）可获得更高质量答案

**关于旧数据 vs 新数据**：旧版本 llama.cpp 镜像（4 周前）测试时 `gpt-oss-20b` 速度约 227.87 tok/s，新镜像（0.0.9519）为 ~154 tok/s（medium）。下降主要源自**新镜像的 Harmony 解析开销**和测试方法差异（prompt 长度、warmup 状态、token 统计口径），与 reasoning 模式本身无关。`gpt-oss-120b` 实际速度（12.62 tok/s）比旧数据（12.34 tok/s）略升。

### reasoning_effort 支持矩阵

`reasoning_effort` 是 OpenAI 在 GPT-OSS (Harmony 格式) 中引入的参数，**不是通用 LLM 标准**。下表说明本仓库 6 个模型对该参数的支持情况（基于 llama.cpp `0.0.9519` 镜像实测）：

| 模型 | 原生支持 `reasoning_effort` | 原生支持 `enable_thinking` | 推荐参数 |
|------|---------------------------|--------------------------|----------|
| **GPT-OSS-20B/120B** | ✅ 是（Harmony 训练时支持，3 档可调） | ❌ 无效（参数名错） | `reasoning_effort: low/medium/high` |
| **Gemma 4 12B/26B** | ❌ 不识别（实测忽略） | ✅ 开关式（on/off） | `enable_thinking: false` |
| **Qwen3.5-35BA3B** | ❌ 不识别（实测忽略） | ✅ 开关式 | `enable_thinking: false` |
| **Qwen3.6-35BA3B** | ❌ 不识别（实测忽略） | ✅ 开关式 | `enable_thinking: false` |

**实测验证**（"用一句话介绍你自己" prompt，warmup 后取 3 次平均，`max_tokens=400`）：

| 模型 | 测试条件 | reasoning 长度 | completion tokens | 结论 |
|------|----------|---------------|-------------------|------|
| **Gemma 4 12B** | 基线（不传参数） | 964-1384 字符 | 400 (max) | 默认开启 |
| Gemma 4 12B | `enable_thinking: false` | **0** | 26-34 | ✅ 关闭成功 |
| Gemma 4 12B | `reasoning_effort: "high"` | **1071-1339** | 400 (max) | ❌ **无效**，行为同基线 |
| **Qwen 3.6 35BA3B** | 基线（不传参数） | 1170-1326 字符 | 400 (max) | 默认开启 |
| Qwen 3.6 35BA3B | `enable_thinking: false` | **0** | 28-33 | ✅ 关闭成功 |
| Qwen 3.6 35BA3B | `reasoning_effort: "high"` | **1173-1281** | 400 (max) | ❌ **无效**，行为同基线 |

**关键观察**：
- `reasoning_effort: "high"` 在 Gemma 4 和 Qwen 3.6 上**完全无效果**（reasoning 长度与基线相同）
- `enable_thinking: false` 能**完美关闭** thinking 模式
- 即使传 `reasoning_effort`，llama.cpp server 不会报错（被 chat_template 静默忽略）

**为什么 vLLM 能用 `reasoning_effort` 但 llama.cpp 不行？**

[llama.cpp Discussion #20408](https://github.com/ggml-org/llama.cpp/discussions/20408) 维护者原话：

> "Llama-server cannot support reasoning_effort at all. ... However, the reasoning effort is something that the model is trained with and thus only the specific model can support."

vLLM 在其推理引擎中**额外实现了** `reasoning_effort` 到 `enable_thinking` 的自动映射（`low/medium/high` → `enable_thinking=true`，`none` → `false`），但 llama.cpp 没有这个映射逻辑。

**结论**：在本仓库使用 llama.cpp 部署时，**只有 GPT-OSS 系列能用 `reasoning_effort`，其他三个模型必须用 `enable_thinking: false`**。

## opencode 集成配置

将本仓库 6 个模型作为 provider 添加到 `~/.config/opencode/opencode.json` 即可使用。

### 关键：thinking/reasoning 通过 llama.cpp 服务端参数控制

由于 opencode 1.3.4+ 存在 [Issue #20815](https://github.com/anomalyco/opencode/issues/20815) 回归（`models.<id>.options` 中的字段不再传递到 API 调用），**所有 thinking/reasoning 控制必须通过 llama.cpp 服务端参数**实现，即在 `docker-compose.yml` 的 `environment` 中添加 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS`。

**好处**：
- ✅ 不依赖 opencode 版本行为
- ✅ 所有通过该容器的请求都生效（curl、opencode、agent-browser 全部一致）
- ✅ 配置简单，一个环境变量搞定
- ✅ llama.cpp 原生支持，性能无损

**代价**：
- ⚠️ 调整 thinking/reasoning 需要重启容器（`docker compose up -d`）
- ⚠️ 暂不能在 opencode TUI 中通过 Ctrl+T 动态切换模式

### llama.cpp 端：6 个 docker-compose.yml 全部已配置

每个 `docker-compose.yml` 的 `environment` 末尾都有（参数值用单引号包裹，避免 YAML 把 `{...}` 解析为 map）：

| 模型 | 环境变量值 | 含义 |
|------|-----------|------|
| `llama-gpt-oss-20b` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"reasoning_effort": "medium"}` | Harmony 推理深度 medium |
| `llama-gpt-oss-120b` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"reasoning_effort": "medium"}` | Harmony 推理深度 medium |
| `llama-gemma4-26BA4B` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}` | 关闭 thinking |
| `llama-gemma4-12b` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}` | 关闭 thinking |
| `llama-qwen35-35BA3B` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}` | 关闭 thinking |
| `llama-qwen36-35BA3B` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}` | 关闭 thinking |

**YAML 语法注意点**：JSON 对象必须用**外层单引号**包裹，否则 docker compose 会把 `{"enable_thinking": false}` 解析为 YAML map（type `map[string]interface {}`）：

```yaml
environment:
  - 'LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}'   # ✅ 正确
  - LLAMA_ARG_CHAT_TEMPLATE_KWARGS={"enable_thinking": false}    # ❌ 被解析为 map
```

### opencode 端：简洁配置（不带 thinking 字段）

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "llama-cpp-20b": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (20B)",
      "options": { "baseURL": "http://localhost:8081/v1", "apiKey": "anything" },
      "models": {
        "gpt-oss-20b-Q4_K_M.gguf": {
          "name": "gpt-oss-20b",
          "limit": { "context": 131072, "output": 8192 }
        }
      }
    },
    "llama-cpp-120b": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (120B)",
      "options": { "baseURL": "http://localhost:8082/v1", "apiKey": "anything" },
      "models": {
        "gpt-oss-120b-mxfp4-00001-of-00003.gguf": {
          "name": "gpt-oss-120b",
          "limit": { "context": 131072, "output": 8192 }
        }
      }
    },
    "llama-cpp-qwen35": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (Qwen35 35B-A3B)",
      "options": { "baseURL": "http://localhost:8083/v1", "apiKey": "anything" },
      "models": {
        "Qwen3.5-35B-A3B-Q4_K_M.gguf": {
          "name": "qwen35-35b-a3b",
          "limit": { "context": 262144, "output": 8192 }
        }
      }
    },
    "llama-cpp-qwen36": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (Qwen3.6 35B-A3B)",
      "options": { "baseURL": "http://localhost:8084/v1", "apiKey": "anything" },
      "models": {
        "Qwen3.6-35B-A3B-Q4_K_M.gguf": {
          "name": "qwen36-35b-a3b",
          "limit": { "context": 262144, "output": 8192 }
        }
      }
    },
    "llama-cpp-gemma4-26b": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (Gemma 4 26B-A4B)",
      "options": { "baseURL": "http://localhost:8085/v1", "apiKey": "anything" },
      "models": {
        "gemma-4-26B-A4B-it-Q4_K_M.gguf": {
          "name": "gemma4-26b-a4b",
          "limit": { "context": 262144, "output": 8192 }
        }
      }
    },
    "llama-cpp-gemma4-12b": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama.cpp (Gemma 4 12B)",
      "options": { "baseURL": "http://localhost:8086/v1", "apiKey": "anything" },
      "models": {
        "gemma-4-12b-it-Q4_K_M.gguf": {
          "name": "gemma-4-12b",
          "limit": { "context": 131072, "output": 8192 }
        }
      }
    }
  }
}
```

### 临时调整 thinking/reasoning

如需切换（启用/关闭 thinking，或调整 reasoning_effort 档位）：

1. 编辑对应模型的 `docker-compose.yml`，修改 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS` 的 JSON 值
2. 重启容器：
   ```bash
   cd llama-gemma4-12b && docker compose up -d
   ```
3. 无需重启 opencode

### 验证服务参数生效

```bash
# 1. 检查容器内环境变量
docker exec llama-gemma4-12b cat /proc/1/environ | tr '\0' '\n' | grep CHAT_TEMPLATE

# 2. 对需要思考的提问，确认 reasoning_content 为空
curl -s -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-12b-it-Q4_K_M.gguf","messages":[{"role":"user","content":"Solve this step by step: A train travels 60 km in 50 minutes. How long will it take to travel 150 km?"}],"max_tokens":800,"temperature":0.1}' \
  | python3 -c "import json,sys; r=json.load(sys.stdin); m=r['choices'][0]['message']; print('content (前300字):', m.get('content','')[:300]); print('reasoning_content:', m.get('reasoning_content', '(None)'))"
```

如果 `reasoning_content` 字段为 `(None)`，说明 thinking 已被服务端参数关闭。
