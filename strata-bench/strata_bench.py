#!/usr/bin/env python3
"""Strata 标准化测试工具（bench / profile-ab / compare）。

协议（与本机 2026-10 起的所有 Strata 测量一致）：
  重启容器 → 3 条预热请求 → 3 轮 ×（5 个不同 prompt × 200 token + 1 条 5000 token prefill）
  → 取 15 个 decode 样本的中位数；prefill 单独统计（由输入 token 决定，可跨版本比）。

为什么必须配对比较：Strata 是推理模型，任何影响专家计算的改动都会改变浮点求和顺序，
近平分叉 → 思考轨迹不同，不同文本的 per-token 代价相差可达数个百分点。跨配置直接比
decode tok/s 会得出假结论（历史上因此得出过 +7.4%、+3.9% 两个错误结论）。

用法：
  strata_bench.py bench       --label 0.2.1            # 跑一轮基准
  strata_bench.py profile-ab  --rounds 3               # 专家画像 A/B（交错顺序）
  strata_bench.py compare     a.json b.json            # 配对比较 + 置换检验
"""
from __future__ import annotations

import argparse, json, os, random, shutil, statistics, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime

# 仓库定位：<repo>/strata-bench/strata_bench.py → 仓库根目录
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 固定测试集

PROMPTS = [
    ("中文技术问答",
     "解释一下 MoE（混合专家）模型里「专家路由」和「专家缓存」分别解决什么问题，为什么显存大小会直接决定推理速度。"),
    ("英文代码理解",
     "Explain what this Python function does and where it can fail: "
     "def group(items, key=lambda x: x['k']): out = {}; "
     "for it in items: out.setdefault(key(it), []).append(it); return out. "
     "Also suggest two edge cases to test."),
    ("中文代码审查",
     "请审查下面这段 Python 代码，指出并发问题并给出改法：\n"
     "import threading\ncache = {}\nlock = threading.Lock()\n"
     "def get(k):\n    if k not in cache:\n        cache[k] = compute(k)\n    return cache[k]\n"
     "def worker():\n    for i in range(100): get(i)\n"
     "解释为什么加锁也可能不够。"),
    ("英文通用问答",
     "What are the main trade-offs between prefetching and demand paging in a memory-mapped file system, "
     "and when does one clearly win? Answer in a short list."),
    ("中文长文摘要",
     "请把下面这段话压缩成三条要点：\n"
     "混合专家模型把每个 token 路由到少量激活的专家上，其余专家权重常驻内存或磁盘。"
     "推理时若目标专家不在显存，需要从内存经 PCIe 搬到显卡，或退回 CPU 计算，两者都慢。"
     "因此显卡能常驻多少专家，直接决定了每次前向的成本；把路由最频繁的专家排在前面，"
     "命中率就会显著提高，这正是专家画像要解决的问题。"),
]
PRE = ("下面是一段用于测试长上下文预读速度的重复文本，请只回复“收到”两个字。\n" +
       "在分布式系统里，缓存失效、消息乱序、幂等设计是三个彼此纠缠的问题。"
       "缓存失效决定了读到的是不是旧数据，消息乱序决定了操作是否还能按预期生效，"
       "而幂等设计决定了重试是否安全。工程上常见的做法是用版本号或时间戳做乐观校验，"
       "把重放窗口限制在可控范围内，并为每个副作用操作带上唯一的幂等键。"
       "这样即使上游重复投递，下游也能识别出重复并安全丢弃。\n") * 40
WARM = "用一句话说说什么是向量数据库。"

# ---------------------------------------------------------------- 客户端


