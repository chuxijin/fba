# -*- coding: utf-8 -*-
"""
按照用户的极简结构重构目录：
1. 目标总文件夹：backend/output/资料分析训练_50天
2. 里面直接平铺 50 个按工作日命名的文件夹（跳过周末与十一国庆），例如：
   - 09月25日_资料分析训练/09月25日_资料分析训练.pdf
   - 09月28日_资料分析训练/09月28日_资料分析训练.pdf
   ...
   - 12月10日_资料分析训练/12月10日_资料分析训练.pdf
3. 彻底去掉多余的“月份”、“每周”等多层嵌套，极简纯粹。
"""

import datetime
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "backend" / "output" / "50_days_pack"
TARGET_ROOT = PROJECT_ROOT / "backend" / "output" / "50天训练"

WEEK_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

def generate_schedule(start_date: datetime.date, total_days: int = 50) -> list[dict]:
    """生成 50 个工作日排期（跳过周六周日与国庆黄金周 10.1~10.7）"""
    schedule = []
    curr = start_date
    day_idx = 0

    while day_idx < total_days:
        is_national_holiday = (curr.month == 10 and 1 <= curr.day <= 7)
        is_weekend = curr.weekday() >= 5

        if not is_weekend and not is_national_holiday:
            day_idx += 1
            # 文件夹纯日期：如 09月25日
            folder_name = f"{curr.month:02d}月{curr.day:02d}日"
            # 文件名保留资料分析训练：如 09月25日_资料分析训练.pdf
            file_name = f"{curr.month:02d}月{curr.day:02d}日_资料分析训练.pdf"
            schedule.append({
                "day_idx": day_idx,
                "date": curr,
                "folder_name": folder_name,
                "file_name": file_name,
                "src_pdf": SRC_DIR / f"Day_{day_idx:02d}.pdf",
            })
        curr += datetime.timedelta(days=1)

    return schedule


def run():
    # 清理并重建目标根目录
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    start_date = datetime.date(2026, 9, 25)
    schedule = generate_schedule(start_date, total_days=50)

    for item in schedule:
        src = item["src_pdf"]
        if not src.exists():
            print(f"[!] 未找到源文件: {src}")
            continue

        # 创建当天的独立子文件夹：如 09月25日_资料分析训练
        day_folder = TARGET_ROOT / item["folder_name"]
        day_folder.mkdir(parents=True, exist_ok=True)

        # 将对应的 PDF 复制进去，并重命名为 09月25日_资料分析训练.pdf
        dest_pdf = day_folder / item["file_name"]
        shutil.copyfile(src, dest_pdf)

    print(f"[✓] 成功创建 {len(schedule)} 个每日文件夹！")
    print(f"    - 首个文件夹: {schedule[0]['folder_name']}")
    print(f"    - 最后一个文件夹: {schedule[-1]['folder_name']}")
    print(f"    - 存放目录: {TARGET_ROOT}")

    # 同时清理之前那个复杂的“行测速算50天特训_9月25日起工作日打卡”文件夹，避免目录混乱冗余
    old_complex_dir = PROJECT_ROOT / "backend" / "output" / "行测速算50天特训_9月25日起工作日打卡"
    if old_complex_dir.exists():
        shutil.rmtree(old_complex_dir)
        print(f"[✓] 已清理旧的复杂多层嵌套目录: {old_complex_dir.name}")

if __name__ == "__main__":
    run()
