#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime

from backend.app.job.schema.job import CreateJobPostingParam
from backend.app.job.service.job import JobService


async def main() -> None:
    obj = CreateJobPostingParam(
        company_name='智慧城市与商业事业群',
        position_require_new={
            'degree_associate': 0,
            'degree_bachelor': 1,
            'degree_master': 0,
            'degree_doctor': 0,
            'degree_unlimited': 0,
            'e_4': 0,
            'e_6': 0,
            'e_fluent': 0,
            'e_IELTS': 0,
            'e_TOEFL': 0,
            'e_GRE': 0,
            's_211': 0,
            's_double_first_class': 0,
            'party_number': 0,
            'oversea': 0,
            'student_leader': 0,
            'address': ['深圳市', '武汉市'],
            'major': ['计算机', '软件工程', '人工智能', '通信相关'],
            'business_trip': 0,
            'overtime': 0,
            'class': [26],
            'major_id': [427, 441, 442, 443, 413],
            'address_id': [2016, 1736],
        },
        expire_date=datetime.fromisoformat('2026-09-15 23:59:59'),
        job_title='26届AI领航员-SCG-测试开发工程师',
        publish_date=datetime.fromisoformat('2025-09-15 18:04:10'),
        num_hire=None,
        class_=0,
        salary=None,
        raw_position_require=(
            '1、本科及以上学历，计算机/软件工程/人工智能/通信相关专业\n'
            '2、了解Linux/docker/k8s的常用操作。\n'
            '3、熟悉Python/shell等脚本语言，了解pytest等自动化测试框架，有相关实习经验的优先。\n'
            '4、了解AI相关技术，有CV/大模型/分布式服务端等相关实习经验优先。\n'
            '5、良好的团队合作能力和独立思考的能力，责任心强，能承受一定的工作压力。'
        ),
        responsibility=(
            '1、参与产品需求评审和开发设计评审，根据项目及业务的需要，设计测试方案和测试用例，并进行自动化脚本的编写。\n'
            '2、按照测试计划完成项目迭代和版本测试，包括接口、功能、性能、精度、稳定性、高可用等相关测试工作，能及时识别项目风险，推动问题的解决。\n'
            '3、对客户及运维部门反馈的产品问题提供技术支持，按需参与项目的远程与现场支持。\n'
            '4、参与CI/CD流水线的建设和维护，针对CI/CD过程中发现的问题持续推动解决和优化。\n'
        ),
        spider_time=datetime.fromisoformat('2025-09-15 20:36:37'),
        position_web_url='https://wecruit.hotjob.cn/SU60fa3bdabef57c1023fc1cbc/pb/posDetail.html?postId=68c7e4a2778ced4f394ab779&postType=campus',
        page_list_config_id='659ffa8121b4ea896f0dea72',
        position_require_parsed=True,
        job_title_id=[126],
        referral_code='tkcsbh',
        referral_show_index=1,
        main_company_name='上海商汤智能科技有限公司',
        company_alias='商汤科技',
        org_type=['民企'],
        industry=['硬件/半导体/芯片'],
        tags=[],
        company_id='6743446713cf1813205064bf',
        logo='https://cdn.tatawangshen.com/company_file/6743446713cf1813205064bf/3929daa6-06ba-11f0-956c-0242ac140002/商汤 (1).svg',
        degree_str=['本科'],
        major_str=['人工智能', '计算机类', '计算机科学与技术', '软件工程', '通信工程'],
        address_str=['深圳', '武汉'],
        job_title_str=['无人机组装测试'],
        # 便于检索
        address_id=[2016, 1736],
        major_id=[427, 441, 442, 443, 413],
    )

    await JobService.create(obj)
    print('inserted')


if __name__ == '__main__':
    asyncio.run(main())


