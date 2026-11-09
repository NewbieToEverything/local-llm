# strata-bench

Strata（Qwen3.8-Flash-Next 125B MoE）的**标准化测试工具**：把换版本、换配置时的测量固化成可复现的脚本 + 留档结果，避免每次得出假结论。

## 为什么需要它

Strata 是推理模型，**任何影响专家计算的改动都会改变浮点求和顺序 → 近平分叉 → 思考轨迹不同**，而不同文本的 per-token 代价相差可达数个百分点。所以：

- ❌ 跨配置直接比 decode tok/s 无效（历史上因此得出过 +7.4%、+3.9% 两个错误结论）
- ✅ 只有两种可靠做法：
  1. **配对比较**：同一批 prompt 在两个版本/配置下各跑一遍，按 (轮次, prompt) 配对，再做置换检验
  2. **只比 prefill**：由输入 token 决定，与输出无关
- ⚠️ **预热是必须的**：冷启动那几轮明显偏低（同一配置预热前 97.2 / 预热后 103.4 tok/s）
- ⚠️ **顺序会偏**：连续跑完 A 再跑 B，后跑的那臂机器更热（page cache、CPU 池都预热了），对比必须**交错顺序**
- ⚠️ `hit_rate` 不是纯缓存指标：走 PCIe 的专家被排除在外

## 协议（bench）

```
重启容器 → 3 条预热 → 3 轮 ×（5 个不同 prompt × 200 token + 1 条 5000 token prefill）
→ 15 个 decode 样本取中位数；prefill 单独统计
```

5 个 prompt 覆盖中文技术问答 / 英文代码理解 / 中文代码审查 / 英文通用问答 / 中文长文摘要，长度和语言都不同；`temperature=0` 固定。

## 用法

```bash
cd local-llm/strata-bench

# 一轮标准基准（结果自动落到 results/，同时写 json 和 md）
python3 strata_bench.py bench --label "0.2.1"

# 专家画像 A/B：两臂只差「启动时有没有学习版画像」，交错顺序，每臂重启 3 次
python3 strata_bench.py profile-ab --rounds 3

# 配对比较两个结果文件（按 (轮次, prompt) 配对 + 置换检验）
python3 strata_bench.py compare results/0.1.45-paired.json results/0.2.1-paired.json
```

参数：`--url`（默认 `http://127.0.0.1:8089`）、`--key-file`（默认 `<repo>/strata-data/state/api-key`）、`--model`、`--rounds`、`--out`、`--container`。服务端不认 key 时会自动去掉 `Authorization` 头重试，所以 0.1.x 和 0.2.x 都能用同一套脚本。

## 结果存档

`results/` 下每次跑都留两份：`<label>.json`（全部原始样本 + 引擎信息）和同名 `.md`（人看的摘要）。**历史结果就是后续比较的基线，别删**。

## 记录

