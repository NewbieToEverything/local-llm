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
| 2026-10-21 | 专家画像 A/B（engine 0.1.46） | 学习版画像的收益集中在**重启后的头两个请求**：命中率 +3.7pp / +1.9pp（6/6 完全分离，符号检验 p=0.031）；第 3 个请求起差异消失（自适应层已在内存里学到同样的东西）。decode 全程中位数 +6~+10 tok/s，方向一致但单请求方差大，未达显著。成本是一个 192 KB 文件 → 保留 |
