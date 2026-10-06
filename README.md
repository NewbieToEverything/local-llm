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

¹ Strata 不是 llama.cpp：它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29GB 查找表），因此能在单张 16GB 卡上跑 125B MoE。**常态占 95.2% 显存，但可用 `POST /v1/vram` 按需让出（`vram_elastic`，实测 22 ms 放出 5.36 GiB），无须再停容器；并发方面引擎虽支持 `"parallel": 2..8`，但本机实测是负收益（见 §3），保持单 slot 更快。** 部署步骤见 [Strata 部署](#strata-部署)。

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

docker run --rm --name download-`basename $PWD` \
  --network host \
  -v xxx/local-llm/llama-xxx/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \   # ← 方案 A（已缓存）到此为止
  # 方案 B（未缓存）：删掉上面那行，改加下面两行，走代理直连 huggingface.co
  # -e HTTP_PROXY=http://127.0.0.1:PORT \
  # -e HTTPS_PROXY=http://127.0.0.1:PORT \
  download-helper:latest \
  bash -c "/hfd.sh unsloth/ModelRepoID --include 'SomeFile.gguf' --local-dir /models -x 10"
```

四个参数都不能省：

- **`--network host`** —— 容器内的 `127.0.0.1` ≠ 宿主的 `127.0.0.1`，不共享网络就访问不到宿主代理。
- **`-x 10`** —— 这是 **aria2c 的「每个文件 10 条连接」**，不是总并发。大文件下载时**不能降**：hf-mirror 对单条连接限速，实测会从开头的 9 MB/s 掉到 180 KB/s。
- **`-u "$(id -u):$(id -g)"`** —— 免得下载出来的文件属 root。
- **容器名固定 `download-<project>`** —— 便于下次运行前清理。中断后先 `docker rm -f download-<project>` 再重跑。

**取文件名与校验值**（`lfs.oid` 就是文件的 sha256，比只看大小可靠；`siblings` 接口也能列全部文件）：

```bash
curl -s "https://huggingface.co/api/models/Owner/Repo/tree/main" --proxy http://127.0.0.1:PORT |
  python3 -c "
import json,sys
for f in json.load(sys.stdin):
    print(f\"{f['size']:>15,}  {(f.get('lfs') or {}).get('oid','-')}  {f['path']}\")"

sha256sum llama-xxx/models/SomeFile.gguf            # 与上面的 oid 对照
./monitor.sh gpt-oss-20b gpt-oss-20b-Q4_K_M.gguf   # 可选：监控下载进度
```

### 下载诊断与脚本

本仓库只提供 `download-helper/` 这条 HF 下载路径。**限速诊断**与**两个非 HF 场景**（通用大文件、Docker 镜像）的脚本都在 **docker-builder 技能**里（`~/.agents/skills/docker-builder/`）：

| 类别 | 文件 | 用途 |
|------|------|------|
| 诊断 | `scripts/net-probe.sh` | 判断瓶颈是「按连接限速」还是「总带宽上限」——长连接速率 << 短请求速率就是前者，加并发有效 |
| 诊断 | `references/download-speed-diagnosis.md` | 限速类型的完整判读与实测数据 |
| 非 HF 下载 | `scripts/parallel-fetch.py` | 并行分块下载大文件：切块 + 每块一条独立 range 请求，规避按连接限速；manifest 驱动，逐文件校验 sha256，支持断点续传 |
| 非 HF 下载 | `scripts/pull-docker-image.py` | 拉 Docker 镜像并 `docker load` 导入，绕开被限速的 `docker pull`（见 [2.3](#23-基础镜像绕开被限速的-docker-pull)） |

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

> **Strata 的两个本机注意点**：① 容器内解析不到 `huggingface.co`（DNS 被污染），所以 `strata/docker-compose.yml` 里设了 `HF_ENDPOINT=https://hf-mirror.com`；② 改配置的重启语义——只改 `strata-data/config/strata-<尺寸>.json` 用 `docker restart strata`（`up -d` 对运行中的容器是 no-op，不会重读 config），改 `strata/docker-compose.yml` 才需要 `./run.sh strata down` 再 `up -d`。

## Strata 部署

`strata/` 是独立引擎 [Niko1221/Strata](https://github.com/Niko1221/Strata)（gitignored），只跑 Qwen3.8-Flash-Next，模型数据落在同级的 `strata-data/`（约 87 GB，也 gitignored）。它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29 GB 查找表），因此能在单张 16 GB 卡上跑 125 B MoE。

**与 llama.cpp 项目共用 `run.sh` 和 `download-helper/`**（HF 下载路径完全通用，Strata 的分片就用它下，见 [2.1](#21-gguf-分片用-download-helper-预置)），其余（镜像构建、配置结构）不适用。

### 1. clone 引擎并构建镜像

上游 Dockerfile 在 build 时编译 CUDA 引擎，**20~40 分钟**，且 `CUDA_ARCHITECTURES` 要按显卡代次填：

| 显卡 | RTX 50 系 | 40 系 | 30 系 | A 系 |
|------|----------|------|------|------|
| `CUDA_ARCHITECTURES` | `120` | `89` | `86` | `80` |

```bash
git clone https://github.com/Niko1221/Strata.git strata

cd strata
# 上游 Dockerfile 在 build 时要下 llama.cpp 源码（GitHub）+ apt/pip，全走构建期网络。
# 必须同时给 --network host 和四个代理变量（把 PORT 换成你的代理端口）：只给
# --network host 仍会直连，实测直连到 GitHub 只有 ~30 KB/s，37.7 MB 的包卡 40 分钟都过不去。
docker build --network host \
  --build-arg CUDA_ARCHITECTURES=120 \
  --build-arg HTTP_PROXY=http://127.0.0.1:PORT \
  --build-arg HTTPS_PROXY=http://127.0.0.1:PORT \
  --build-arg http_proxy=http://127.0.0.1:PORT \
  --build-arg https_proxy=http://127.0.0.1:PORT \
  -t strata:upstream .

# 派生层：把 /opt/strata 交给宿主用户，使 bind mount 产生的文件不属 root
docker build -t strata:latest -f Dockerfile.local \
  --build-arg HOST_UID=$(id -u) --build-arg HOST_GID=$(id -g) .
```

### 1b. 更新引擎到新版本

```bash
cd strata
git pull
```

然后**重新执行上面第 1 步那条 `strata:upstream` 的构建命令**（代理参数一个都不能省）。要点：

- **层缓存救不了更新**：`COPY . .` 排在下载/编译之前，源码一变它之后的所有层全部失效（Docker 层缓存只在「源码 + 构建命令完全没变」时命中，那时整条构建 0 秒完成）。llama.cpp 那个包在 `setup.py` 里本来有缓存，但上游 `.dockerignore` 刻意排除了 `third_party/`，宿主机上的副本进不了构建上下文。
- **有代理时整条约 4 分钟**：下载 17 秒 + sm_120 单架构编译约 3.5 分钟（20 核并行）。没有代理则无限重试。
- **先留回滚标签**，再重建：
  ```bash
  docker tag strata:upstream strata:upstream-<旧版本>
  docker tag strata:latest   strata:latest-<旧版本>
  ```
- 新版可能要新参数：`git pull` 后确认 `setup.py` 的 `MIN_ENGINE` 是否已等于新版本，并注意 config 里 `args` 是 setup 自有键，**重跑 `--setup` 会丢掉手加的引擎参数**（如 `--pool-workers`）。

`Dockerfile.local` 这层是必需的：上游镜像以 root 运行，`/opt/strata` 又是 bind mount 的宿主目录，不 chown 的话 `strata-data/` 里的文件会全属 root、后续层就没法增量写。

之后用常规方式启动：`./run.sh strata up -d`。

### 2. 下载模型文件

⚠️ **不要让 `setup.py` 自己下载模型。** 它是单连接，实测会被 hf-mirror 限速到 0.6 MB/s，85 GB 的 ETA 是 34 小时——实际不可用。三个部分分别处理：

#### 2.1 GGUF 分片：用 `download-helper` 预置

`setup.py` 的 `download()` 接受预置文件，命中就跳过、不会重下（有 `.done` 标记直接返回；文件存在且 size 等于 HEAD 的 `Content-Length` 就补标记再返回）。所以直接用上面的 `download-helper` 流程预置，保持**原文件名和子目录结构**：

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

hf-mirror 对 setup.py 用的 pinned revision（`setup.py` 的 `HF_REVISIONS` 里那个 commit `ed59f920…`）返回 308 未缓存，所以走 `main`——当前 `main` HEAD 恰好等于该 commit，但**将来会漂移**。这些分片 setup.py 只按 size 校验、不查 sha256，想严格校验就按[下载模型文件](#下载模型文件)那节取 `lfs.oid` 比对。

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

`docker pull` 单连接下 blob，遇到按连接限速的 registry 会爬到几小时。用 `scripts/pull-docker-image.py`（见 [下载诊断与脚本](#下载诊断与脚本)）走 registry HTTP API 并发拉取、装配成 docker-archive 再 `docker load`。一个坑：**存储驱动是 `overlay2`（未启用 containerd 镜像存储）时 `docker load` 只认 docker-archive**（`<config>.json` + `manifest.json` + 各 `<id>/layer.tar`，且**层必须是未压缩的 tar**），直接喂 OCI layout（`oci-layout` + `index.json` + `blobs/sha256/*`）会报 `blobs/json: no such file or directory`。

## 采样参数配置

各模型的 `command:` 字段通过 CLI 参数设置采样参数，缓解模型生产重复内容（过量重采样）的问题。opencode 等客户端未显式传参时，均使用这些默认值。

> **Strata 不适用本节**：它的配置（`strata-<尺寸>.json`）里只有引擎 / serving 参数，**没有任何采样参数**，也没有服务端采样默认值——缺省 `temperature` 时引擎按 **greedy** 解码。要非贪心采样，必须由请求携带参数（见 [覆盖默认值](#覆盖默认值)）。

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

客户端可以通过 API 请求体覆盖任一采样参数（8 个 llama.cpp 模型和 Strata 都支持；端口换成目标模型即可）：

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

两个例外要注意：

- **GPT-OSS**：`top_k=0` / `top_p=1.0` 是官方硬要求（保证 Harmony format 的输出分布正确），覆盖它们会让质量下降。
- **Strata**：它没有服务端采样默认值——**不传就是 greedy**（`temperature` 缺省与 `temperature=0` 等价，都不会转发给引擎）；要用别的采样必须在请求里显式带上。

## API 调用

### 多模态（图像）

**llama.cpp 系列**（Qwen 3.5/3.6、Gemma 4 系列、AgentWorld；GPT-OSS 不支持图像）需在 `docker-compose.yml` 中配置 mmproj：

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

> **Strata** 的图像能力是引擎内置的：`strata-<尺寸>.json` 的 `vision` 段 + 共享的 `mmproj-Qwen3.8-Flash-Next-BF16.gguf`，客户端只要在条目里声明 `capabilities.input: ["image"]`（当前条目配置见 `~/.config/opencode/opencode.json`）。

### thinking 模式

**llama.cpp 系列**（Strata 的思考控制走客户端 `reasoningEffort`，见 [thinking / reasoning 的控制位置](#thinking--reasoning-的控制位置)）。

Gemma 4 / Qwen 3.x 的 thinking 取决于各 compose 的 `LLAMA_ARG_CHAT_TEMPLATE_KWARGS`——**不是模型默认值，本仓库里也不统一**（如 qwen36 设为 `false`）。开启时回答前会输出 `reasoning_content`；临时关闭可在请求里带 `chat_template_kwargs`，永久改则改 env 并重启容器：
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

添加到 `~/.config/opencode/opencode.json` 的 `providers` 下。改完必须执行 `opencode reload`，否则运行中的 server 仍用旧配置（模型不会出现在列表里）：

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

- **多模态**要在 `capabilities.input` 里加 `"image"`，opencode 默认认为自定义 provider 只支持 text，**不声明即无法开启**（[Issue #9897](https://github.com/anomalyco/opencode/issues/9897)）
- 字段名有两套等价写法（v2.0.22 实测都能用）：本文件在用的 `package`/`settings`/`capabilities` ↔ 官方 schema 的 `npm`/`options`/`modalities`
- **不要写 `variants` 字段**（会让该模型被整体丢弃、从列表消失），但 opencode 会自动为 openai-compatible 模型生成 `low`/`medium`/`high` 档位（映射为 `reasoningEffort`，正是 Strata 需要的请求参数）。⚠️ **选过的档位会持久化**：在 TUI 的 variant 窗口选一次，会写进 `~/.local/state/opencode/model.json`，**此后该模型一直套用它、跨会话有效**，条目里的 `options.reasoningEffort` 不再生效。排查「条目写 high 却没在想」先看这里；恢复时在窗口选 **Default**。注意 `opencode run --model provider/model#variant` 也会写入，**用它测试会污染后续所有请求**（且删键会被会话切换写回来）。
