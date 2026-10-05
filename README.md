# Local LLM Deployment

本地部署的开源 LLM 服务，基于 llama.cpp + Docker。

## 硬件环境

本目录下部署的所有开源 LLMs 已经在 NVIDIA RTX 5070 Ti (16GB VRAM) 上测试成功，理论上在更大显存的显卡上会有更好的表现。

## 可用模型及表现

下表中的速度和延迟均指在 NVIDIA RTX 5070 Ti (16GB VRAM) 上的表现。

| 指标 | GPT-OSS-20B | GPT-OSS-120B | Qwen3.5-35BA3B | Qwen3.6-35BA3B | Gemma4-26BA4B | Gemma4-26BA4B (QAT) | Gemma4-12B | Qwen-AgentWorld-35B-A3B | Qwen3.8-Flash-Next (Strata) |
|------|-------------|--------------|---------------|---------------|---------------------|------------|------------------------|------------------------|------------------------|
| API生成速度 (medium) | 154 tok/s | 12.62 tok/s | 57.77 tok/s | 57.03 tok/s | 44.06 tok/s | **52.6 tok/s** | 91.2 tok/s (Q4_K_M) / 65 tok/s (Q6_K) | 62.2 tok/s | 59.1 tok/s |
| 首Token延迟 | 48 ms | 726 ms | 73 ms | 80 ms | 160 ms | **76 ms** | 365 ms (Q4_K_M) / 1251 ms (Q6_K) | 46 ms | 453 ms |
| Prefill 速度 (4K prompt) | **8198 tok/s** | **672 tok/s** | **1612 tok/s** | **1634 tok/s** | **2101 tok/s** | **2645 tok/s** | **3058 tok/s** (Q4_K_M) / **3185 tok/s** (Q6_K) | 1747 tok/s | 2573 tok/s |
| 量化格式 | Q4_K_M | MXFP4 | Q4_K_M | Q4_K_M | Q4_K_M | UD-Q4_K_XL (QAT) | Q4_K_M / Q6_K | Q4_K_M | GSQ-RCO IQ3_S |
| 发布日期 | 2025-08-05 | 2025-08-05 | 2026-02-24 | 2026-04-16 | 2026-04-02 | 2026-06-09 | 2026-06-03 | 2026-06-24 | 2026-09 |
| 参数量 | 21B (3.6B活跃) | 117B (5.1B活跃) | 35B (3B活跃) | 35B (3B活跃) | 26B (3.8B活跃) | 26B (3.8B活跃) | 12B (dense) | 35B (3B活跃) | 125B (6B活跃) + 51B n-gram + 4B MTP |
| 模型架构 | MoE Transformer | MoE Transformer | Hybrid Gated DeltaNet + MoE | Hybrid Gated DeltaNet + MoE | MoE Transformer | MoE Transformer | Dense Unified | Hybrid Gated DeltaNet + MoE | Hybrid Gated DeltaNet + QSA + N-gram + MoE |
| 上下文长度 | 128K | 128K | 256K | 256K | 256K | 256K | 256K | 256K | 128K (原生 262K) |
| 内存占用 | ~12GB | ~63GB | 22GB | 22GB | 17GB | ~15GB | ~13GB (Q4_K_M) / ~14GB (Q6_K) | ~21GB | 66GB RAM / 15.4GB 显存 |
| 许可证 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | **qwen-community-1.0**（非 Apache，商用需自行确认） |
| 多模态支持 | - | - | 图像 | 图像 | 图像 | 图像 | 图像+音频 | 图像 | 图像 |
| SWE-bench (代码问题) | 60.7% | ~62% | 69.2% | 73.4% | 71.0% | ~ | ~70% | - (world model) | - ² |
| AIME (竞赛数学) | 96%/98.7% | - | 91.0%/91.0% | 92.7%/92.7% | 88.3% | ~ | ~88% | - (world model) | - ² |
| MMLU (知识测试) | 85.3% | - | 85.3% | 86.1% | 85.2% | ~ | ~85.5% | - (world model) | - ² |

¹ Strata 不是 llama.cpp：它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29GB 查找表），因此能在单张 16GB 卡上跑 125B MoE。**它独占 94.7% 显存，启动前须停掉其它模型容器；且只有 1 个 slot（串行），不适合并发辅助任务。** 首次启动需先构建镜像（见 [AGENTS.md](AGENTS.md)），并会下载约 85GB 模型、转换格式，耗时数小时。

