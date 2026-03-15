"""
wave_runner.py - 防风控随机分波签到调度器

策略：
  - 全部账号以"今天日期"为随机种子进行洗牌，保证同一天两波使用相同的排列
  - 上午波 (wave=1)：取前半部分账号
  - 下午波 (wave=2)：取后半部分账号
  - 每个账号间插入 15~45 分钟随机延迟，确保总时长 < 5.5 小时
  - 每次仅向 checkin.py 传入单账号 JSON，不修改 checkin.py 逻辑
"""

from __future__ import annotations

import datetime
import json
import os
import random
import subprocess
import sys
import time
from typing import Any, cast


# ── 时间安全常数 ────────────────────────────────────────────────────
# GitHub Actions 强制上限 6 小时 = 360 分钟
# 预留 30 分钟安全垫 → 每波调度预算 = 330 分钟
# 单账号执行耗时（含 Playwright WAF）保守估计 ≤ 8 分钟
# 7 账号最差情况：6 × MAX_DELAY_MIN + 7 × 8 = 6 × 40 + 56 = 296 分钟 ≤ 330 ✅
MIN_DELAY_MIN = 15  # 账号间最短等待（分钟）
MAX_DELAY_MIN = 40  # 账号间最长等待（分钟）


def get_wave() -> int:
    """
    波次判断优先级（从高到低）：

    1. WAVE_INPUT  ← 手动触发时用户通过下拉框选择（'1' 或 '2'）
    2. WAVE_SCHEDULE ← 定时触发时 GitHub 传入的 cron 表达式
       - '30 1 * * *' → 1（上午波）
       - '30 7 * * *' → 2（下午波）
    3. UTC 当前小时 ← 兜底回退（UTC < 7 → 1，UTC ≥ 7 → 2）

    ⚠️ 注意：同一天内无论触发多少次，只要波次相同，
    账号列表完全一致（由日期随机种子决定），不会换人。
    """
    # 1. 手动触发：用户下拉选择
    wave_input = os.environ.get("WAVE_INPUT", "").strip()
    if wave_input in ("1", "2"):
        return int(wave_input)

    # 2. 定时触发：通过 cron 表达式判断
    schedule = os.environ.get("WAVE_SCHEDULE", "").strip()
    if schedule == "30 1 * * *":
        return 1
    elif schedule == "30 7 * * *":
        return 2

    # 3. 兜底：按 UTC 当前小时自动判断
    utc_hour = datetime.datetime.now(datetime.timezone.utc).hour
    return 1 if utc_hour < 7 else 2


def load_accounts() -> list[dict]:
    """从环境变量读取并解析账号列表。"""
    raw = os.environ.get("ANYROUTER_ACCOUNTS", "").strip()
    if not raw:
        print("❌ 错误：未在环境变量 ANYROUTER_ACCOUNTS 中检测到账号配置", flush=True)
        sys.exit(1)
    try:
        accounts = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ 账号 JSON 解析失败：{e}", flush=True)
        sys.exit(1)
    if not isinstance(accounts, list) or len(accounts) == 0:
        print("❌ 错误：ANYROUTER_ACCOUNTS 必须是非空 JSON 数组", flush=True)
        sys.exit(1)
    return accounts


def select_accounts(accounts: list[Any], wave: int) -> list[Any]:
    """
    使用日期作为随机种子，对账号列表洗牌后按波次分割。
    同一天内两波使用相同的排列，因此账号严格不重叠。
    """
    today = datetime.date.today().isoformat()  # e.g. "2026-03-15"
    rng = random.Random(today)
    shuffled: list[Any] = list(accounts)
    rng.shuffle(shuffled)

    total = len(shuffled)
    split = (total + 1) // 2  # 奇数时上午波多取一个

    if wave == 1:
        return cast(list[Any], shuffled[:split])
    else:
        return cast(list[Any], shuffled[split:])


def run_checkin_for(account: dict[str, Any]) -> int:
    """以单账号调用 checkin.py，返回退出码。"""
    env = os.environ.copy()
    env["ANYROUTER_ACCOUNTS"] = json.dumps([account], ensure_ascii=False)
    result = subprocess.run(["uv", "run", "checkin.py"], env=env)  # noqa: S603, S607
    return result.returncode


def main() -> None:  # noqa: C901
    wave = get_wave()
    wave_label = "上午场 ☀️" if wave == 1 else "下午场 🌇"

    print(f"{'=' * 50}", flush=True)
    print(f"🌊 AnyRouter 防风控随机签到 — {wave_label} (波次 {wave})", flush=True)
    print(f"🕐 当前 UTC 时间：{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    accounts = load_accounts()
    selected = select_accounts(accounts, wave)

    today = datetime.date.today().isoformat()
    print(f"📋 总账号数：{len(accounts)}，本波分配：{len(selected)} 个（随机种子日期：{today}）", flush=True)
    print(f"⏱  账号间随机延迟范围：{MIN_DELAY_MIN}~{MAX_DELAY_MIN} 分钟", flush=True)
    print("=" * 50, flush=True)

    failed_accounts: list[str] = []

    for i, account in enumerate(selected):  # type: ignore[var-annotated]
        name = account.get("name", f"Account {i + 1}")

        if i > 0:
            wait_sec = random.randint(MIN_DELAY_MIN * 60, MAX_DELAY_MIN * 60)
            wait_min, wait_s = divmod(wait_sec, 60)
            print(f"\n⏳ 防风控随机等待 {wait_min} 分 {wait_s} 秒……", flush=True)
            time.sleep(wait_sec)

        print(f"\n{'─' * 40}", flush=True)
        print(f"👉 [{i + 1}/{len(selected)}] 正在签到：{name}", flush=True)
        print(f"{'─' * 40}", flush=True)

        exit_code = run_checkin_for(account)
        if exit_code != 0:
            print(f"⚠️  账号「{name}」签到异常，退出码：{exit_code}", flush=True)
            failed_accounts.append(name)
        else:
            print(f"✅ 账号「{name}」签到完成", flush=True)

    print(f"\n{'=' * 50}", flush=True)
    print(f"🏁 本波次签到结束 | 成功：{len(selected) - len(failed_accounts)} | 失败：{len(failed_accounts)}", flush=True)
    if failed_accounts:
        print(f"❌ 失败账号：{', '.join(failed_accounts)}", flush=True)
    print("=" * 50, flush=True)

    # 有账号失败时以非零退出码报告，让 GitHub Actions 标记为失败
    if failed_accounts:
        sys.exit(1)


if __name__ == "__main__":
    main()
