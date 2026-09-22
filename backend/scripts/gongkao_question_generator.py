# -*- coding: utf-8 -*-
"""
公考行测速算与资料分析高质量题目生成引擎 (GongkaoQuestionGenerator)
特点：
1. 8 种核心题型严格按公考教研逻辑生成；
2. 增长率严格控制在 0.x% ~ 100% 之间，且与常见特征分数保持 3% ~ 10% 的硬核偏离度，杜绝直接套公式秒杀，强制截位直除与拆分法训练；
3. 分数大小比较定向构造：差分法、化同倍数法、首位直除法、反向变动四大经典模型，输出 LaTeX 上下式立体真分数；
4. 严格单向纯函数与随机种子控制，确保 50 份题目无重复、数据真实自然。
"""

import math
import random
from typing import Any, Tuple

# 常见特征分数百分比对照基准
FEATURE_RATES = [
    50.0, 33.3, 25.0, 20.0, 16.7, 14.3, 12.5, 11.1, 10.0, 9.1, 8.3, 7.7, 7.1, 6.7
]

def generate_offset_growth_rate(rng: random.Random) -> Tuple[float, str]:
    """
    生成与特征分数有 3% ~ 10% 偏离度的真实公考增长率
    确保：
    1. 范围在 0.8% ~ 85.0% 之间；
    2. 与任何特征分数的绝对差值都在 [2.8%, 10.0%] 之间（或更远）；
    3. 保留 1 位小数（如 13.8%、18.4%、22.5%、31.6% 等）。
    """
    for _ in range(100):
        # 模式 A (60%): 选取一个特征点，在距离其 3% ~ 8% 的区间生成
        if rng.random() < 0.6:
            base_f = rng.choice(FEATURE_RATES)
            offset = rng.uniform(3.0, 8.5)
            sign = 1 if rng.random() < 0.5 else -1
            rate = base_f + sign * offset
        # 模式 B (25%): 常见中高非特征区间 (28% ~ 75%)
        elif rng.random() < 0.85:
            rate = rng.uniform(28.0, 75.0)
        # 模式 C (15%): 低速增长微增区间 (1.5% ~ 5.5%)
        else:
            rate = rng.uniform(1.5, 5.5)

        rate = round(rate, 1)
        if rate < 0.8 or rate > 95.0:
            continue

        # 校验：检查是否与任意特征分数距离过近（必须大于 2.8%）
        min_dist = min(abs(rate - f) for f in FEATURE_RATES)
        if min_dist >= 2.8:
            return rate, f"{rate}%"

    # 保底安全值
    fallback = round(rng.uniform(17.5, 19.2), 1)
    return fallback, f"{fallback}%"


