#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from typing import Any

from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import ListShareFilesParam
from backend.app.coulddrive.service.baidu.client import BaiduClient


async def run_test(cookie: str, link: str) -> None:
    """运行百度 link 分享列表的简单测试"""
    client = BaiduClient(cookies=cookie)

    # 根级
    params_root = ListShareFilesParam(
        drive_type=DriveType.BAIDU_DRIVE,
        source_type="link",
        source_id=link,
        file_path="/",
    )
    root_list = await client.get_share_list(params_root)
    print(f"root count={len(root_list)}")
    for item in root_list[:5]:
        print({
            "file_id": item.file_id,
            "file_name": item.file_name,
            "is_folder": item.is_folder,
            "file_path": item.file_path,
        })

    # 如果根下有目录，进入第一个目录再列一层
    first_dir = next((i for i in root_list if i.is_folder), None)
    if first_dir:
        params_sub = ListShareFilesParam(
            drive_type=DriveType.BAIDU_DRIVE,
            source_type="link",
            source_id=link,
            file_path=first_dir.file_path,
        )
        sub_list = await client.get_share_list(params_sub)
        print(f"sub count={len(sub_list)} path={first_dir.file_path}")
        for item in sub_list[:5]:
            print({
                "file_id": item.file_id,
                "file_name": item.file_name,
                "is_folder": item.is_folder,
                "file_path": item.file_path,
            })


if __name__ == "__main__":
    # 用你提供的 cookie 和链接
    COOKIE = (
        "BIDUPSID=9A0F46EC76E423766C39C6C7B4F5F051; PSTM=1751510520; BAIDUID=9A0F46EC76E42376859F917A920CA8C2:FG=1; H_PS_PSSID=62325_63145_63584_63639_63646_63690_63693_63724_63711_63774_63810_63823; ZFY=zn1uAgPHliA8aHrVKN1UvKWxKzdtUf0kaIydhqKbIFU:C; BAIDUID_BFESS=9A0F46EC76E42376859F917A920CA8C2:FG=1; BDUSS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKDWZ2ig1mdoY; BDUSS_BFESS=UM1Y3V6ZnoyR01DamdtODdVekFQYmJJblN3TEZEVENwNmR1SGlMWUJJdWdZNDlvSVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKDWZ2ig1mdoY; PANWEB=1; Hm_lvt_0ba7bcf57b5e55fbfbab9a2750acdf3e=1751635591,1751686750,1751784493,1751784523; STOKEN=6aebe90a8c3a78e4c2ae396bffd38bc0ea01714f288632cbb0a44298addeabf9; Hm_lvt_182d6d59474cf78db37e0b2248640ea5=1753942909,1754214335,1754483537,1754549693; csrfToken=Jfm0lXypUB9YX5tG2IDYj3im; PANPSC=11710659305822854947%3AnHZOtuqy9asOmxlqtMELYFcS2d9ns3O5C61tf8CKQkgNjbYgPSAIMKUY4cQrI%2BJ7mkqHYt%2BNhjH42whq4mqbpONHiOwr%2ByPWOg9ifdcaUVf6tFIdG58v4x1SnoRAxu5fJlOfPZFHq36ck0T9AttkQZI6enfTG9RjNaEJrI5V%2Fed8Wde7ocAHCFvKX4DMNpv6FHFBPAHjbTFVFY6DiFPjb2Xs5TPgvEgZZyiEnGgQhUpH8Q8GquUrPqVYKwkVuBOyX2XlUsKRi0YmtM9d4zNnAx3eJYyVFsgjaZ6lcKGvWBM%3D; Hm_lvt_7a3960b6f067eb0085b7f96ff5e660b0=1753930217,1753942916,1754214379,1754921446; HMACCOUNT=796E4F7EA274F24E; BDCLND=it5JCKQ4OnRKAYrlLbj9QkHJHwJvJPDA%2BkyO16QKk2E%3D; Hm_lpvt_7a3960b6f067eb0085b7f96ff5e660b0=1754921450; ndut_fmt=5148C9BD52197A480C887492C961C3C0C4C33D1889533FB6861F7D21050E244E; ab_sr=1.0.1_NDg3ZjUyNjFmMzM5YWM3NmVmZDA0MmNkYjg1MmU1ZDFlNWUzYzU4NmM1ZGZlNzNlMmFjMWU4MGNhYmYyNWNlNTZkMTAyYTE3ZWJjZWNmODZjYjA0ZmE4MzA0MjYzZTRiYTU4MGNmNWM1ODI1YTNlODQwMTMyNzgxN2M1YTZjNmRlMDEyNGQ1Nzc4YzdlZGZmNWRmMGZmMTE2N2Y3NWYyM2MzOTFjYWFkYTAwYzBhNTRhYjc1ODBjNGRmYzdhODRj"
    )
    LINK = "https://pan.baidu.com/s/1uIM7LXbsPYPiWplyVHo9qg?pwd=zyas"

    asyncio.run(run_test(COOKIE, LINK))


