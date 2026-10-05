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

¹ Strata 不是 llama.cpp：它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29GB 查找表），因此能在单张 16GB 卡上跑 125B MoE。**它独占 94.7% 显存，启动前须停掉其它模型容器；且只有 1 个 slot（串行），不适合并发辅助任务。** 部署步骤见 [Strata 部署](#strata-部署)。

² 官方 model card 未报告 SWE-bench Verified / AIME / MMLU，无法与本表其它列同口径并列。其自报的另一套基准分数为：SWE-bench Pro 62.5、SWE-bench Multilingual 81.0、LiveCodeBench v6 91.9、GPQA Diamond 91.7、HLE 35.9、DeepSWE 1.1 58.7、NL2Repo-Bench 48.1、CoWorkBench 73.9、AndroidWorld 84.5、LVBench 76.6、ERQA 72.3、RealWorldQA 88.5（出处：[Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)，评测条件见其 card 脚注）。

## 快速开始

### 下载模型文件

`download-helper/` 是唯一入口：一个装了 `hfd.sh` + `aria2c` 的薄镜像。

**先判断 hf-mirror 有没有缓存你要的文件**——这一步决定用哪个代理方案，跳过会白等几小时：

```bash
curl -sI "https://hf-mirror.com/Owner/Repo/resolve/main/SomeFile.gguf" | head -1
```

| 响应 | 含义 | 走哪个方案 |
|------|------|-----------|
| `200` / `302` | 已缓存 | **方案 A** |
| `308` | 未缓存，跳到 `huggingface.co` | **方案 B** |

```bash
cd download-helper
docker build -t download-helper:latest .

# 方案 A：hf-mirror 已缓存 —— 不设代理
docker run --rm --name download-`basename $PWD` \
  --network host \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  download-helper:latest \
  bash -c "/hfd.sh unsloth/ModelRepoID --include 'SomeFile.gguf' --local-dir /models -x 10"

# 方案 B：hf-mirror 未缓存 —— 移除 HF_ENDPOINT，走代理直连 huggingface.co
docker run --rm --name download-`basename $PWD` \
  --network host \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HTTP_PROXY=http://127.0.0.1:PORT \
  -e HTTPS_PROXY=http://127.0.0.1:PORT \
  download-helper:latest \
  bash -c "/hfd.sh unsloth/ModelRepoID --include 'SomeFile.gguf' --local-dir /models -x 10"
```

四个参数都不能省：

- **`--network host`** —— 容器内的 `127.0.0.1` ≠ 宿主的 `127.0.0.1`，不共享网络就访问不到宿主代理。
- **`-x 10`** —— 这是 **aria2c 的「每个文件 10 条连接」**，不是总并发。大文件下载时**不能降**：hf-mirror 对单条连接限速，实测会从开头的 9 MB/s 掉到 180 KB/s。
- **`-u "$(id -u):$(id -g)"`** —— 免得下载出来的文件属 root。
- **容器名固定 `download-<project>`** —— 便于下次运行前清理。中断后先 `docker rm -f download-<project>` 再重跑。

**取官方文件列表**（确认 mmproj、分片的准确文件名）：

```bash
curl -s "https://huggingface.co/api/models/Owner/Repo" --proxy http://127.0.0.1:PORT |
  python3 -c "import json,sys; [print(f['rfilename']) for f in json.load(sys.stdin)['siblings']]"
```

**下载后验证**：拿 HF 的 LFS sha256 逐个比对，比只看大小可靠（`lfs.oid` 就是文件的 sha256）：

```bash
curl -s "https://huggingface.co/api/models/Owner/Repo/tree/main" --proxy http://127.0.0.1:PORT |
  python3 -c "
import json,sys
for f in json.load(sys.stdin):
    print(f\"{f['size']:>15,}  {(f.get('lfs') or {}).get('oid','-')}  {f['path']}\")"

sha256sum llama-xxx/models/SomeFile.gguf   # 与上面的 oid 对照
```

```bash
# 监控下载进度（可选）
./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf
```

### 下载诊断与脚本

本仓库只提供 `download-helper/` 这条 HF 下载路径。诊断限速类型、以及下面两个非 HF 场景的脚本，都在 **docker-builder 技能**里（`~/.agents/skills/docker-builder/`）：

| 文件 | 用途 |
|------|------|
| `scripts/net-probe.sh` | 判断瓶颈是「按连接限速」还是「总带宽上限」——长连接速率 << 短请求速率就是前者，加并发有效 |
| `scripts/parallel-fetch.py` | 并行分块下载大文件：切块 + 每块一条独立 range 请求，规避按连接限速；manifest 驱动，逐文件校验 sha256，支持断点续传 |
| `scripts/pull-docker-image.py` | 拉 Docker 镜像并 `docker load` 导入，绕开被限速的 `docker pull`（见 [2.3](#23-基础镜像绕开被限速的-docker-pull)） |
| `references/download-speed-diagnosis.md` | 限速类型的完整判读与实测数据 |

> 这些脚本**不在本仓库内**，换机器需自行获取。

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
| strata | 8089 | 128K | 见 [Strata 部署](#strata-部署) ¹ |

¹ Strata 是独立引擎、非 llama.cpp，结构上与上面 8 个项目不同类。首次部署要额外构建镜像和预置模型文件，完整步骤见下节。

## Strata 部署

`strata/` 是独立引擎 [Niko1221/Strata](https://github.com/Niko1221/Strata)（gitignored），只跑 Qwen3.8-Flash-Next，模型数据落在同级的 `strata-data/`（约 93 GB，也 gitignored）。它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29 GB 查找表），因此能在单张 16 GB 卡上跑 125 B MoE。

**与 llama.cpp 项目共用的只有 `run.sh`**，其余（镜像构建、模型下载、配置结构）都不适用。

### 1. clone 引擎并构建镜像

上游 Dockerfile 在 build 时编译 CUDA 引擎，**20~40 分钟**，且 `CUDA_ARCHITECTURES` 要按显卡代次填：

| 显卡 | RTX 50 系 | 40 系 | 30 系 | A 系 |
|------|----------|------|------|------|
| `CUDA_ARCHITECTURES` | `120` | `89` | `86` | `80` |

```bash
git clone https://github.com/Niko1221/Strata.git strata

cd strata
docker build -t strata:upstream --build-arg CUDA_ARCHITECTURES=120 .

# 派生层：把 /opt/strata 交给宿主用户，使 bind mount 产生的文件不属 root
docker build -t strata:latest -f Dockerfile.local \
  --build-arg HOST_UID=$(id -u) --build-arg HOST_GID=$(id -g) .
```

`Dockerfile.local` 这层是必需的：上游镜像以 root 运行，`/opt/strata` 又是 bind mount 的宿主目录，不 chown 的话 `strata-data/` 里的文件会全属 root、后续层就没法增量写。

之后用常规方式启动：`./run.sh strata up -d`。

### 2. 下载模型文件

⚠️ **不要让 `setup.py` 自己下载模型。** 它是单连接，实测会被 hf-mirror 限速到 0.6 MB/s，85 GB 的 ETA 是 34 小时——实际不可用。三个部分分别处理：

#### 2.1 GGUF 分片：用 `download-helper` 预置

`setup.py` 接受预置文件，命中就跳过、不会重下（`strata/setup.py:766` 看到 `.done` 标记直接返回；`:797` 文件存在且 size 等于 HEAD 的 `Content-Length` 就补标记再返回）。所以直接用上面的 `download-helper` 流程预置，保持**原文件名和子目录结构**：

```bash
# 当前 MODEL=IQ3_S 时是这两个分片；换尺寸改 --include 里的目录名
docker run --rm --name download-strata-shards \
  --network host \
  -v xxx/local-llm/strata-data/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  download-helper:latest \
  bash -c "/hfd.sh ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF \
           --include 'IQ3_S/*' --local-dir /models -x 10"
```

落盘路径须是 `strata-data/models/IQ3_S/<原名>`（`hfd.sh` 保留仓库内的子目录，`--local-dir` 指到 `models/` 即可）。

hf-mirror 对 setup.py 用的 pinned revision（`setup.py:66` 的 commit `ed59f920…`）返回 308 未缓存，所以走 `main`——当前 `main` HEAD 恰好等于该 commit，但**将来会漂移**。这些分片 setup.py 只按 size 校验、不查 sha256，想严格校验就按[下载模型文件](#下载模型文件)那节取 `lfs.oid` 比对。

#### 2.2 MTP 张量：拆 `mtp_fetch.py` 的过滤并行

MTP 张量（落在 `strata-data/mtp/`）由引擎自带的 `tools/mtp_fetch.py` 拉，本身是**串行**的，5.21 GB 排成一队约 2.8 小时。它有 `inventory` / `fetch` / `verify` 三个子命令，`fetch` 支持 `--only <子串>` 过滤，且各实例写各自的 `.bin` 文件、互不冲突——利用这点并行：

```bash
export HF_ENDPOINT=https://hf-mirror.com
cd strata
# 96% 的体积集中在下面三个张量上，拆 3 路约 1 小时
python3 tools/mtp_fetch.py fetch --out ../strata-data/mtp \
  --only mtp.layers.0.mlp.experts.gate_up_proj &
python3 tools/mtp_fetch.py fetch --out ../strata-data/mtp \
  --only mtp.layers.0.mlp.experts.down_proj &
python3 tools/mtp_fetch.py fetch --out ../strata-data/mtp \
  --only mtp.layers.0.self_attn &
wait

# 关键收尾：补齐剩下的小张量并写出完整 manifest
python3 tools/mtp_fetch.py fetch  --out ../strata-data/mtp
python3 tools/mtp_fetch.py verify --out ../strata-data/mtp   # 退出码 0 = 全部张量正确
```

并行安全的前提是 **`--only` 的过滤互不重叠**，否则会互相覆盖；每个张量下完都会按脚本内置的 pinned revision sha256 校验。**那步不带 `--only` 的完整 `fetch` 不能省**——小张量和 `mtp-manifest.json` 是它写的。

#### 2.3 基础镜像：绕开被限速的 `docker pull`

`docker pull` 用单条连接下载 blob，遇到按连接限速的 registry 会爬到几小时。可选做法是自己走 registry HTTP API：匿名取 token → 解析 manifest → 列出每个 blob 的 digest 与大小 → 分块并发逐个拉取 → 校验 sha256 → 装配成 **docker-archive** tar → `docker load`。

格式上有个坑：**存储驱动是 `overlay2`（未启用 containerd 镜像存储）时，`docker load` 只认 docker-archive**，即 `<config>.json` + `manifest.json` + 各 `<id>/layer.tar`，且**层必须是未压缩的 tar**。直接喂 OCI layout（`oci-layout` + `index.json` + `blobs/sha256/*`）会报 `blobs/json: no such file or directory`。

现成脚本见 [下载诊断与脚本](#下载诊断与脚本)。

### 3. 配置与运行要点

- **显存互斥**：占 94.7%（15.4/16.3 GB），启动前必须停掉 llama.cpp 容器；只有 1 个 slot（串行），不适合做并发辅助任务。
- **`HF_ENDPOINT=https://hf-mirror.com` 必需**：容器内解析不到 `huggingface.co`（DNS 被污染），已在 `strata/docker-compose.yml` 里设好。
- **切尺寸**：改 compose 里 `MODEL`（`Q2_0`/`IQ2_XS`/`IQ3_XXS`/`IQ3_S`/`Coder`/`Swift`）后 **`./run.sh strata down` 再 `up -d`**——直接改 compose 后 `up -d` 不会重建容器。分片表与 vision encoder 共用，已缓存的不重复下载。
- **配置位置**：serving / 采样参数在 `strata-data/config/strata-<尺寸>.json`，chat template kwargs 在 `strata/docker-compose.yml` 的环境变量里。
- **首次启动**仍会跑 `setup.py` 做格式转换（生成 `strata-data/packs/`），此时 CPU / 磁盘占用高属正常。

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

**手动删掉这个键可能白删：会话切换会把它写回来。** TUI 在会话 ID 变化时，会从该会话最后一条用户消息里恢复 variant 并重新持久化（`packages/tui/src/component/prompt/index.tsx:305-327`，`local.model.variant.set(msg.model.variant)`）。所以在一个已经用过 `high` 的旧会话里，键会不断复活。彻底清掉要么**新建会话**，要么在 variant 窗口选 Default。

### Strata 专用条目

Strata 接受任意模型名（服务端忽略该字段），故条目名可自定义。

`limit.output` 必须给思考留足余量：实测 `8192` 时难题的思考会吃光全部预算，返回**空正文**（`finish_reason: length`），官方建议 `32768`。

当前配置（2 个条目 + variant 切档）：

```json
"strata": {
  "package": "@opencode/ai/providers/openai-compatible",
  "name": "Strata",
  "settings": { "baseURL": "http://localhost:8089/v1", "apiKey": "anything" },
  "models": {
    "strata": {
      "name": "Qwen3.8-Flash-Next",
      "capabilities": { "tools": true, "input": ["text", "image"], "output": ["text"] },
      "limit": { "context": 131072, "input": 131072, "output": 32768 },
      "options": { "reasoningEffort": "high" }
    },
    "strata-none": {
      "name": "Qwen3.8-Flash-Next-None",
      "capabilities": { "tools": true, "input": ["text", "image"], "output": ["text"] },
      "limit": { "context": 131072, "input": 131072, "output": 32768 },
      "options": { "reasoningEffort": "none" }
    }
  }
}
```

#### 命名规则：model 名和 provider 名会被直接拼在一起

输入框下方的显示串由 TUI 拼成（`packages/tui/src/component/prompt/index.tsx:1441-1450`）：

```
{agent} · {model.name}{provider.name} · {variant}
```

**中间没有分隔符**——所以两段都会连着读，且当前选中的 variant 以 `·high` 形式跟在最后（`none` 不在档位表里，不会显示）。取值见 `context/local.tsx:266-268`：两段都优先用配置里的 `name`，缺省才回退到 `modelID` / `providerID`。

因此命名要满足两点：**每条模型名自带区分词**（没选 variant 时 `·high` 不显示，两条会撞名），**provider 名要短**（两条共用，省不掉也不该重复占位）。上面这套渲染出来是 29 字符，与云端模型（如 `Space Bunny FreeOpenCode Zen·max`，32 字符）相当。

`name` 纯属显示，调用时用的是 `providerID/modelID`（`opencode models` 也只打这两个），改名不影响任何请求。TUI 没有关闭 provider 名的开关（`packages/tui/src/config/index.tsx` 的 `Info` schema 里没有该项）。

> ⚠️ `strata-none` 也会弹出 `low`/`medium`/`high` 档位——`provider/transform.ts:800-805` 对 `@ai-sdk/openai-compatible` 的**每个**模型都返回这三个值，不看 `options`。在它上面选了档位就会覆盖 `options.reasoningEffort: none`，名字里的 `-None` 随即名不副实。

用法对照：

| 想要的效果 | 操作 |
|-----------|------|
| 默认（质量优先） | 选 `strata`，不选 variant |
| 中等 / 快 | 选 `strata` + variant `medium` / `low` |
| 最快、完全不思考 | 选 `strata-none` |

服务端还有两个兜底键，写在 `strata-data/config/strata-iq3_s.json`：

| 键 | 值 | 作用 |
|----|-----|------|
| `reasoning_budget_tokens` | `16384` | 思考硬上限，到点强制收尾再作答，保证不会出现空正文 |
| `fit_max_tokens` | `true` | `prompt + max_tokens` 超上下文时收敛输出长度，而非返回 400 |

> ⚠️ **改这两个键必须重启容器**：`serve/server.py:2940` 只在启动时读一次并存进 `self.fit_max_tokens`，之后不再看配置文件。`docker compose restart` 不够（entrypoint 不会重跑），要 `./run.sh strata down` 再 `up -d`。启动日志里能看到是否真的生效：
>
> ```
> server 0.0.0.0:8080, gpu 0, fit_max_tokens true, reasoning_budget_tokens 16384
> [strata] thinking budget: 16384 tokens (reasoning_budget_tokens; a request can set its own)
> ```

#### 上下文溢出：`fit_max_tokens` 能救什么、救不了什么

`serve/server.py:1379` 的可用余量是 `room = 131072 - 8 - prompt_tokens`（`CTX_SLACK = 8`）。行为分三种：

| 情形 | 行为 |
|------|------|
| `max_tokens ≤ room` | 正常生成 |
| `max_tokens > room` 且 `fit_max_tokens: true` | **收敛**到 `room`，HTTP 200 |
| `room < 1`（prompt ≥ 131064） | **仍然报错**，与 `fit_max_tokens` 无关 |

第三种是硬天花板：`server.py:1381` 的 `room < 1` 判断在 `fit_max_tokens` 分支**之前**，那时只会 `raise`。

实测（复现 opencode 报错的同一组数字）：

| 请求 | 结果 |
|------|------|
| prompt 102785 + `max_tokens` 29117（溢出 830） | HTTP 200，收敛到 28279，正常作答 |
| prompt 102785 + `max_tokens` 60000 | HTTP 200，同样收敛 |
| prompt 130978 + `max_tokens` 100（room 仅 86） | HTTP 200，`finish_reason: length`，86 tokens |

#### 为什么还需要调早 opencode 的压缩阈值

`fit_max_tokens` 只保证「不 400」，不保证「有地方写答案」——room 剩多少完全取决于 prompt 长度。所以 opencode 侧的自动压缩必须比这条线更早触发，否则会在压缩生效前先撞上 `room < 1`。

opencode 的阈值算法在 `packages/opencode/src/session/overflow.ts`：

- 未设 `limit.input` 时：`usable = context - min(limit.output, 32000)` = 131072 − 32000 = **99072**
- 设了 `limit.input` 时：`usable = limit.input - compaction.reserved`

两个容易踩的点：

1. **`compaction.reserved` 只在设了 `limit.input` 时才生效**（`overflow.ts:17-19` 的三元分支），否则那个 45000 根本不参与计算。
2. **只加 `limit.input` 会让压缩更晚触发**（`usable` 从 99072 变成 111072），必须同时显式设 `reserved`。

当前配置：

```json
// opencode.json
"compaction": { "reserved": 45000 }
// strata 条目的 limit（两个条目都要）
"limit": { "context": 131072, "input": 131072, "output": 32768 }
```

→ `usable = 131072 - 45000 = 86072`，比默认早 13000 tokens。

> `reserved` 是 v1 配置的字段名；`opencode debug config` 会把它显示成 `buffer`（`core/src/v1/config/migrate.ts:61` 的 v1→v2 改名），值能透传就说明写对了。

**还有一层：压缩只在 turn 收尾时检查**（`session/processor.ts:753-758`，拿上一轮的 `usage.tokens` 判断）。所以单个 turn 内新增的工具输出可以把 prompt 一次性顶过阈值——这正是 opencode 报 `prompt (102847) + max tokens (29117) exceeds the context` 的成因：上一轮结束时还没到 99072，这一轮就被顶过去了。`reserved` 留的 45000 缓冲就是为这种情况兜的底。

**Strata 只有 1 个 slot**，并发请求会排队而非报错——实测 3 个并发耗时 4.0/6.7/9.2 秒依次完成（总耗时是**累加**，不是取最大），且排队中的请求 6.5ms 就拿到响应头，不会触发客户端超时。日常单任务无影响；并行 subagent 会退化成串行。
