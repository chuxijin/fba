#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse, parse_qs

from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import ListFilesParam, TransferParam
from backend.app.coulddrive.service.baidu.client import BaiduClient


def _ensure_abs(target_path: str) -> str:
    target_path = target_path.strip()
    if not target_path:
        return "/"
    if not target_path.startswith("/"):
        target_path = "/" + target_path
    return target_path


def _extract_pwd_from_link(link: str) -> str:
    try:
        parsed = urlparse(link)
        q = parse_qs(parsed.query)
        if "pwd" in q and q["pwd"]:
            return q["pwd"][0]
    except Exception:
        pass
    # 支持 "url|pwd" 组合
    if "|" in link:
        try:
            return link.split("|", 1)[1].strip()
        except Exception:
            return ""
    return ""


async def main() -> None:
    print("=== 百度网盘 链接转存交互式测试 ===")
    # 默认使用环境变量，否则回退为之前验证通过的完整 Cookie
    default_cookie = os.environ.get("BAIDU_COOKIE", "") or (
        "BIDUPSID=9A0F46EC76E423766C39C6C7B4F5F051; PSTM=1751510520; BAIDUID=9A0F46EC76E42376859F917A920CA8C2:FG=1; H_PS_PSSID=62325_63145_63584_63639_63646_63690_63693_63724_63711_63774_63810_63823; ZFY=zn1uAgPHliA8aHrVKN1UvKWxKzdtUf0kaIydhqKbIFU:C; BAIDUID_BFESS=9A0F46EC76E42376859F917A920CA8C2:FG=1; BDUSS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKDWZ2ig1mdoY; BDUSS_BFESS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKDWZ2ig1mdoY; PANWEB=1; Hm_lvt_0ba7bcf57b5e55fbfbab9a2750acdf3e=1751635591,1751686750,1751784493,1751784523; STOKEN=6aebe90a8c3a78e4c2ae396bffd38bc0ea01714f288632cbb0a44298addeabf9; Hm_lvt_182d6d59474cf78db37e0b2248640ea5=1753942909,1754214335,1754483537,1754549693; csrfToken=Jfm0lXypUB9YX5tG2IDYj3im; PANPSC=11710659305822854947%3AnHZOtuqy9asOmxlqtMELYFcS2d9ns3O5C61tf8CKQkgNjbYgPSAIMKUY4cQrI%2BJ7mkqHYt%2BNhjH42whq4mqbpONHiOwr%2ByPWOg9ifdcaUVf6tFIdG58v4x1SnoRAxu5fJlOfPZFHq36ck0T9AttkQZI6enfTG9RjNaEJrI5V%2Fed8Wde7ocAHCFvKX4DMNpv6FHFBPAHjbTFVFY6DiFPjb2Xs5TPgvEgZZyiEnGgQhUpH8Q8GquUrPqVYKwkVuBOyX2XlUsKRi0YmtM9d4zNnAx3eJYyVFsgjaZ6lcKGvWBM%3D; Hm_lvt_7a3960b6f067eb0085b7f96ff5e660b0=1753930217,1753942916,1754214379,1754921446; HMACCOUNT=796E4F7EA274F24E; BDCLND=it5JCKQ4OnRKAYrlLbj9QkHJHwJvJPDA%2BkyO16QKk2E%3D; Hm_lpvt_7a3960b6f067eb0085b7f96ff5e660b0=1754921450; ndut_fmt=5148C9BD52197A480C887492C961C3C0C4C33D1889533FB6861F7D21050E244E; ab_sr=1.0.1_NDg3ZjUyNjFmMzM5YWM3NmVmZDA0MmNkYjg1MmU1ZDFlNWUzYzU4NmM1ZGZlNzNlMmFjMWU4MGNhYmYyNWNlNTZkMTAyYTE3ZWJjZWNmODZjYjA0ZmE4MzA0MjYzZTRiYTU4MGNmNWM1ODI1YTNlODQwMTMyNzgxN2M1YTZjNmRlMDEyNGQ1Nzc4YzdlZGZmNWRmMGZmMTE2N2Y3NWYyM2MzOTFjYWFkYTAwYzBhNTRhYjc1ODBjNGRmYzdhODRj"
    )
    if not default_cookie:
        print("提示: 可设置环境变量 BAIDU_COOKIE 来覆盖默认 cookie。")
    cookie = input("请输入 Cookie(回车使用已内置/环境变量): ").strip() or default_cookie or ""
    if not cookie:
        # 退回到示例 cookie（来自先前测试）
        cookie = (
            "BIDUPSID=9A0F46EC76E423766C39C6C7B4F5F051; PSTM=1751510520; BAIDUID=9A0F46EC76E42376859F917A920CA8C2:FG=1; "
            "BDUSS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urY; "
            "BDUSS_BFESS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urY; "
            "STOKEN=6aebe90a8c3a78e4c2ae396bffd38bc0ea01714f288632cbb0a44298addeabf9"
        )

    link = input("请输入分享链接(回车使用示例): ").strip() or "https://pan.baidu.com/s/1uIM7LXbsPYPiWplyVHo9qg?pwd=zyas"
    auto_pwd = _extract_pwd_from_link(link)
    password = input(f"请输入提取码(自动检测为 '{auto_pwd}', 回车使用自动): ").strip() or auto_pwd

    client = BaiduClient(cookies=cookie)

    # 列出根目录可选文件夹
    root_params = ListFilesParam(drive_type=DriveType.BAIDU_DRIVE, file_path="/")
    root_items = await client.get_disk_list(root_params)
    folders = [i for i in root_items if i.is_folder]

    print("\n可选择的根目录文件夹:")
    for idx, fd in enumerate(folders):
        print(f"[{idx}] {fd.file_path}")

    print("\n选择目标路径方式:")
    print("  - 输入索引使用已有文件夹")
    print("  - 输入 c 创建新文件夹 (位于根目录下)")
    print("  - 输入 p 直接手动输入绝对路径")

    choice = input("请输入选择: ").strip().lower()
    target_path = "/"

    if choice.isdigit() and int(choice) < len(folders):
        target_path = folders[int(choice)].file_path
    elif choice == "c":
        new_name = input("请输入新建文件夹名称: ").strip()
        target_path = _ensure_abs(new_name)
    elif choice == "p":
        manual = input("请输入目标绝对路径(如 /我的资源/测试保存): ").strip()
        target_path = _ensure_abs(manual)
    else:
        print("未选择有效项，默认使用根目录 /")
        target_path = "/"

    # 执行转存
    params = TransferParam(
        drive_type=DriveType.BAIDU_DRIVE,
        source_type="link",
        source_id=link,
        source_path="/",
        target_path=target_path,
        file_ids=None,
        ext={"password": password} if password else {},
    )

    ok = await client.transfer(params)
    print(f"\n转存结果: {'成功' if ok else '失败'} -> 目标路径: {target_path}")


if __name__ == "__main__":
    asyncio.run(main())


