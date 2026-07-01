# Gemma4-12B MTP Speculative Decoding 不可用

## 现象

```log
E llama_init_from_model: failed to initialize the context: Gemma4Assistant requires
ctx_other to be set (this warning is normal during memory fitting)
```

后续推理时报 `failed to process speculative batch`。

## 根因

llama-server 在创建 speculative draft/MTP context 时，错误地把 target model 的 `embeddings = true` 和 `pooling_type` 复制了过来。Gemma4Assistant draft model 只输出 draft logits，没有 embeddings 输出，因此初始化失败。

`llama-cli` 不受影响，因为它不会复制 target-side 的 embeddings 参数到 speculative context。

## 相关链接

| 链接 | 说明 |
|------|------|
| [#24443](https://github.com/ggml-org/llama.cpp/issues/24443) | MTP models fail to load in llama-server, works with llama-cli |
| [#24795](https://github.com/ggml-org/llama.cpp/issues/24795) | gemma4-assistant MTP 在 b9553 正常，b9702+ 回归 |
| [#24942](https://github.com/ggml-org/llama.cpp/pull/24942) | **修复 PR（OPEN，未合并）**：禁用 draft/MTP context 的 embeddings/pooling |

## 解决条件

PR #24942 合并到主干后，拉取最新 Docker image 即可启用 MTP。

## 预期收益

MTP draft model（`MTP/gemma-4-12b-it-Q8_0-MTP.gguf`，444 MB）使用 `--spec-type draft-simple --spec-draft-n-max 5` 配置，预期速度从 65→~100-160 tok/s。

## Docker image 版本记录

| Tag | 日期 | MTP 状态 |
|-----|------|---------|
| server-cuda (b9519) | 2026-06-05 | ❌ 不识别 gemma4-assistant |
| server-cuda (b9843) | 2026-06-30 | ❌ 识别但 embeddings bug |
| server-cuda (post-#24942) | TBD | ✅ 修复后 |