| 日期 | 对比 | 结论 |
|---|---|---|
| 2026-10-21 | 0.1.45 → 0.2.1（engine 0.1.45 → 0.1.46） | **decode +3.12 tok/s（配对均值，+2.9%），13/15 为正，置换检验 p=0.0082**（中位 108.3 → 110.8）；prefill 2944.8 → 2894.7 tok/s（−1.7%）。数据：`results/0.1.45-paired.json`、`results/0.2.1-paired.json`、`results/compare-0.1.45-vs-0.2.1.json` |
| 2026-10-23 | 0.2.1 → 0.2.2（engine 0.1.46 → 0.1.47） | 配对均差 **−0.90 tok/s，p=0.59 不显著**（中位 110.8 → 112.3）；prefill 2894.7 → 2931.8（+1.3%）。引擎两侧配置一致（slots 4454 / workers 14），Qwen 路径源码未变 → 速度等价。数据：`results/0.2.2-paired.json`、`results/compare-0.2.1-vs-0.2.2.json` |
| 2026-10-26 | 128K → 256K 上下文（0.2.2 / engine 0.1.47，未换引擎） | 配对均差 **−0.97 tok/s，p=0.42 不显著**（中位 112.3 → 110.6）；prefill 2931.8 → 2940.7（+0.3%）；专家槽位 4454 → 4339（KV 流式 staging 占少量显存）。数据：`results/0.2.2-256k-20261026-004355.json`、`results/compare-0.2.2-128K-vs-256K.json` |
| 2026-10-28 | 0.2.3 → 0.2.7（engine 0.1.48 → 0.1.52，256K） | 配对均差 **−1.23 tok/s，p=0.37 不显著**（中位 109.8 → 108.2）；prefill 2688.0 → 2718.3（+1.1%）；专家槽位 4339 → 4328。数据：`results/0.2.3-256k-20261028-165541.json`、`results/0.2.7-256k-20261028-170427.json`、`results/compare-0.2.3-256k-vs-0.2.7-256k.json` |
| 2026-10-30 | 0.2.7 → 0.2.8（engine 0.1.52 → 0.1.54，256K） | 配对均差 **−1.79 tok/s，p=0.23 不显著**（中位 108.2 → 106.0）；prefill 2718.3 → 2757.8（+1.5%）；专家槽位 4328 → 4204。同配置重跑漂移 +2.85（p=0.073），差值在漂移内。数据：`results/0.2.7-256k-20261028-170427.json`、`results/0.2.8-256k-20261030-20261030-101641.json`、`results/compare-0.2.7-256k-vs-0.2.8-256k.json` |
| 2026-10-31 | 0.2.8 → 0.2.9（engine 0.1.54 → 0.1.55，256K） | 配对均差 **+1.34 tok/s，p=0.21 不显著**（中位 109.2 → 111.3）；prefill 2772.6 → 2887.2（**+4.1%**）；专家槽位 4204 → 4202。与官方 Linux NVIDIA「prompt +2%~6%、decode 不变」一致。数据：`results/0.2.8-256k-b2-20261030-102330.json`、`results/0.2.9-256k-20261031-182611.json`、`results/compare-0.2.8-b2-vs-0.2.9-256k.json`、`results/compare-0.2.8-b1-vs-0.2.9-256k.json` |
| 2026-11-06 | 0.2.9 → 0.2.11（engine 0.1.55 → 0.1.57，256K，DFlash2） | 配对均差 **+6.57 tok/s，p=0.0049**（中位 111.3 → 116.4，12/15 正）；同版本重跑漂移 −1.45（p=0.37）；prefill 2887.2 → 2843.5（−1.5%，5K prompt 未吃到 16K 上限）；专家槽位 4202 → 4377，`prefill_cap` 8192 → 16640。DFlash2 草稿接受率 84.0%，MTP 为 67.4%。数据：`results/0.2.9-256k-20261031-182611.json`、`results/0.2.11-256k-dflash2-20261106-171722.json`、`results/0.2.11-256k-dflash2-b2-20261106-171901.json`、`results/compare-0.2.9-256k-vs-0.2.11-256k-dflash2-b2.json`、`results/compare-0.2.11-dflash2-b1-vs-b2.json` |
| 2026-11-08 | 0.2.11 → 0.2.12（engine 0.1.57 → 0.1.58，256K，DFlash2） | 配对均差 +0.91 tok/s，**p=0.56 不显著**（中位 116.4 → 118.5）；prefill 2843.5 → 2868.7（+0.9%，噪声内）；专家槽位 4377 → 4376。与 0.2.11 等价。tuned DFlash2 要求 ≥12000 槽，本机 4376 不适用，也未下载。数据：`results/0.2.11-256k-dflash2-b2-20261106-171901.json`、`results/0.2.12-256k-dflash2-20261108-193013.json`、`results/compare-0.2.11-dflash2-b2-vs-0.2.12-256k-dflash2.json` |
| 2026-10-30 | `--lookup-chain 2` A/B（0.2.8，同版本） | 对同配置第二臂 **+0.74 tok/s，p=0.56 不显著**；首轮看似 +3.59（p=0.039），实为顺序偏差（同配置 b1→b2 +2.85，p=0.073）。数据：`results/0.2.8-256k-b2-20261030-102330.json`、`results/0.2.8-256k-lookup2-20261030-102138.json`、`results/compare-0.2.8-b2-vs-lookup2.json`、`results/compare-0.2.8-b1-vs-b2.json` |
| 2026-10-21 | 专家画像 A/B（engine 0.1.46） | 学习版画像的收益集中在**重启后的头两个请求**：命中率 +3.7pp / +1.9pp（6/6 完全分离，符号检验 p=0.031）；第 3 个请求起差异消失（自适应层已在内存里学到同样的东西）。decode 全程中位数 +6~+10 tok/s，方向一致但单请求方差大，未达显著。成本是一个 192 KB 文件 → 保留 |

> KVA 长 prompt A/B 不在标准 bench 协议内（需要 14K/30K 冷读并确认 `cache_n=0`），方法与本机结果见 `docs/strata-tuning.md` 的「KVA A/B」节；原始数据：`results/kva-20261028-off1.json`、`results/kva-20261028-on.json`、`results/kva-20261028-off2.json`。