² 官方 model card 未报告 SWE-bench Verified / AIME / MMLU，无法与本表其它列同口径并列。其自报的另一套基准分数为：SWE-bench Pro 62.5、SWE-bench Multilingual 81.0、LiveCodeBench v6 91.9、GPQA Diamond 91.7、HLE 35.9、DeepSWE 1.1 58.7、NL2Repo-Bench 48.1、CoWorkBench 73.9、AndroidWorld 84.5、LVBench 76.6、ERQA 72.3、RealWorldQA 88.5（出处：[Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)，评测条件见其 card 脚注）。

## 快速开始

### 下载模型文件

```bash
cd download-helper
docker build -t download-helper:latest .

docker run --rm \
  --network host \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e HTTP_PROXY=http://127.0.0.1:PORT \
  -e HTTPS_PROXY=http://127.0.0.1:PORT \
  download-helper:latest \
  bash -c "/hfd.sh unsloth/ModelRepoID --include ModelFileName --local-dir /models -x 10"
```

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
| agentworld-35b | 8084 | 256K | `./run.sh agentworld-35b up -d` |
| qwen36-35BA3B | 8085 | 256K | `./run.sh qwen36-35BA3B up -d` |
| gemma4-12b | 8086 | 256K | `./run.sh gemma4-12b up -d` |
| gemma4-26BA4B | 8087 | 256K | `./run.sh gemma4-26BA4B up -d` |
| gemma4-26b-qat | 8088 | 256K | `./run.sh gemma4-26b-qat up -d` |
| strata | 8089 | 128K | 需先构建镜像 ¹ |

¹ Strata 与上面 8 个模型有三点差异，其余配置见 `strata/docker-compose.yml`，构建步骤见 [AGENTS.md](AGENTS.md)：

1. **首次须先构建镜像**（上游 Dockerfile 要编译 CUDA 引擎，20~40 分钟），否则 `./run.sh strata up -d` 直接失败。
2. **独占 94.7% 显存**，启动前须停掉其它模型容器；且只有 1 个 slot（串行），不适合并发辅助任务。
3. **首次启动会下载约 85GB 模型并转换格式**（落到 `strata-data/`，完成后约 93GB），耗时数小时、期间系统卡顿属正常。容器内解析不到 `huggingface.co`（DNS 被污染），已在 compose 里设 `HF_ENDPOINT=https://hf-mirror.com`。

尺寸可换：改 compose 里 `MODEL` 后重启即可，`Q2_0` / `IQ2_XS` / `IQ3_XXS` / `IQ3_S` / `Coder` / `Swift` 共用已缓存的分片表与 vision encoder。

## 采样参数配置

各模型的 `command:` 字段通过 CLI 参数设置采样参数，缓解模型生产重复内容（过量重采样）的问题。opencode 等客户端未显式传参时，均使用这些默认值。

> `LLAMA_ARG_*` 环境变量中仅 `LLAMA_ARG_TOP_K` 被注册，其他采样参数（`--temp`、`--top-p`、`--repeat-penalty`、`--presence-penalty`、`--frequency-penalty`）不支持 env var，必须通过 CLI 参数传入。

### 各模型配置

| 模型 | 端口 | command: |
|------|------|----------|
| gpt-oss-20b | 8081 | `--temp 1.0 --top-p 1.0 --top-k 0 --repeat-penalty 1.0` |
| gpt-oss-120b | 8082 | 同上 |
| qwen35-35BA3B | 8083 | `--temp 1.0 --top-p 0.95 --top-k 20 --repeat-penalty 1.0 --presence-penalty 1.5` |
| agentworld-35b | 8084 | `--temp 0.6 --top-p 0.95 --top-k 20` |
| qwen36-35BA3B | 8085 | `--temp 1.0 --top-p 0.95 --top-k 20 --repeat-penalty 1.0 --presence-penalty 1.5` |
| gemma4-12b | 8086 | `--temp 1.2 --top-p 0.95 --top-k 64` |
| gemma4-26BA4B | 8087 | 同上 |
| gemma4-26b-qat | 8088 | 同上 |

### 说明

