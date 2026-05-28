"""简历 Service"""

import json
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_resume import resume_dao
from backend.plugin.oc.schema.resume import SaveResumeParam, FieldInfo, FieldMapping, SelectorFillParam
from backend.plugin.oc.service.formatter_service import formatter_service
from backend.core.conf import settings


class ResumeService:
    """简历服务"""

    @staticmethod
    async def get(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
        """获取用户简历"""
        resume = await resume_dao.get_by_user_id(db, user_id)
        if not resume:
            return None
        return {
            'id': resume.id,
            'user_id': resume.user_id,
            'encrypted_data': resume.encrypted_data,
            'data_hash': resume.data_hash,
            'created_time': resume.created_time,
            'updated_time': resume.updated_time
        }

    @staticmethod
    async def save(db: AsyncSession, user_id: int, obj: SaveResumeParam) -> None:
        """保存或更新简历"""
        existing = await resume_dao.get_by_user_id(db, user_id)
        if existing:
            await resume_dao.update(db, existing, obj)
        else:
            await resume_dao.create(db, user_id, obj)
        await db.commit()

    @staticmethod
    async def delete(db: AsyncSession, user_id: int) -> int:
        """删除简历"""
        count = await resume_dao.delete_by_user_id(db, user_id)
        await db.commit()
        return count

    @staticmethod
    async def identify_fields(fields: list[FieldInfo]) -> list[FieldMapping]:
        """使用 AI 识别表单字段类型"""
        # 构建 prompt
        fields_json = json.dumps(
            [f.model_dump() for f in fields],
            ensure_ascii=False,
            indent=2
        )

        prompt = f"""你是一个表单字段识别专家。分析以下表单字段信息，判断每个字段应该填写简历中的哪个数据。

表单字段列表：
{fields_json}

可用的简历字段：
- name: 姓名
- phone: 手机号
- email: 邮箱
- gender: 性别
- birthday: 生日
- address: 地址
- school: 学校
- major: 专业
- degree: 学历
- company: 公司
- position: 职位
- selfIntro: 自我介绍
- expectedSalary: 期望薪资
- expectedCity: 期望城市
- skills: 技能
- github: GitHub
- linkedin: LinkedIn
- portfolio: 作品集

请返回 JSON 格式的映射结果，只返回能够匹配的字段：
[{{"fieldIndex": 0, "resumeField": "name", "confidence": 0.95}}, ...]

只返回 JSON 数组，不要其他内容。"""

        try:
            # 调用 OpenAI API
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL or 'gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': '你是一个专业的表单字段分析助手，只返回 JSON 格式的结果。'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            result_text = response.choices[0].message.content.strip()

            # 解析 JSON
            # 移除可能的 markdown 代码块标记
            if result_text.startswith('```'):
                result_text = result_text.split('\n', 1)[1]
                result_text = result_text.rsplit('```', 1)[0]

            mappings_data = json.loads(result_text)

            return [FieldMapping(**m) for m in mappings_data]

        except Exception as e:
            print(f'AI identify error: {e}')
            return []

    @staticmethod
    def get_formatter() -> dict[str, Any]:
        """获取 formatter 配置"""
        return formatter_service.get_formatter()

    @staticmethod
    async def selector_fill(obj: SelectorFillParam) -> str | None:
        """
        AI 选择下拉选项

        1. 先使用本地 mapping 匹配
        2. 本地匹配失败，调用 AI 匹配
        """
        # 解析 resume_key 获取 category 和 field
        category, field, label = formatter_service.parse_resume_key(obj.resume_key)

        # 1. 尝试本地匹配
        matched = formatter_service.find_best_match(
            obj.resume_value,
            obj.candidates_value,
            category,
            field
        )

        if matched:
            print(f'[SelectorFill] 本地匹配成功: {obj.resume_value} -> {matched}')
            return matched

        # 2. 本地匹配失败，调用 AI
        print(f'[SelectorFill] 本地未匹配，调用 AI: {obj.resume_value} in {obj.candidates_value}')

        try:
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            # 构建 prompt，包含完整简历数据（如果有）
            resume_context = ''
            if obj.resume_data:
                resume_context = f"""
完整简历数据（供参考）:
{json.dumps(obj.resume_data, ensure_ascii=False, indent=2)}
"""

            prompt = f"""你是一个表单填充助手。用户需要在下拉框中选择一个选项。
{resume_context}
字段标签: {obj.label or label or '未知'}
当前字段的值: {obj.resume_value}
可选项: {json.dumps(obj.candidates_value, ensure_ascii=False)}

请根据简历数据和当前字段的值，从可选项中选择一个最匹配的选项。
注意：有些字段可能需要结合简历中的其他信息来判断（如"是否为最高学历"需要查看所有教育经历）。

如果没有合适的选项，返回 null。
只返回选中的选项值（字符串）或 null，不要其他内容。"""

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL or 'gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': '你是一个表单填充助手，只返回选项值或 null。'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            result = response.choices[0].message.content.strip()

            # 处理返回结果
            if result.lower() == 'null' or result == '':
                return None

            # 去掉可能的引号
            result = result.strip('"\'')

            # 验证结果是否在选项中
            if result in obj.candidates_value:
                print(f'[SelectorFill] AI 匹配成功: {obj.resume_value} -> {result}')
                return result

            return None

        except Exception as e:
            print(f'[SelectorFill] AI 匹配失败: {e}')
            return None

    @staticmethod
    async def parse_pdf(text: str) -> dict[str, Any]:
        """
        使用 AI 解析 PDF 简历文本

        Args:
            text: PDF 提取的文本内容

        Returns:
            解析后的简历数据
        """
        system_prompt = """你是一个专业的简历解析专家。请分析以下简历文本，提取结构化信息并以JSON格式返回。

请严格按照以下JSON结构返回数据（只返回有效数据，没有的字段不要包含）：

{
  "name": "姓名",
  "english_name": "英文名",
  "gender": "性别（男/女）",
  "date_of_birth": "出生日期（YYYY-MM-DD格式）",
  "ethnicity": "民族",
  "phone_number": "手机号",
  "email": "邮箱",
  "wechat_id": "微信号",
  "qq": "QQ号",
  "political_affiliation": "政治面貌",
  "marital_status": "婚姻状况",
  "household_registration_location": "户籍所在地",
  "hometown": "籍贯",
  "current_residence": "现居住地",
  "years_of_work_experience": "工作年限",

  "job_intention": [{
    "intended_position": "期望职位",
    "expected_city": "期望城市",
    "expected_industry": "期望行业",
    "expected_salary": 期望薪资数字,
    "desired_employment_type": "工作类型（全职/兼职/实习）"
  }],

  "education_background": [{
    "start_time": "开始时间（YYYY-MM-DD）",
    "end_time": "结束时间（YYYY-MM-DD）",
    "school": "学校名称",
    "major": "专业",
    "degree": "学位（博士/硕士/学士/无学位）",
    "education_level": "学历（博士研究生/硕士研究生/本科/大专/高中）",
    "form_of_study": "学习形式（全日制/非全日制）",
    "tier": "学校层次（985/211/双一流/普通本科）",
    "institute": "院系",
    "score": "GPA/成绩"
  }],

  "work_experience": [{
    "start_time": "开始时间（YYYY-MM-DD）",
    "end_time": "结束时间（YYYY-MM-DD）",
    "company": "公司名称",
    "position": "职位",
    "department": "部门",
    "job_description": "工作内容描述"
  }],

  "internship_experience": [{
    "start_time": "开始时间（YYYY-MM-DD）",
    "end_time": "结束时间（YYYY-MM-DD）",
    "company": "公司名称",
    "position": "职位",
    "department": "部门",
    "job_description": "实习内容描述"
  }],

  "project_experience": [{
    "start_time": "开始时间（YYYY-MM-DD）",
    "end_time": "结束时间（YYYY-MM-DD）",
    "project_name": "项目名称",
    "role": "担任角色",
    "project_description": "项目描述",
    "responsibility": "个人职责"
  }],

  "language_proficiency": [{
    "language_type": "语种",
    "certification_name": "证书名称",
    "score": "分数",
    "level_of_mastery": "掌握程度（精通/熟练/良好/一般）"
  }],

  "computer_skills": [{
    "certification_name": "技能/证书名称",
    "level_of_mastery": "掌握程度"
  }],

  "certificates": [{
    "certification_name": "证书名称",
    "certification_date": "获得时间（YYYY-MM-DD）",
    "certification_number": "证书编号",
    "certification_auth_department": "颁发机构"
  }]
}

注意事项：
1. 日期统一转换为YYYY-MM-DD格式，如果只有年月则使用YYYY-MM-01
2. 只返回JSON，不要有任何额外的文字说明
3. 如果某个字段在简历中没有找到，就不要包含该字段
4. 薪资只返回数字，不要包含"元"、"K"等单位
5. 区分工作经历和实习经历，在校期间的工作经历归类为实习"""

        try:
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL or 'gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'请解析以下简历内容：\n\n{text}'}
                ],
                temperature=0.3,
                max_tokens=4000,
                response_format={'type': 'json_object'}
            )

            result_text = response.choices[0].message.content.strip()
            print(f'[ParsePdf] AI 解析完成，返回 {len(result_text)} 字符')

            return json.loads(result_text)

        except Exception as e:
            print(f'[ParsePdf] AI 解析失败: {e}')
            raise Exception(f'AI 解析失败: {e}')


resume_service: ResumeService = ResumeService()