class Client:
    def __init__(self, url="http://127.0.0.1:8089", key_file=None, key=None, model=None):
        self.url = url.rstrip("/")
        self.key = key if key is not None else (open(key_file).read().strip() if key_file else "")
        self.model = model
        self._no_auth = False          # 旧版服务端不接受 key 时自动降级

    def _req(self, path, body=None, timeout=900):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.key and not self._no_auth:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url + path, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def call(self, path, body=None, timeout=900):
        try:
            return self._req(path, body, timeout)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and not self._no_auth:
                self._no_auth = True       # 服务端不认这个头：去掉再试
                return self._req(path, body, timeout)
            raise

    def models(self):
        return self.call("/v1/models", timeout=10)

    def metrics(self):
        return self.call("/metrics", timeout=30)

    def chat(self, prompt, max_tokens, temperature=0.0):
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": temperature, "stream": False}
        return self.call("/v1/chat/completions", body)

    def wait_ready(self, limit=600):
        t0 = time.time()
        while time.time() - t0 < limit:
            try:
                if self.models().get("data"):
                    return time.time() - t0
            except Exception:
                pass
            time.sleep(2)
        raise RuntimeError("服务端在超时内没就绪")


def med(v):
    v = [x for x in v if isinstance(x, (int, float))]
    return round(statistics.median(v), 2) if v else None


def engine_info(cli):
    try:
        e = cli.metrics().get("engine", {})
    except Exception:
        return {}
    keys = ("version", "model", "expert_slots", "expert_cache_mib", "pool_workers",
            "vram_free_mib", "kv", "max_context", "vram_elastic", "prefill_cap")
    return {k: e.get(k) for k in keys}


def last_request(cli):
    m = cli.metrics()
    reqs = m.get("requests") or []
    return (reqs[0] if reqs else {}), m.get("engine", {})


# ---------------------------------------------------------------- bench

def cmd_bench(a):
    cli = Client(a.url, a.key_file, a.key, a.model)
    if not a.model:
        cli.model = cli.models()["data"][0]["id"]
    if a.restart:
        subprocess.run(["docker", "restart", a.container], capture_output=True)
    t = cli.wait_ready()
    print(f"服务端就绪 {t:.0f}s（model={cli.model}）", flush=True)
    for _ in range(a.warmup):
        cli.chat(WARM, 64)
    print(f"预热 {a.warmup} 条完成", flush=True)

    decode, prefill, rows = [], [], []
    for rnd in range(1, a.rounds + 1):
        for name, p in PROMPTS:
            cli.chat(p, a.max_tokens)
            r, _ = last_request(cli)
            decode.append(r.get("decode_tok_s"))
            rows.append({"round": rnd, "name": name, "decode": r.get("decode_tok_s"),
                         "hit": r.get("hit_rate"), "out": r.get("output_tokens"),
                         "prompt_tokens": r.get("prompt_tokens")})
            print(f"  轮{rnd} {name}: decode={r.get('decode_tok_s')} hit={r.get('hit_rate')}", flush=True)
        cli.chat(PRE, 16)
        r, _ = last_request(cli)
        pm = (r.get("prompt_ms") or 0) / 1000.0
        pr = round((r.get("prompt_total") or 0) / pm, 1) if pm > 0 else None
        prefill.append(pr)
        print(f"  轮{rnd} prefill: {r.get('prompt_total')} tok / {r.get('prompt_ms')} ms -> {pr} tok/s", flush=True)

    out = {"label": a.label, "time": datetime.now().isoformat(timespec="seconds"),
           "model": cli.model, "url": cli.url, "rounds": a.rounds, "max_tokens": a.max_tokens,
           "decode": decode, "prefill": prefill, "rows": rows, "engine": engine_info(cli)}
    print(f"\ndecode 样本 {len(decode)} 个，中位数 = {med(decode)}，均值 = {round(statistics.mean(decode),2)}")
    print(f"prefill 中位数 = {med(prefill)} tok/s")
    print("引擎:", out["engine"])
    save(out, a.out)
    return out


# ---------------------------------------------------------------- profile A/B

