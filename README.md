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

¹ Strata 是独立引擎、非 llama.cpp，结构上与上面 8 个项目不同类。0.2.1 起官方直接发布 Docker 镜像，**不用再本地编译引擎**；首次部署要预置模型文件，完整步骤见下节。

> **Strata 的三个本机注意点**：① 容器内解析不到 `huggingface.co`（DNS 被污染），所以 `strata/docker-compose.yml` 里设了 `HF_ENDPOINT=https://hf-mirror.com`；② 0.2.x 起服务端**强制 API key**（没设就在首次启动时自动生成，存 `strata-data/state/api-key`），所有客户端都要带 `Authorization: Bearer <key>`；③ 改配置的重启语义——运行配置在 `strata-data/install/strata-<尺寸>.json`（0.1.x 在 `config/`），改完 `docker restart strata` 即可（`up -d` 对运行中的容器是 no-op，不重读 config），改 `strata/docker-compose.yml` 才需要 `./run.sh strata down` 再 `up -d`。

## Strata 部署

`strata/` 是独立引擎 [Niko1221/Strata](https://github.com/Niko1221/Strata)（gitignored），只跑 Qwen3.8-Flash-Next，模型数据落在同级的 `strata-data/`（约 87 GB，也 gitignored）。它把模型分层放在 GPU（高频 expert）/ RAM（全量）/ SSD（29 GB 查找表），因此能在单张 16 GB 卡上跑 125 B MoE。

**0.2.1 起官方直接发布 Docker 镜像**，不用再 clone 源码编译 CUDA 引擎（以前那套 20~40 分钟的构建流程已作废）。镜像里固定了引擎与 Terminal 的版本，容器入口走 `strata launch`：准备模型 → 加载 → 起服务。

**与 llama.cpp 项目共用 `run.sh` 和 `download-helper/`**（HF 下载路径完全通用，Strata 的分片就用它下，见 [2.1](#21-gguf-分片用-download-helper-预置)）。

### 1. 拉官方镜像

| 显卡 | 镜像标签 | 宿主要求 |
|---|---|---|
| NVIDIA RTX 20/30/40/50 系 | `0.2.2-cuda13` | 驱动 **≥ 580** + NVIDIA Container Toolkit |
| NVIDIA GTX 10 (Pascal) / Tesla P100 / V100 | `0.2.2-cuda12` | 驱动 **≥ 575**（0.2.2 起 CUDA 12 包又带 Pascal/Volta 代码） |
| AMD RX 9000 / Radeon AI PRO R9700 | `0.2.1-rocm-gfx120x` | 0.2.2 镜像尚未发布（引擎包有 `hip-rx9070`），先用 0.2.1 |
| AMD RX 7000 / RX 6000 | `0.2.2-rocm-gfx110x` | `amdgpu` 内核驱动（0.2.2 起顺带 RX 6000 引擎包） |
| AMD Ryzen AI Max (Strix Halo) | `0.2.2-rocm-gfx1151` | `amdgpu` 内核驱动 |
| Intel Arc | 无官方镜像 | 官方没发过 sycl tag；Gyro 可在 Arc 跑，引擎要自己源码编 |

```bash
docker pull ghcr.io/niko1221/strata:0.2.2-cuda13   # 本机实测一次拉完（1.4 GB）
# 拉不动时用 scripts/pull-docker-image.py 走 registry API 并发拉（见 2.3 节的说明）
```

拉完先留个回滚标签：

```bash
docker tag ghcr.io/niko1221/strata:0.2.2-cuda13 strata:v0.2.2
```

### 2. 预置模型文件

0.2.x 的数据卷布局（`strata/docker-compose.yml` 里挂 `../strata-data:/data`）：

| 宿主路径 | 内容 |
|---|---|
| `strata-data/Strata-data/models/<尺寸>/` | GGUF 分片 + `mmproj-*.gguf`（看图要用） |
| `strata-data/Strata-data/packs/<尺寸>/` | 准备好的 pack（省掉一次本机转换） |
| `strata-data/Strata-data/mtp/` | MTP 张量与 draft layer |
| `strata-data/install/` | 运行配置 `strata-<尺寸>.json`、日志 |
| `strata-data/state/` | 预设、调优结果、**API key** |
| `strata-data/config/` | 终端自身设置 |

⚠️ **0.2.x 不读 0.1.x 的旧布局**（`strata-data/models` / `packs` / `mtp` / `config`）：要么把目录挪进 `Strata-data/`，要么用 `MODEL_PATH` 指到旧位置。

#### 2.1 GGUF 分片：用 `download-helper` 预置

`strata launch` 认 `MODEL_PATH`（容器内已有的 GGUF 目录），指过去就**不再下载模型本身**。预置时保持原文件名和子目录结构：

```bash
docker run --rm --name download-strata-shards \
  --network host \
  -v xxx/local-llm/strata-data/Strata-data/models:/models \
  -u "$(id -u):$(id -g)" \
  -e HF_ENDPOINT=https://hf-mirror.com \
  download-helper:latest \
  bash -c "/hfd.sh ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF \
           --include 'IQ3_S/*' --local-dir /models -x 10"
```

- 落盘路径须是 `strata-data/Strata-data/models/IQ3_S/<原名>`。
- **看图用的 `mmproj-Qwen3.8-Flash-Next-BF16.gguf` 必须和分片放同一目录**：0.2.x 找不到就直接报「put mmproj-… in <folder>」，不会替你下载。
- hf-mirror 对 pinned revision（`ed59f920…`）返回 308 未缓存，所以走 `main`——当前 `main` HEAD 恰好等于该 commit，但**将来会漂移**。分片只按 size 校验、不查 sha256，想严格校验就按[下载模型文件](#下载模型文件)那节取 `lfs.oid` 比对。

#### 2.2 pack 与 MTP

- **pack**（`packs/<尺寸>/`，含 `native_experts.txt` + `tokenizer/`）：没有它，首次启动会在本机做一次转换（读 79 GB，写约 1.5 GB）。从 0.1.x 升级时，把旧的 `packs/iq3_s` 直接搬进 `Strata-data/packs/` 就能复用，不重转。
- **MTP draft layer**（`mtp/rt/`）：0.2.x 会自动拉约 5 GB 的 MTP 张量并生成 `mtp/rt/`。想并行加速下载，用引擎自带的 `tools/mtp_fetch.py`（`inventory` / `fetch` / `verify` 三个子命令，`fetch` 支持 `--only <子串>` 过滤；多路并行时过滤串不能重叠，否则互相覆盖）：

```bash
export HF_ENDPOINT=https://hf-mirror.com
cd strata
python3 tools/mtp_fetch.py fetch --out ../strata-data/Strata-data/mtp \
  --only mtp.layers.0.mlp.experts.gate_up_proj &
python3 tools/mtp_fetch.py fetch --out ../strata-data/Strata-data/mtp \
  --only mtp.layers.0.mlp.experts.down_proj &
python3 tools/mtp_fetch.py fetch --out ../strata-data/Strata-data/mtp \
  --only mtp.layers.0.self_attn &
wait
python3 tools/mtp_fetch.py fetch  --out ../strata-data/Strata-data/mtp   # 补齐小张量 + manifest，这步不能省
python3 tools/mtp_fetch.py verify --out ../strata-data/Strata-data/mtp   # 退出码 0 = 全部张量正确
```

#### 2.3 镜像拉不动时

`docker pull` 单连接下 blob，遇到按连接限速的 registry 会爬到几小时。用 `scripts/pull-docker-image.py`（见 [下载诊断与脚本](#下载诊断与脚本)）走 registry HTTP API 并发拉取、装配成 docker-archive 再 `docker load`。一个坑：**存储驱动是 `overlay2`（未启用 containerd 镜像存储）时 `docker load` 只认 docker-archive**（`<config>.json` + `manifest.json` + 各 `<id>/layer.tar`，且**层必须是未压缩的 tar**），直接喂 OCI layout（`oci-layout` + `index.json` + `blobs/sha256/*`）会报 `blobs/json: no such file or directory`。

### 3. 启动与客户端接入

```bash
./run.sh strata up -d
docker logs -f strata            # 首次启动：准备模型 → 加载（本机约 40 s）
```

**API key**：0.2.x 起服务端**强制**要 key（容器内监听所有地址，不带 key 不给服务）。compose 里没设 `API_KEY` 时，首次启动自动生成并存到 `strata-data/state/api-key`：

```bash
docker exec strata strata launch --show-key --preset docker
```

客户端要带 `Authorization: Bearer <key>`。三处常用配置的最小改动：

| 客户端 | 文件 | 改什么 |
|---|---|---|
| opencode | `~/.config/opencode/opencode.json` | `providers.strata.settings.apiKey` 填 key（`baseURL` 保持 `http://localhost:8089/v1`） |
| codex | `~/.codex/<profile>.config.toml` | `[model_providers.<id>]` 里加 `experimental_bearer_token = "<key>"`（或 `env_key = "STRATA_API_KEY"` 走环境变量） |
| Hermes | `~/.hermes/config.yaml` | `providers.strata.api_key` 填 key |

官方有 `strata connect <app>`（opencode / codex / claude-code / hermes / pi / oh-my-pi / openclaw）能生成这些配置：**默认只打印不写文件**，`--write` 才写（写前询问 + 留备份）。但它的 opencode 输出是 **V1 风格**（`provider` 而非 `providers`），还会顺手改掉默认模型、`compaction`、`share`；codex / hermes 的输出是**整文件替换**。所以本仓库的做法是：**只把它当参考，key 手工填进自己的配置**。

### 4. 配置改哪儿

- **运行配置**：`strata-data/install/strata-<尺寸>.json`（0.1.x 时代在 `strata-data/config/`，升级后位置变了）。
- `args` 是 setup 自有键，**重跑 setup 会被覆盖**；`user_args` 才是你手改的引擎参数（每次启动都盖在 `args` 上）。`expert_profile_save` / `vram_elastic` / `vision.elastic` / `reasoning_budget_tokens` 这些顶层键通常会被后续 setup 保留，**但换引擎大版本的镜像有一条例外，见下一节**。
- 改完 `docker restart strata` 即可生效；改 `docker-compose.yml` 里的环境变量（MODEL / CONTEXT / VISION / KV / STRATA_SET 等）要 `./run.sh strata down` 再 `up -d`。
- 0.1.x 的 `LOW_RAM` / `RESIDENT_BUDGET_GIB` / `KV_STREAMING` / `LAYER_SPLIT` / `CONFIG` / `REINSTALL` 在 0.2.x **已废弃**，只打警告并忽略；`HOST` 也不再需要（容器内本来就监听所有地址，能被谁访问由端口映射决定）。

### 5. 更新与回滚

```bash
docker compose pull && ./run.sh strata down && ./run.sh strata up -d
```

模型文件、pack、预设、调优结果都在卷里，换镜像不会重下。回滚：把 compose 的 `image:` 改回旧标签（更新前 `docker tag` 留好），`down` 之后再 `up -d`。

⚠️ **0.2.2 实测的坑：换引擎大版本会重生成运行配置。** 容器启动时若发现旧配置里的组件路径在新镜像里不存在（引擎目录名随版本变，如 `0.1.46-…/strata-vision` → `0.1.47-…`；开着 vision 时必触发），入口会打出一行 «making them again» 然后**整个重写** `install/strata-<尺寸>.json`——`user_args`、`expert_profile_save`、`vram_elastic`、`vision.elastic`、`reasoning_budget_tokens` 全部丢，引擎参数回落到自动算的默认值（本机实测 pool 13、槽位 3771、expert-profile 指回镜像内路径）。API key、模型文件、pack、MTP、学习版专家画像（`config/expert-profile-learned.bin`）不受影响。

升级后必须重放用户键再 `docker restart strata`，重放完成核对 `slots` / `pool_workers`：

```bash
python3 - <<'EOF'
import json
p = 'strata-data/install/strata-iq3_s.json'
c = json.load(open(p))
c['user_args'] = ['--pool-workers', '14']
c['expert_profile_save'] = '/data/config/expert-profile-learned.bin'
c['vram_elastic'] = True
c['reasoning_budget_tokens'] = 16384
c.setdefault('vision', {})['elastic'] = True
json.dump(c, open(p, 'w'), indent=1)
EOF
docker restart strata
# 验证（期望 4454 / 14）：curl -s localhost:8089/metrics -H "Authorization: Bearer $(cat strata-data/state/api-key)" | see engine.expert_slots / pool_workers
```

### 6. 性能测量

`strata-bench/` 是标准化的测试工具（固定协议 + 结果留档 + 配对比较），换版本或改配置后用它测，别直接拿两次数字相减：

```bash
python3 strata-bench/strata_bench.py bench --label "0.2.1"
python3 strata-bench/strata_bench.py compare results/旧.json results/新.json
```

本机实测（RTX 5070 Ti，IQ3_S，128K）：

| 版本变化 | decode | prefill | 结论 |
|---|---|---|---|
| 0.1.45 → 0.2.1（engine 0.1.45→0.1.46） | 配对均值 **+3.12 tok/s（+2.9%）**，13/15 正，p=0.0082；中位 108.3 → 110.8 | 2944.8 → 2894.7（−1.7%） | 官方镜像/数据布局迁移的收益 |
| 0.2.1 → 0.2.2（engine 0.1.46→0.1.47） | 配对均值 **−0.90 tok/s，p=0.59（不显著）**；中位 110.8 → 112.3 | 2894.7 → 2931.8（+1.3%） | 引擎对 Qwen 的路径没改（源码仅一处 VDEBUG 编译修复），速度等价，符合预期 |

详见 [`strata-bench/README.md`](strata-bench/README.md) 与 `docs/strata-tuning.md`（本机笔记，不进版本库）。

## 采样参数配置

各模型的 `command:` 字段通过 CLI 参数设置采样参数，缓解模型生产重复内容（过量重采样）的问题。opencode 等客户端未显式传参时，均使用这些默认值。

> **Strata 的采样参数不走 `command:`，而是走运行配置里的 `sampling` 块**（`strata-data/install/strata-<尺寸>.json`）。0.2.x 支持 `temperature` / `top_p` / `top_k` / `min_p` / `presence_penalty` / `repetition_penalty` / `frequency_penalty` / `penalty_last_n` / `seed`，作为**请求没带这些字段时的默认值**；请求自己带的永远优先，显式 `temperature=0` 仍是 greedy，不带 `temperature` 也是 greedy。写错的值会让服务直接拒绝启动（不会静默改采样）。

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
- **`limit` 要按模型的真实上限填**：`context` 给模型上限；`output` 给 **thinking 模型**留足（本机 **Strata** 用 `32768`——给 `8192` 时难题的思考会吃光预算、返回**空正文**）；想让 `compaction.reserved` 生效还必须同时显式设 `limit.input`
- 字段名有两套等价写法（v2.0.22 实测都能用）：本文件在用的 `package`/`settings`/`capabilities` ↔ 官方 schema 的 `npm`/`options`/`modalities`
- **不要写 `variants` 字段**（会让该模型被整体丢弃、从列表消失），但 opencode 会自动为 openai-compatible 模型生成 `low`/`medium`/`high` 档位（映射为 `reasoningEffort`，正是 Strata 需要的请求参数）。⚠️ **选过的档位会持久化**：在 TUI 的 variant 窗口选一次，会写进 `~/.local/state/opencode/model.json`，**此后该模型一直套用它、跨会话有效**，条目里的 `options.reasoningEffort` 不再生效。