- **Qwen 3.x**（`qwen35`、`qwen36`）：官方推荐 `presence_penalty=1.5` + `repeat_penalty=1.0`（禁用重复惩罚，转而使用存在惩罚）来抑制重复
- **Gemma 4**（`gemma4-12b`、`gemma4-26BA4B`、`gemma4-26b-qat`）：`--temp 1.2` 略高于默认值（0.8）以减少重复；`top_k=64` 为 Gemma 官方推荐值
- **GPT-OSS**（`gpt-oss-20b`、`gpt-oss-120b`）：官方要求 `top_k=0`（禁用）、`top_p=1.0`（禁用 nucleus sampling），以确保 Harmony format 的输出分布正确
- **Qwen-AgentWorld**（`agentworld-35b`）：基于 Qwen 架构，使用较低温度 0.6 以适应 agent 场景

### 覆盖默认值

客户端可以通过 API 请求体覆盖任一参数：

```bash
curl -X POST http://localhost:8085/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.8,
    "top_p": 0.9,
    "presence_penalty": 0.0
  }'
```

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

GPT-OSS 使用 OpenAI 独有的 **Harmony** chat format，行为与其他模型不同：

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

### thinking / reasoning 的控制位置

各 provider 不一样，取决于服务的 API 是否接受**请求级**参数：

| Provider | 控制位置 | 方式 |
|----------|---------|------|
| llama.cpp 系列 | **服务端** | `docker-compose.yml` 里的 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS`（见下表），调整需重启容器 |
| Strata | **客户端** | model 条目的 `options.reasoningEffort`，改 `~/.config/opencode/opencode.json` 后 `opencode reload` |

> **实测记录**：`models.<id>.options` 是否下发到 API，在 opencode v2.0.22 + Strata 上是**会下发的**——`options.reasoningEffort: "none"` 时服务端日志直接进入 `answering`（无 `thinking` 阶段），设为 `"high"` 时先出现 `thinking: 4552 of max 32768 tokens`。历史上 llama.cpp 侧受 [Issue #20815](https://github.com/anomalyco/opencode/issues/20815) 影响，故仍沿用服务端写法（未在 v2.0.22 上复测）。

llama.cpp 系列的环境变量：

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

### provider 条目模板

添加到 `~/.config/opencode/opencode.json` 的 `providers` 下（字段名与现有 8 个 llama.cpp provider 一致，实际生效已验证）：

```json
"llama-cpp-xxxx": {
  "package": "@opencode/ai/providers/openai-compatible",
  "name": "llama.cpp (模型名称)",
  "settings": { "baseURL": "http://localhost:PORT/v1", "apiKey": "anything" },
  "models": {
    "服务端模型ID": {
      "name": "显示名",
      "capabilities": { "tools": true, "input": ["text"], "output": ["text"] },
      "limit": { "context": 262144, "output": 8192 }
    }
  }
}
```

改完配置必须执行 `opencode reload`，否则运行中的 server 仍用旧配置（模型不会出现在列表里）。

字段名有两套等价写法，本机 v2.0.22 实测**都能用**：`package`/`settings`/`capabilities`（本文件在用）与官方 schema 的 `npm`/`options`/`modalities`。

> 多模态模型：`capabilities.input` 需含 `"image"`（官方写法为 `modalities.input`）。opencode 默认认为自定义 provider 只支持 text 输入，**不声明即无法开启多模态**（[Issue #9897](https://github.com/anomalyco/opencode/issues/9897)）。

**配置里不要写 `variants` 字段，但 variant 切换本身是可用的——这两件事不冲突。**

先说哪件不能做：在 model 条目里声明 `variants` 会让该模型被整体丢弃、从模型列表消失（连 `variants: {}` 也会）。原因在源码 `provider/transform.ts`：`variants()` 的 `@ai-sdk/openai-compatible` 分支虽然会自动生成档位，但 opencode 还会拿模型 ID 去匹配它内置的硬编码表（`glm-5.2`、`minimax-m3`、Anthropic 系列等），自定义模型匹配不上，配置里再声明就校验失败。

再说哪件能用：**opencode 会自动为 openai-compatible 模型生成 variant 档位**，取值来自 `WIDELY_SUPPORTED_EFFORTS = ["low", "medium", "high"]`，映射为 `{ reasoningEffort: <档位> }`——正好是 Strata 需要的请求参数。在 TUI 里选好模型后会弹出 variant 窗口（`DialogVariant`），选择结果**持久化到 `~/.local/state/opencode/model.json`**，跨会话有效。

**各档位的实际效果**（用 curl 直连测量，绕开 opencode 的 agent 循环干扰；同一问题各跑一次）：

| 档位 | 完成 tok | 思考字数 | 正文 |
|------|---------|---------|------|
| `none` | 852 | **0** | 1415 字 |
| `low` | 832 | 521 | 759 字 |
| `medium` | 1204 | 948 | 927 字 |
| `high` | 5495 | **15196** | 1011 字 |

`none` 的正文反而最长（无规划时写得更啰嗦），但总 token 只有 `high` 的 1/6.4。

> `low`/`medium`/`high` 是模型训练时注入的**软指令**，不是硬上限——差异在难题上才放大，简单问题上三者接近。要可靠上限请用服务端的 `reasoning_budget_tokens`（见下）。
>
> 上表测的是**单次请求**，刻意绕开 opencode 的 agent 循环。经 opencode 时每轮对话会发多个请求（辅助调用 + 多轮 agent），无法从服务端日志归因到某一档位的整体效果——**想验证档位差异就用 curl 直连服务端**，不要用 opencode 跑。

**`none` 不在 variant 档位里**，需要单独一个 model 条目。原因是 `none` 与另外三个不是同一个轴：`low`/`medium`/`high` 是「开启思考」模式下的强度档位，`none` 是**关闭思考**（模板渲染成空的 `<think></think>`）。

### ⚠️ variant 选择会持久化，并覆盖条目的 options

这是最容易踩的坑。在 TUI 的 variant 窗口里选一次，选择会写进 `~/.local/state/opencode/model.json` 的 `variant` 字段，**此后该模型一直套用它，跨会话有效**，条目里的 `options.reasoningEffort` 不再生效。

```json
// ~/.local/state/opencode/model.json
"variant": { "strata/strata": "high" }   // ← 这一条会一直覆盖 model 条目
```

排查「条目写 high 却没在想」时先看这里。要恢复成由条目控制，在 variant 窗口选 **Default**（等价于删掉该键），或直接删掉对应的键。

`opencode run --model provider/model#variant` 同样会写入这个状态，因此**用它做测试会污染后续所有请求**——测试档位请用 curl 直连服务端，或测完清理该键。

