#!/usr/bin/env python3
"""Claude Code のローカルログ (~/.claude/projects/**/*.jsonl) からトークン消費を実測集計する。

標準ライブラリのみ。Windows / macOS / Linux で動く。ログを読むだけで何も書き換えない。

使い方:
  python claude_usage.py                      # 全期間、消費の大きい上位20セッション
  python claude_usage.py --since 2026-09-01   # 期間を絞る
  python claude_usage.py --top 50 --csv out.csv
  python claude_usage.py --root D:\\path\\to\\.claude\\projects

見方:
  entrypoint : cli = 手で起動した対話, sdk-cli = `claude -p` 等の非対話呼び出し
               (Codex など他ツールから呼ばれた場合はここに出やすい)
  指示数     : 人 (または呼び出し元) が送った実メッセージ数。tool_result は含まない
  最大文脈   : 1リクエストで読み込まれた文脈の最大トークン数 (履歴の長さの目安)
  5分超え    : 前のやり取りから5分以上空いた回数 (プロンプトキャッシュ失効の目安)
  重み付き   : 入力単価=1 として 出力5 / キャッシュ書込1.25 / キャッシュ読込0.1 で換算した
               API料金比の目安。サブスクの利用枠の計算式とは限らないので、
               セッション同士の「相対比較」にだけ使うこと。
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

W_IN, W_OUT, W_CW, W_CR = 1.0, 5.0, 1.25, 0.1
CACHE_TTL_SEC = 300


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_real_instruction(rec):
    """tool_result だけのユーザー行や、メタ行を除いた『実際の指示』か。"""
    if rec.get("isSidechain") or rec.get("isMeta"):
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip()
            for b in content
        )
    return False


class Session:
    def __init__(self, sid):
        self.sid = sid
        self.cwd = ""
        self.entrypoint = ""
        self.first = None
        self.last = None
        self.models = set()
        self.requests = {}  # (msg_id, req_id) -> usage dict (最大の output を採用)
        self.sub_requests = {}
        self.instructions = 0
        self.gaps = 0
        self._prev_ts = None
        self.files = set()

    def touch(self, ts):
        if ts is None:
            return
        if self.first is None or ts < self.first:
            self.first = ts
        if self.last is None or ts > self.last:
            self.last = ts

    def add_usage(self, key, usage, sidechain):
        bucket = self.sub_requests if sidechain else self.requests
        old = bucket.get(key)
        if old is None or usage["out"] >= old["out"]:
            bucket[key] = usage

    def totals(self, include_sub=True):
        t = dict(inp=0, out=0, cw=0, cr=0, turns=0, max_ctx=0)
        buckets = [self.requests] + ([self.sub_requests] if include_sub else [])
        for b in buckets:
            for u in b.values():
                t["inp"] += u["inp"]
                t["out"] += u["out"]
                t["cw"] += u["cw"]
                t["cr"] += u["cr"]
                t["turns"] += 1
                t["max_ctx"] = max(t["max_ctx"], u["inp"] + u["cw"] + u["cr"])
        t["weighted"] = W_IN * t["inp"] + W_OUT * t["out"] + W_CW * t["cw"] + W_CR * t["cr"]
        return t


def scan(root, since):
    sessions = {}
    nfiles = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, fn)
            nfiles += 1
            # サブエージェントのファイルは親セッションに合算する
            in_subdir = f"{os.sep}subagents{os.sep}" in path
            try:
                fh = open(path, "r", encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"読めない: {path} ({e})", file=sys.stderr)
                continue
            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    sid = rec.get("sessionId") or os.path.splitext(fn)[0]
                    ts = parse_ts(rec.get("timestamp"))
                    if since and ts and ts < since:
                        continue
                    s = sessions.get(sid)
                    if s is None:
                        s = sessions[sid] = Session(sid)
                    s.files.add(path)
                    s.touch(ts)
                    if rec.get("cwd") and not s.cwd:
                        s.cwd = rec["cwd"]
                    if rec.get("entrypoint") and not s.entrypoint:
                        s.entrypoint = rec["entrypoint"]

                    sidechain = bool(rec.get("isSidechain")) or in_subdir
                    rtype = rec.get("type")
                    if rtype == "user" and is_real_instruction(rec) and not in_subdir:
                        s.instructions += 1
                    if not sidechain and ts is not None and rtype in ("user", "assistant"):
                        if s._prev_ts and (ts - s._prev_ts).total_seconds() > CACHE_TTL_SEC:
                            s.gaps += 1
                        s._prev_ts = ts
                    if rtype == "assistant":
                        msg = rec.get("message") or {}
                        u = msg.get("usage")
                        if not isinstance(u, dict):
                            continue
                        if msg.get("model"):
                            s.models.add(msg["model"])
                        key = (msg.get("id") or rec.get("uuid"), rec.get("requestId"))
                        s.add_usage(
                            key,
                            dict(
                                inp=u.get("input_tokens") or 0,
                                out=u.get("output_tokens") or 0,
                                cw=u.get("cache_creation_input_tokens") or 0,
                                cr=u.get("cache_read_input_tokens") or 0,
                            ),
                            sidechain,
                        )
    return sessions, nfiles


def fmt(n):
    return f"{int(n):,}"


def short(path, n=34):
    p = path or "(不明)"
    return p if len(p) <= n else "…" + p[-(n - 1):]


def local(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(os.path.expanduser("~"), ".claude", "projects"))
    ap.add_argument("--since", help="YYYY-MM-DD 以降だけ集計")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--csv", help="全セッションをCSVに書き出す")
    ap.add_argument("--no-subagents", action="store_true", help="サブエージェント分を除く")
    args = ap.parse_args()

    since = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").astimezone().astimezone(timezone.utc)
    if not os.path.isdir(args.root):
        sys.exit(f"ログフォルダがない: {args.root}  (--root で指定)")

    sessions, nfiles = scan(args.root, since)
    rows = []
    for s in sessions.values():
        t = s.totals(include_sub=not args.no_subagents)
        if t["turns"] == 0 and s.instructions == 0:
            continue
        rows.append((s, t))
    if not rows:
        sys.exit("集計対象なし")
    rows.sort(key=lambda r: r[1]["weighted"], reverse=True)

    grand = defaultdict(float)
    for _, t in rows:
        for k in ("inp", "out", "cw", "cr", "turns", "weighted"):
            grand[k] += t[k]

    print(f"ファイル {nfiles} 個 / セッション {len(rows)} 件 / 期間 {args.since or '全期間'}")
    print(
        f"合計: 出力 {fmt(grand['out'])} | 新規入力 {fmt(grand['inp'])} | "
        f"キャッシュ書込 {fmt(grand['cw'])} | キャッシュ読込 {fmt(grand['cr'])} | "
        f"リクエスト {fmt(grand['turns'])}\n"
    )

    print(f"== 重み付き消費の上位 {args.top} セッション ==")
    hdr = f"{'開始':16} {'entry':9} {'指示':>4} {'req':>5} {'出力':>10} {'CR(読込)':>13} {'最大文脈':>9} {'5分超':>4} {'占有%':>5}  {'フォルダ':34} 会話ID"
    print(hdr)
    for s, t in rows[: args.top]:
        share = 100 * t["weighted"] / grand["weighted"] if grand["weighted"] else 0
        print(
            f"{local(s.first):16} {s.entrypoint[:9]:9} {s.instructions:>4} {t['turns']:>5} "
            f"{fmt(t['out']):>10} {fmt(t['cr']):>13} {fmt(t['max_ctx']):>9} {s.gaps:>4} {share:>5.1f}  "
            f"{short(s.cwd):34} {s.sid[:8]}"
        )

    print("\n== entrypoint 別 (誰が起動したかの手がかり) ==")
    by_ep = defaultdict(lambda: defaultdict(float))
    for s, t in rows:
        e = by_ep[s.entrypoint or "(不明)"]
        e["n"] += 1
        e["instr"] += s.instructions
        e["out"] += t["out"]
        e["cr"] += t["cr"]
        e["weighted"] += t["weighted"]
    for k, e in sorted(by_ep.items(), key=lambda kv: -kv[1]["weighted"]):
        print(
            f"  {k:12} セッション {int(e['n']):>4}  指示 {int(e['instr']):>5}  出力 {fmt(e['out']):>12}  "
            f"CR {fmt(e['cr']):>14}  占有 {100 * e['weighted'] / grand['weighted']:.1f}%"
        )

    print("\n== フォルダ別 ==")
    by_cwd = defaultdict(lambda: defaultdict(float))
    for s, t in rows:
        e = by_cwd[s.cwd or "(不明)"]
        e["n"] += 1
        e["instr"] += s.instructions
        e["out"] += t["out"]
        e["weighted"] += t["weighted"]
    for k, e in sorted(by_cwd.items(), key=lambda kv: -kv[1]["weighted"])[:10]:
        per = e["out"] / e["instr"] if e["instr"] else 0
        print(
            f"  {short(k, 44):44} セッション {int(e['n']):>3}  指示 {int(e['instr']):>4}  "
            f"出力 {fmt(e['out']):>10} (指示1件あたり {fmt(per)})  占有 {100 * e['weighted'] / grand['weighted']:.1f}%"
        )

    print("\n== 日別 (セッション開始日ベース) ==")
    by_day = defaultdict(lambda: defaultdict(float))
    for s, t in rows:
        d = s.first.astimezone().strftime("%Y-%m-%d") if s.first else "-"
        by_day[d]["n"] += 1
        by_day[d]["out"] += t["out"]
        by_day[d]["weighted"] += t["weighted"]
    for d in sorted(by_day)[-14:]:
        e = by_day[d]
        print(f"  {d}  セッション {int(e['n']):>3}  出力 {fmt(e['out']):>10}  占有 {100 * e['weighted'] / grand['weighted']:.1f}%")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["session_id", "start", "end", "entrypoint", "cwd", "models", "instructions",
                        "requests", "output", "input", "cache_write", "cache_read", "max_context",
                        "gaps_over_5min", "weighted"])
            for s, t in rows:
                w.writerow([s.sid, local(s.first), local(s.last), s.entrypoint, s.cwd,
                            ";".join(sorted(s.models)), s.instructions, t["turns"], t["out"], t["inp"],
                            t["cw"], t["cr"], t["max_ctx"], s.gaps, round(t["weighted"])])
        print(f"\nCSV 出力: {args.csv}")


if __name__ == "__main__":
    main()