class GongkaoQuestionGenerator:
    """公考行测速算与资料分析单卷 62 题生成器"""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def gen_sec_a_tens_times_digit(self) -> list[Tuple[str, str]]:
        """(a) 10~19 乘以个位数 (10题)"""
        results = []
        used = set()
        while len(results) < 10:
            a = self.rng.randint(11, 19)
            b = self.rng.randint(3, 9)
            if (a, b) in used:
                continue
            used.add((a, b))
            ans = str(a * b)
            results.append((f"{a} × {b} =", ans))
        return results

    def gen_sec_b_three_times_digit(self) -> list[Tuple[str, str]]:
        """(b) 三位数乘以一位数 (10题，穿插乘5、补数与多进位)"""
        results = []
        used = set()
        while len(results) < 10:
            # 穿插一些接近整百（如 298, 396, 495）与常规三位数
            if len(results) % 3 == 0:
                hundred = self.rng.randint(2, 8) * 100
                diff = self.rng.randint(1, 6)
                a = hundred - diff
            else:
                a = self.rng.randint(125, 895)

            b = self.rng.randint(3, 9)
            if (a, b) in used:
                continue
            used.add((a, b))
            ans = str(a * b)
            results.append((f"{a} × {b} =", ans))
        return results

    def gen_sec_c_five_div_three(self) -> list[Tuple[str, str]]:
        """(c) 五位数除以三位数 (10题，考查截位直除试商与首位区分)"""
        results = []
        used = set()
        while len(results) < 10:
            b = self.rng.randint(132, 896)  # 除数 3 位
            # 商在 45 ~ 380 之间
            quotient = self.rng.uniform(45.0, 360.0)
            a = int(b * quotient)
            if a < 10000 or a > 99999 or b in used:
                continue
            used.add(b)
            # 保留 1 位小数或取整估算
            ans = f"{a / b:.2f}"
            results.append((f"{a} ÷ {b} =", ans))
        return results

    def gen_sec_d_three_sub_three(self) -> list[Tuple[str, str]]:
        """(d) 三位数的减法 (10题，穿插跨0退位与连续退位)"""
        results = []
        used = set()
        while len(results) < 10:
            # 确保 a > b，且差值有实际计算量
            if len(results) % 2 == 0:
                # 跨 0 退位（如 802, 704）
                a = self.rng.randint(4, 9) * 100 + self.rng.randint(1, 9)
            else:
                a = self.rng.randint(450, 985)

            b = self.rng.randint(145, a - 65)
            if (a, b) in used:
                continue
            used.add((a, b))
            ans = str(a - b)
            results.append((f"{a} - {b} =", ans))
        return results

    def gen_sec_e_three_add_three(self) -> list[Tuple[str, str]]:
        """(e) 三位数的加法 (10题，穿插连续进位与凑整)"""
        results = []
        used = set()
        while len(results) < 10:
            a = self.rng.randint(168, 785)
            b = self.rng.randint(156, 850)
            if (a, b) in used:
                continue
            used.add((a, b))
            ans = str(a + b)
            results.append((f"{a} + {b} =", ans))
        return results

    def gen_sec_f_base_period(self) -> list[Tuple[str, str]]:
        """(f) 给出现期和增长率，求基期量 (4题，偏离特征分数 3%~10%，强制截位直除)"""
        results = []
        for _ in range(4):
            # 现期 3000 ~ 65000（公考常见 4~5 位宏观数据）
            val = self.rng.randint(3200, 68000)
            rate_num, rate_str = generate_offset_growth_rate(self.rng)
            # 基期 = 现期 / (1 + r)
            r_dec = rate_num / 100.0
            base_val = round(val / (1.0 + r_dec), 1)
            # 若结果接近整数则取整，否则保留1位
            ans_str = f"{int(round(base_val))}" if abs(base_val - round(base_val)) < 0.05 else f"{base_val:.1f}"
            results.append((f"{val}    {rate_str}", ans_str))
        return results

    def gen_sec_g_increment(self) -> list[Tuple[str, str]]:
        """(g) 给出基期和增长率，求增长量 (4题，偏离特征分数 3%~10%，强制拆分与相乘)"""
        results = []
        for _ in range(4):
            val = self.rng.randint(2800, 56000)
            rate_num, rate_str = generate_offset_growth_rate(self.rng)
            # 增长量 = 基期 * r
            inc_val = round(val * (rate_num / 100.0), 1)
            ans_str = f"{int(round(inc_val))}" if abs(inc_val - round(inc_val)) < 0.05 else f"{inc_val:.1f}"
            results.append((f"{val}    {rate_str}", ans_str))
        return results

    def gen_sec_h_fraction_compare(self) -> list[Tuple[str, str]]:
        """
        (h) 分数大小比较 (4题，上下式立体真分数)
        四大定向技巧模型：
        1. 差分法模型：大分数减小分数得到差分数，差分数有明显区分；
        2. 化同/倍数法模型：分子呈接近 2 或 3 倍关系，放大后看分母；
        3. 直除首位模型：两分数首位试商不同，或首位相同次位差极大；
        4. 反向变动模型：分子大且分母小，直接判定。
        """
        results = []

        # 1. 差分法题型
        # 构造基准小分数 a2/b2 与 大分数 a1/b1
        b2 = self.rng.randint(2500, 7500)
        a2 = int(b2 * self.rng.uniform(0.12, 0.35))
        # 差分数 diff_a / diff_b
        diff_b = self.rng.randint(1200, 3500)
        # 让差分数比小分数大或小 30% 以上，极度适合差分法秒杀
        factor = self.rng.choice([1.35, 0.65])
        diff_a = int(diff_b * (a2 / b2) * factor)
        a1 = a2 + diff_a
        b1 = b2 + diff_b
        # 比较 a1/b1 与 a2/b2
        ans1 = "＞" if (a1 / b1) > (a2 / b2) else "＜"
        stem1 = rf"$\frac{{{a1}}}{{{b1}}}$    (     )    $\frac{{{a2}}}{{{b2}}}$"
        results.append((stem1, ans1))

        # 2. 化同/倍数法题型
        mul = self.rng.choice([2, 3])
        sub_b = self.rng.randint(2100, 4800)
        sub_a = self.rng.randint(180, 750)
        # 另一个分数的分子接近 sub_a * mul
        main_a = sub_a * mul + self.rng.randint(-5, 5)
        # 分母相对放大更多或更少
        shift = self.rng.choice([1.12, 0.88])
        main_b = int(sub_b * mul * shift)
        ans2 = "＞" if (sub_a / sub_b) > (main_a / main_b) else "＜"
        stem2 = rf"$\frac{{{sub_a}}}{{{sub_b}}}$    (     )    $\frac{{{main_a}}}{{{main_b}}}$"
        results.append((stem2, ans2))

        # 3. 直除首位题型
        den1 = self.rng.randint(3200, 8800)
        den2 = self.rng.randint(3200, 8800)
        # 一个首位是 2 或 3，另一个首位是 4 或 5
        r1 = self.rng.uniform(0.21, 0.28)
        r2 = self.rng.uniform(0.42, 0.53)
        if self.rng.random() < 0.5:
            r1, r2 = r2, r1
        num1 = int(den1 * r1)
        num2 = int(den2 * r2)
        ans3 = "＞" if (num1 / den1) > (num2 / den2) else "＜"
        stem3 = rf"$\frac{{{num1}}}{{{den1}}}$    (     )    $\frac{{{num2}}}{{{den2}}}$"
        results.append((stem3, ans3))

        # 4. 反向变动或特征微调题型
        b_base = self.rng.randint(4000, 8500)
        a_base = self.rng.randint(800, 2200)
        # 反向变动：一个分子大分母小，另一个分子小分母大
        del_a = self.rng.randint(120, 350)
        del_b = self.rng.randint(400, 950)
        ans4 = "＞"
        stem4 = rf"$\frac{{{a_base + del_a}}}{{{b_base - del_b}}}$    (     )    $\frac{{{a_base}}}{{{b_base}}}$"
        # 偶尔反转位置
        if self.rng.random() < 0.5:
            stem4 = rf"$\frac{{{a_base}}}{{{b_base}}}$    (     )    $\frac{{{a_base + del_a}}}{{{b_base - del_b}}}$"
            ans4 = "＜"
        results.append((stem4, ans4))

        return results

    def generate_day_payload_data(self, day_index: int) -> dict[str, Any]:
        """生成单日（Day XX）全套 62 题数据"""
        sec_a = self.gen_sec_a_tens_times_digit()
        sec_b = self.gen_sec_b_three_times_digit()
        sec_c = self.gen_sec_c_five_div_three()
        sec_d = self.gen_sec_d_three_sub_three()
        sec_e = self.gen_sec_e_three_add_three()
        sec_f = self.gen_sec_f_base_period()
        sec_g = self.gen_sec_g_increment()
        sec_h = self.gen_sec_h_fraction_compare()

        sections_def = [
            ("sec_a", "一、基础计算：10~19 乘以个位数", sec_a, "blank", "基础速算"),
            ("sec_b", "二、基础计算：三位数乘以一位数", sec_b, "blank", "基础速算"),
            ("sec_c", "三、基础计算：五位数除以三位数（截位直除）", sec_c, "blank", "截位直除"),
            ("sec_d", "四、基础计算：三位数的减法", sec_d, "blank", "基础速算"),
            ("sec_e", "五、基础计算：三位数的加法", sec_e, "blank", "基础速算"),
            ("sec_data_base", "六、资料分析 · 基期量计算特训（给出现期量与增长率，求基期量）", sec_f, "blank", "基期量"),
            ("sec_data_inc", "七、资料分析 · 增长量计算特训（给出基期量与增长率，求增长量）", sec_g, "blank", "增长量"),
            ("sec_compare", "八、资料分析 · 分数大小比较特训（在括号内填写 ＞ 或 ＜）", sec_h, "blank", "比大小"),
        ]

        return {
            "day": day_index,
            "title": f"公考行测提速专项突破 · 第 {day_index:02d} 天打卡",
            "subtitle": "核心速算强化 · 浮动增长率实战 · 分数极速直除比大小",
            "sections_def": sections_def,
        }