def cmd_profile_ab(a):
    """专家画像 A/B：两臂只差「启动时有没有学习版画像文件」。交错顺序抵消漂移。"""
    cli = Client(a.url, a.key_file, a.key, a.model)
    if not a.model:
        cli.model = cli.models()["data"][0]["id"]
    if not os.path.exists(a.profile_backup):
        shutil.copyfile(a.profile, a.profile_backup)
    order = a.order or (["A", "B", "B", "A", "A", "B"] if a.rounds == 3 else None)
    if not order:
        half = ["A"] * a.rounds + ["B"] * a.rounds
        order = half[:len(half)//2] + half[len(half)//2:][::-1]
    rows = []
    for idx, arm in enumerate(order, 1):
        subprocess.run(["docker", "stop", "-t", "120", a.container], capture_output=True)
        if arm == "A":
            shutil.copyfile(a.profile_backup, a.profile)
        elif os.path.exists(a.profile):
            os.remove(a.profile)
        subprocess.run(["docker", "start", a.container], capture_output=True)
        t = cli.wait_ready()
        used = "学习版" if arm == "A" else "官方基线"
        for i in range(1, a.reqs + 1):
            cli.chat(PROMPTS[0][1], 96)
            r, _ = last_request(cli)
            rows.append({"order": idx, "arm": used, "req": i, "hit": r.get("hit_rate"),
                         "decode": r.get("decode_tok_s"), "first_tok": r.get("first_engine_token_s")})
            print(f"  #{idx} [{used}] req{i}: hit={r.get('hit_rate')} decode={r.get('decode_tok_s')}", flush=True)
        print(f"  #{idx} [{used}] 装载 {t:.0f}s", flush=True)
    # 收尾：恢复学习版
    shutil.copyfile(a.profile_backup, a.profile)
    subprocess.run(["docker", "restart", a.container], capture_output=True)
    cli.wait_ready()

    out = {"label": a.label, "time": datetime.now().isoformat(timespec="seconds"),
           "test": "profile-ab", "order": order, "rows": rows}
    print("\n=== 分位中位数 ===")
    for arm in ("学习版", "官方基线"):
        sel = [r for r in rows if r["arm"] == arm]
        for pos in range(1, a.reqs + 1):
            s = [r for r in sel if r["req"] == pos]
            if not s:
                continue
            hits = [r["hit"] for r in s]
            sep = "完全分离" if min(hits) > max([r["hit"] for r in
                  [x for x in rows if x["arm"] != arm and x["req"] == pos]] or [1]) else ""
            print(f"{arm} 第{pos}个请求: hit={med(hits)} ({', '.join(f'{h:.3f}' for h in hits)}) {sep} "
                  f"decode={med([r['decode'] for r in s])}")
    save(out, a.out)
    return out


# ---------------------------------------------------------------- compare

def cmd_compare(a):
    A = json.load(open(a.first))
    B = json.load(open(a.second))
    da, db = A["decode"], B["decode"]
    # 按 (轮次, prompt 名) 配对
    key_a = {(r["round"], r["name"]): r["decode"] for r in A["rows"]}
    key_b = {(r["round"], r["name"]): r["decode"] for r in B["rows"]}
    pairs = {k: (key_a[k], key_b[k]) for k in key_a if k in key_b}
    diffs = [y - x for x, y in pairs.values()]      # B - A
    n = len(diffs)
    mean_d = statistics.mean(diffs)
    # 置换检验（符号翻转，2^n 全枚举，n<=18 时可行）
    if n <= 18:
        cnt = 0
        for mask in range(2 ** n):
            s = sum(d if (mask >> i) & 1 else -d for i, d in enumerate(diffs))
            if abs(s) >= abs(sum(diffs)):
                cnt += 1
        p = cnt / (2 ** n)
    else:
        p = None
    pos = sum(1 for d in diffs if d > 0)
    print(f"A = {A.get('label')}  ({A.get('time')})")
    print(f"B = {B.get('label')}  ({B.get('time')})")
    print(f"配对数 {n}（B 更高 {pos} 个，A 更高 {n-pos} 个）")
    print(f"A 中位 {med(da)} tok/s，B 中位 {med(db)} tok/s，差（B-A） {med(db)-med(da):+.2f}")
    print(f"配对均值差（B-A） {mean_d:+.2f} tok/s，置换检验 p = {p}")
    print("  逐对明细：")
    for (rd, nm), (x, y) in sorted(pairs.items()):
        print(f"    轮{rd} {nm:<14} A {x:7.1f}  B {y:7.1f}  Δ(B-A) {y-x:+7.1f}")
    pa, pb = A.get("prefill") or [], B.get("prefill") or []
    if pa and pb:
        print(f"prefill：A {med(pa)} tok/s，B {med(pb)} tok/s")
    print("引擎 A:", A.get("engine"))
    print("引擎 B:", B.get("engine"))
    if a.out:
        save({"label": f"compare:{A.get('label')} vs {B.get('label')}",
              "time": datetime.now().isoformat(timespec="seconds"), "test": "compare",
              "pairs": n, "mean_diff_B_minus_A": mean_d, "p": p,
              "median_a": med(da), "median_b": med(db),
              "prefill_a": med(pa), "prefill_b": med(pb)}, a.out)
    return {"p": p, "mean_diff": mean_d}


# ---------------------------------------------------------------- 结果落盘

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def save(obj, out):
    os.makedirs(RESULTS, exist_ok=True)
    if not out:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = os.path.join(RESULTS, f"{obj.get('label','run').replace('/','_')}-{stamp}.json")
    with open(out, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    # 同一份内容再存一份 markdown 摘要，方便人看
    md = os.path.splitext(out)[0] + ".md"
    with open(md, "w") as f:
        f.write(f"# {obj.get('label')}\n\n时间：{obj.get('time')}\n\n")
        if obj.get("test") == "profile-ab":
            f.write("| 序 | 臂 | 第几个请求 | hit | decode tok/s |\n|---|---|---|---|---|\n")
            for r in obj["rows"]:
                f.write(f"| {r['order']} | {r['arm']} | {r['req']} | {r['hit']} | {r['decode']} |\n")
        elif obj.get("test") == "compare":
            f.write(f"- 配对数：{obj.get('pairs')}\n")
            f.write(f"- 配对均值差（B-A）：**{obj.get('mean_diff_B_minus_A'):+.2f}** tok/s，置换检验 p = {obj.get('p')}\n")
            f.write(f"- 中位数：A {obj.get('median_a')} / B {obj.get('median_b')} tok/s\n")
            f.write(f"- prefill：A {obj.get('prefill_a')} / B {obj.get('prefill_b')} tok/s\n")
        else:
            f.write(f"- decode 样本：{obj.get('decode')}\n")
            f.write(f"- decode 中位数：**{med(obj.get('decode', []))}** tok/s\n")
            f.write(f"- prefill：{obj.get('prefill')}（中位 {med(obj.get('prefill', []))} tok/s）\n")
            f.write(f"- 引擎：{obj.get('engine')}\n")
    print(f"结果已写入 {out} 和 {md}")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--url", default="http://127.0.0.1:8089")
        sp.add_argument("--key-file", default=os.path.join(REPO, "strata-data", "state", "api-key"))
        sp.add_argument("--key", default=None)
        sp.add_argument("--model", default=None)
        sp.add_argument("--label", default="run")
        sp.add_argument("--out", default=None)

    b = sub.add_parser("bench", help="标准基准")
    common(b)
    b.add_argument("--rounds", type=int, default=3)
    b.add_argument("--warmup", type=int, default=3)
    b.add_argument("--max-tokens", type=int, default=200)
    b.add_argument("--container", default="strata")
    b.add_argument("--no-restart", dest="restart", action="store_false")
    b.set_defaults(restart=True, func=cmd_bench)

    ab = sub.add_parser("profile-ab", help="专家画像 A/B")
    common(ab)
    ab.add_argument("--rounds", type=int, default=3, help="每臂重启次数")
    ab.add_argument("--reqs", type=int, default=4, help="每次重启后发几个请求")
    ab.add_argument("--order", default=None, help='如 "A,B,B,A,A,B"，默认按 rounds 生成交错序')
    ab.add_argument("--container", default="strata")
    ab.add_argument("--profile", default=os.path.join(REPO, "strata-data", "config", "expert-profile-learned.bin"))
    ab.add_argument("--profile-backup", default="/tmp/opencode/profile-learned-backup.bin")
    ab.set_defaults(func=cmd_profile_ab)

    c = sub.add_parser("compare", help="配对比较两个结果文件")
    c.add_argument("first")
    c.add_argument("second")
    c.add_argument("--out", default=None)
    c.set_defaults(func=cmd_compare)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
