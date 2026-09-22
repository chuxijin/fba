# -*- coding: utf-8 -*-
"""
按 2026 年 9 月 25 日起的工作日（跳过周六、周日及国庆长假）
将 50 份特训题卡精确匹配到每个工作日，并建立结构化归档目录与排期总表
"""

import datetime
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "backend" / "output" / "50_days_pack"
TARGET_DIR = PROJECT_ROOT / "backend" / "output" / "行测速算50天特训_9月25日起工作日打卡"

WEEK_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

def generate_schedule(start_date: datetime.date, total_days: int = 50) -> list[dict]:
    """生成工作日排期表（跳过周六周日与国庆黄金周 10.1~10.7）"""
    schedule = []
    curr = start_date
    day_idx = 0

    while day_idx < total_days:
        # 国庆长假（10月1日~10月7日）
        is_national_holiday = (curr.month == 10 and 1 <= curr.day <= 7)
        # 周末（周六、周日）
        is_weekend = curr.weekday() >= 5

        if not is_weekend and not is_national_holiday:
            day_idx += 1
            schedule.append({
                "day_idx": day_idx,
                "date": curr,
                "date_str": curr.strftime("%Y-%m-%d"),
                "month_str": f"{curr.month:02d}月",
                "weekday_str": WEEK_NAMES[curr.weekday()],
                "src_pdf": SRC_DIR / f"Day_{day_idx:02d}.pdf",
                "target_filename": f"{curr.strftime('%Y-%m-%d')}_{WEEK_NAMES[curr.weekday()]}_Day{day_idx:02d}.pdf",
            })
        curr += datetime.timedelta(days=1)

    return schedule


def organize():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    start_date = datetime.date(2026, 9, 25)
    schedule = generate_schedule(start_date, total_days=50)

    # 月份子目录映射
    month_dirs = {
        "09月": TARGET_DIR / "01_九月份打卡(9.25~9.30)",
        "10月": TARGET_DIR / "02_十月份打卡(10.08~10.30)",
        "11月": TARGET_DIR / "03_十一月份打卡(11.02~11.30)",
        "12月": TARGET_DIR / "04_十二月份打卡(12.01~12.10)",
    }

    for md in month_dirs.values():
        md.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    # 复制与分发
    for item in schedule:
        src = item["src_pdf"]
        if not src.exists():
            print(f"[!] 源文件不存在: {src}")
            continue

        target_name = item["target_filename"]
        # 1. 复制到月份子文件夹
        m_key = item["month_str"]
        dest_month = month_dirs[m_key] / target_name
        shutil.copyfile(src, dest_month)

        # 2. 根目录也放一份按日期平铺的完整清单
        dest_flat = TARGET_DIR / target_name
        shutil.copyfile(src, dest_flat)
        copied_count += 1

    # 附带 Day 00 作为“预热自测”放在根目录
    src_day00 = SRC_DIR / "Day_00.pdf"
    if src_day00.exists():
        shutil.copyfile(src_day00, TARGET_DIR / "2026-09-24_周四_Day00_预热自测卷.pdf")

    # 生成排期汇总 Markdown 索引文件
    md_content = [
        "# 公考行测提速专项突破 · 50天工作日打卡完整排期表",
        "",
        "> **排期规则**：以 2026 年 9 月 25 日起算，跳过每周六、周日双休以及十一国庆黄金周（10.1~10.7）。",
        f"> **总周期跨度**：**{schedule[0]['date_str']}（{schedule[0]['weekday_str']}）** 至 **{schedule[-1]['date_str']}（{schedule[-1]['weekday_str']}）**，整整排到了 **12 月 10 日**！",
        "",
        "## 一、 各月份排期统计",
        f"- **09 月（起步强化）**：共 4 天（Day 01 ~ Day 04）",
        f"- **10 月（国庆后攻坚）**：共 17 天（Day 05 ~ Day 21）",
        f"- **11 月（进阶提速）**：共 21 天（Day 22 ~ Day 42）",
        f"- **12 月（冲刺收官）**：共 8 天（Day 43 ~ Day 50）",
        f"- **累计有效工作日**：整整 **50 个工作日**",
        "",
        "## 二、 每日详细打卡清单",
        "",
        "| 打卡天数 | 日期 | 星期 | 对应题卡文件 | 建议用时 | 题量与题型配置 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for item in schedule:
        md_content.append(
            f"| **第 {item['day_idx']:02d} 天** | {item['date_str']} | {item['weekday_str']} | `{item['target_filename']}` | 31 分钟 | 基础计算50题 + 基期量4题 + 增长量4题 + 上下立体分数比大小4题 (全62题) |"
        )

    readme_path = TARGET_DIR / "每日打卡排期总表.md"
    readme_path.write_text("\n".join(md_content), encoding="utf-8")
    print(f"[✓] 成功匹配并分发 {copied_count} 份题卡至: {TARGET_DIR}")
    print(f"[✓] 已生成排期索引表: {readme_path}")
    print(f"[✓] 50天排期结果: 从 {schedule[0]['date_str']} 持续到 {schedule[-1]['date_str']}")

if __name__ == "__main__":
    organize()
