# Local LLM Deployment

本地部署的开源 LLM 服务，基于 llama.cpp + Docker。

## 硬件环境

本目录下部署的所有开源 LLMs 已经在 NVIDIA RTX 5070 Ti (16GB VRAM) 上测试成功，理论上在更大显存的显卡上会有更好的表现。

## 可用模型及表现

下表中的速度和延迟均指在 NVIDIA RTX 5070 Ti (16GB VRAM) 上的表现。

| 指标 | GPT-OSS-20B | GPT-OSS-120B | Qwen3.5-35BA3B | Qwen3.6-35BA3B | Gemma4-26BA4B |
|------|-------------|--------------|---------------|---------------|---------------|
| API生成速度 | 227.87 tok/s | 12.34 tok/s | 53.18 tok/s | 53.93 tok/s | 38.82 tok/s |
| 首Token延迟 | 147 ms | 1077 ms | 337 ms | 245 ms | 262 ms |
| 量化格式 | Q4_K_M | MXFP4 | Q4_K_M | Q4_K_M | Q4_K_M |
| 发布日期 | 2025-08-05 | 2025-08-05 | 2026-02-24 | 2026-04-16 | 2026-04-02 |
| 参数量 | 21B (3.6B活跃) | 117B (5.1B活跃) | 35B (3B活跃) | 35B (3B活跃) | 26B (3.8B活跃) |
| 模型架构 | MoE Transformer | MoE Transformer | Hybrid Gated DeltaNet + MoE | Hybrid Gated DeltaNet + MoE | MoE Transformer |
| 上下文长度 | 128K | 128K | 256K | 256K | 256K |
| 内存占用 | ~12GB | ~63GB | 22GB | 22GB | 17GB |
| 许可证 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| SWE-bench (代码问题) | 60.7% | ~62% | 69.2% | 73.4% | 71.0% |
| AIME (竞赛数学) | 96%/98.7% | - | 91.0%/91.0% | 92.7%/92.7% | 88.3% |
| MMLU (知识测试) | 85.3% | - | 85.3% | 86.1% | 85.2% |

## 下载模型文件

`download-helper/` 目录提供下载容器，该容器使用 python:3.11-slim 为基础的自定义镜像，使用 hfd 脚本支持断点续传和多线程高速下载，容器启动模板如下：

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


## 注意事项

- 不要同时运行多个大模型，需按需启动/停止
- `run.sh` 已自动匹配宿主机的 UID:GID，避免权限问题