### Strata 专用条目

Strata 接受任意模型名（服务端忽略该字段），故条目名可自定义——**把区分词放在名字最前面**，否则 TUI 截断后几个条目看起来一样。

`limit.output` 必须给思考留足余量：实测 `8192` 时难题的思考会吃光全部预算，返回**空正文**（`finish_reason: length`），官方建议 `32768`。

当前配置（2 个条目 + variant 切档）：

```json
"strata": {
  "package": "@opencode/ai/providers/openai-compatible",
  "name": "Strata (Qwen3.8-Flash-Next 125B)",
  "settings": { "baseURL": "http://localhost:8089/v1", "apiKey": "anything" },
  "models": {
    "strata": {
      "name": "Strata high｜默认（variant 可切 low/medium）",
      "capabilities": { "tools": true, "input": ["text", "image"], "output": ["text"] },
      "limit": { "context": 131072, "output": 32768 },
      "options": { "reasoningEffort": "high" }
    },
    "strata-none": {
      "name": "Strata none｜不思考（最快）",
      "capabilities": { "tools": true, "input": ["text", "image"], "output": ["text"] },
      "limit": { "context": 131072, "output": 32768 },
      "options": { "reasoningEffort": "none" }
    }
  }
}
```

用法对照：

| 想要的效果 | 操作 |
|-----------|------|
| 默认（质量优先） | 选 `strata`，不选 variant |
| 中等 / 快 | 选 `strata` + variant `medium` / `low` |
| 最快、完全不思考 | 选 `strata-none` |

服务端还有两个兜底键，写在 `strata-data/config/strata-iq3_s.json`（改后需重启容器）：

| 键 | 值 | 作用 |
|----|-----|------|
| `reasoning_budget_tokens` | `16384` | 思考硬上限，到点强制收尾再作答，保证不会出现空正文 |
| `fit_max_tokens` | `true` | `prompt + max_tokens` 超上下文时自动压缩，而非返回 400 |

**Strata 只有 1 个 slot**，并发请求会排队而非报错——实测 3 个并发耗时 4.0/6.7/9.2 秒依次完成（总耗时是**累加**，不是取最大），且排队中的请求 6.5ms 就拿到响应头，不会触发客户端超时。日常单任务无影响；并行 subagent 会退化成串行。
