"""简历字段 Formatter 配置 - Python 版本"""

from typing import TypedDict


class FieldConfig(TypedDict, total=False):
    """字段配置"""

    strategy: str  # input | drop_down_box | time | textarea
    chinese: str
    order: int
    embedding: list[str]
    mapping: dict[str, list[str]]


class CategoryConfig(TypedDict):
    """分类配置"""

    chinese: str
    order: int
    fields: dict[str, FieldConfig]


# ===== 基本信息字段配置 =====
BASIC_INFO_FIELDS: dict[str, FieldConfig] = {
    'name': {
        'strategy': 'input',
        'chinese': '姓名',
        'embedding': ['姓名', '填表人签名', '本人签名', '申请人', '真实姓名', '中文姓名'],
    },
    'english_name': {
        'strategy': 'input',
        'chinese': '英文名',
        'embedding': ['英文名', '英文姓名', 'English Name', '拼音姓名', '姓名（英文）', '姓名(英文)'],
    },
    'gender': {
        'strategy': 'drop_down_box',
        'chinese': '性别',
        'embedding': ['性别', '男/女'],
        'mapping': {
            '男': ['男', '男性', '男生', 'Male', 'M', '1'],
            '女': ['女', '女性', '女生', 'Female', 'F', '2'],
        },
    },
    'date_of_birth': {
        'strategy': 'time',
        'chinese': '出生日期',
        'embedding': ['出生日期', '出生年月', '生日', '出生年月日', '出生时间'],
    },
    'phone_number': {
        'strategy': 'input',
        'chinese': '手机号码',
        'embedding': ['手机', '手机号', '手机号码', '电话', '联系电话', '移动电话'],
    },
    'email': {
        'strategy': 'input',
        'chinese': '邮箱',
        'embedding': ['邮箱', '电子邮箱', 'Email', 'E-mail', '电子邮件'],
    },
    'ethnicity': {
        'strategy': 'drop_down_box',
        'chinese': '民族',
        'embedding': ['民族', '族别'],
        'mapping': {
            '汉族': ['汉族', '汉'],
            '蒙古族': ['蒙古族', '蒙古'],
            '回族': ['回族', '回'],
            '藏族': ['藏族', '藏'],
            '维吾尔族': ['维吾尔族', '维吾尔'],
            '苗族': ['苗族', '苗'],
            '彝族': ['彝族', '彝'],
            '壮族': ['壮族', '壮'],
            '满族': ['满族', '满'],
            '朝鲜族': ['朝鲜族', '朝鲜'],
            '侗族': ['侗族', '侗'],
            '瑶族': ['瑶族', '瑶'],
            '白族': ['白族', '白'],
            '土家族': ['土家族', '土家'],
        },
    },
    'political_affiliation': {
        'strategy': 'drop_down_box',
        'chinese': '政治面貌',
        'embedding': ['政治面貌', '政治身份', '党派'],
        'mapping': {
            '群众': ['群众', '普通公民', '无党派', '普通群众', '无党派人士'],
            '共青团员': ['共青团员', '团员', '中国共产主义青年团团员'],
            '中共党员': ['中共党员', '党员', '中国共产党党员', '中共正式党员', '正式党员'],
            '中共预备党员': ['中共预备党员', '预备党员'],
            '民主党派': ['民主党派', '民主党派成员'],
        },
    },
    'marital_status': {
        'strategy': 'drop_down_box',
        'chinese': '婚姻状况',
        'embedding': ['婚姻状况', '婚姻', '婚否'],
        'mapping': {
            '未婚': ['未婚', '单身', '未婚未育'],
            '已婚': ['已婚', '已婚已育', '已婚未育'],
            '离异': ['离异', '离婚'],
            '丧偶': ['丧偶'],
        },
    },
    'household_registration_location_type': {
        'strategy': 'drop_down_box',
        'chinese': '户籍类型',
        'embedding': ['户籍类型', '户口性质', '户口类型', '户籍性质'],
        'mapping': {
            '城镇': ['城镇', '城镇户口', '非农业', '非农业户口', '城市'],
            '农村': ['农村', '农村户口', '农业', '农业户口'],
        },
    },
    'current_residence': {
        'strategy': 'input',
        'chinese': '现居住地',
        'embedding': ['现居住地', '居住地', '现住址', '地址', '居住城市', '现居城市'],
    },
    'years_of_work_experience': {
        'strategy': 'input',
        'chinese': '工作年限',
        'embedding': ['工作年限', '工作经验', '从业年限'],
    },
    'blood_type': {
        'strategy': 'drop_down_box',
        'chinese': '血型',
        'embedding': ['血型'],
        'mapping': {
            'A型': ['A型', 'A', 'A血型'],
            'B型': ['B型', 'B', 'B血型'],
            'O型': ['O型', 'O', 'O血型'],
            'AB型': ['AB型', 'AB', 'AB血型'],
        },
    },
    'health_condition': {
        'strategy': 'drop_down_box',
        'chinese': '健康状况',
        'embedding': ['健康状况', '健康', '身体状况'],
        'mapping': {
            '良好': ['良好', '健康', '正常', '好'],
            '一般': ['一般', '普通'],
            '较差': ['较差', '差'],
        },
    },
    'nationality': {
        'strategy': 'drop_down_box',
        'chinese': '国籍',
        'embedding': ['国籍', '国家'],
        'mapping': {
            '中国': ['中国', '中华人民共和国', 'China', 'CN'],
        },
    },
}

# ===== 教育经历字段配置 =====
EDUCATION_FIELDS: dict[str, FieldConfig] = {
    'school': {
        'strategy': 'input',
        'chinese': '学校',
        'embedding': ['学校', '学校名称', '毕业院校', '院校', '院校名称', '就读学校'],
    },
    'major': {
        'strategy': 'input',
        'chinese': '专业',
        'embedding': ['专业', '专业名称', '所学专业', '主修专业'],
    },
    'education_level': {
        'strategy': 'drop_down_box',
        'chinese': '学历',
        'embedding': ['学历', '最高学历', '学历层次', '教育程度'],
        'mapping': {
            '博士研究生': ['博士研究生', '博士', 'PhD', 'Doctor'],
            '硕士研究生': ['硕士研究生', '硕士', '研究生', 'Master'],
            '本科': ['本科', '大学本科', '学士', '普通本科', 'Bachelor'],
            '大专': ['大专', '专科', '高职', '大学专科'],
            '高中': ['高中', '高中/中专', '高中及以下'],
            '中专': ['中专', '职高', '中等专业学校'],
            '初中': ['初中', '初中及以下'],
        },
    },
    'degree': {
        'strategy': 'drop_down_box',
        'chinese': '学位',
        'embedding': ['学位', '学位类型', '授予学位'],
        'mapping': {
            '博士': ['博士', '博士学位'],
            '硕士': ['硕士', '硕士学位'],
            '学士': ['学士', '学士学位'],
            '无学位': ['无学位', '无', '未取得'],
        },
    },
    'start_time': {
        'strategy': 'time',
        'chinese': '入学时间',
        'embedding': ['入学时间', '入学日期', '开始时间', '起始时间'],
    },
    'end_time': {
        'strategy': 'time',
        'chinese': '毕业时间',
        'embedding': ['毕业时间', '毕业日期', '结束时间', '截止时间'],
    },
    'form_of_study': {
        'strategy': 'drop_down_box',
        'chinese': '学习形式',
        'embedding': ['学习形式', '受教育类型', '是否统招', '是否全日制'],
        'mapping': {
            '全日制': ['全日制', '统招', '普通全日制', '普通高等教育', '是'],
            '非全日制': ['非全日制', '在职', '业余', '自考', '成人教育', '否'],
        },
    },
    'overseas_education_experience': {
        'strategy': 'drop_down_box',
        'chinese': '是否有海外学习经历',
        'embedding': ['是否有海外学习经历', '海外经历', '留学经历'],
        'mapping': {
            '是': ['是', '有', 'Yes', 'Y', '已有'],
            '否': ['否', '无', 'No', 'N', '没有'],
        },
    },
}

# ===== 工作经历字段配置 =====
WORK_FIELDS: dict[str, FieldConfig] = {
    'company': {
        'strategy': 'input',
        'chinese': '公司',
        'embedding': ['公司', '公司名称', '单位名称', '工作单位', '企业名称'],
    },
    'company_size': {
        'strategy': 'drop_down_box',
        'chinese': '公司规模',
        'embedding': ['公司规模', '企业规模', '单位规模', '规模'],
        'mapping': {
            '20人以下': ['20人以下', '1-20人', '少于20人', '20人及以下'],
            '20-99人': ['20-99人', '20-100人', '20-50人', '50-99人'],
            '100-499人': ['100-499人', '100-500人', '100-299人', '300-499人'],
            '500-999人': ['500-999人', '500-1000人'],
            '1000-9999人': ['1000-9999人', '1000-5000人', '5000-9999人', '1000人以上'],
            '10000人以上': ['10000人以上', '万人以上', '10000+'],
        },
    },
    'company_type': {
        'strategy': 'drop_down_box',
        'chinese': '公司性质',
        'embedding': ['公司性质', '企业性质', '单位性质', '企业类型'],
        'mapping': {
            '国有企业': ['国有企业', '国企', '国有'],
            '民营企业': ['民营企业', '民营', '私营', '私营企业', '民营/私营'],
            '外资企业': ['外资企业', '外资', '外企', '外商独资'],
            '合资企业': ['合资企业', '合资', '中外合资'],
            '上市公司': ['上市公司', '上市'],
            '事业单位': ['事业单位', '事业'],
            '政府机关': ['政府机关', '机关', '政府', '党政机关'],
            '非营利组织': ['非营利组织', 'NGO', '社会组织'],
            '其他': ['其他'],
        },
    },
    'position': {
        'strategy': 'input',
        'chinese': '职位',
        'embedding': ['职位', '职位名称', '岗位', '担任职务', '职务'],
    },
    'department': {
        'strategy': 'input',
        'chinese': '部门',
        'embedding': ['部门', '所在部门', '部门名称'],
    },
    'start_time': {
        'strategy': 'time',
        'chinese': '入职时间',
        'embedding': ['入职时间', '入职日期', '开始时间', '起始时间'],
    },
    'end_time': {
        'strategy': 'time',
        'chinese': '离职时间',
        'embedding': ['离职时间', '离职日期', '结束时间', '截止时间'],
    },
    'industry': {
        'strategy': 'input',
        'chinese': '行业',
        'embedding': ['行业', '所在行业', '公司行业'],
    },
    'reason_for_leaving': {
        'strategy': 'input',
        'chinese': '离职原因',
        'embedding': ['离职原因', '离开原因'],
    },
}

# ===== 实习经历字段配置 =====
INTERNSHIP_FIELDS: dict[str, FieldConfig] = {
    'company': {
        'strategy': 'input',
        'chinese': '实习公司',
        'embedding': ['实习公司', '实习单位', '公司', '公司名称'],
    },
    'company_size': WORK_FIELDS['company_size'],
    'company_type': WORK_FIELDS['company_type'],
    'position': {
        'strategy': 'input',
        'chinese': '实习职位',
        'embedding': ['实习职位', '实习岗位', '职位', '岗位'],
    },
    'department': WORK_FIELDS['department'],
    'start_time': {
        'strategy': 'time',
        'chinese': '实习开始时间',
        'embedding': ['实习开始时间', '开始时间', '入职时间'],
    },
    'end_time': {
        'strategy': 'time',
        'chinese': '实习结束时间',
        'embedding': ['实习结束时间', '结束时间', '离职时间'],
    },
    'salary': {
        'strategy': 'input',
        'chinese': '薪资',
        'embedding': ['薪资', '工资', '月薪', '实习工资'],
    },
}

# ===== 求职意向字段配置 =====
JOB_INTENTION_FIELDS: dict[str, FieldConfig] = {
    'intended_position': {
        'strategy': 'input',
        'chinese': '期望职位',
        'embedding': ['期望职位', '意向职位', '期望岗位', '应聘职位'],
    },
    'expected_city': {
        'strategy': 'input',
        'chinese': '期望城市',
        'embedding': ['期望城市', '期望工作地', '意向城市', '工作城市'],
    },
    'expected_salary': {
        'strategy': 'input',
        'chinese': '期望薪资',
        'embedding': ['期望薪资', '薪资要求', '期望月薪', '意向薪资'],
    },
    'current_salary': {
        'strategy': 'input',
        'chinese': '当前薪资',
        'embedding': ['当前薪资', '目前薪资', '现薪资'],
    },
    'desired_employment_type': {
        'strategy': 'drop_down_box',
        'chinese': '工作类型',
        'embedding': ['工作类型', '期望工作类型', '求职类型'],
        'mapping': {
            '全职': ['全职', '正式', '正式员工'],
            '兼职': ['兼职', '临时'],
            '实习': ['实习', '实习生'],
        },
    },
}

# ===== 语言能力字段配置 =====
LANGUAGE_FIELDS: dict[str, FieldConfig] = {
    'language_type': {
        'strategy': 'drop_down_box',
        'chinese': '语言',
        'embedding': ['语言', '外语', '语种', '外语类型'],
        'mapping': {
            '英语': ['英语', 'English'],
            '日语': ['日语', 'Japanese'],
            '法语': ['法语', 'French'],
            '德语': ['德语', 'German'],
            '韩语': ['韩语', 'Korean', '朝鲜语'],
            '俄语': ['俄语', 'Russian'],
            '西班牙语': ['西班牙语', 'Spanish'],
        },
    },
    'level_of_mastery': {
        'strategy': 'drop_down_box',
        'chinese': '掌握程度',
        'embedding': ['掌握程度', '外语水平', '英语水平', '语言水平', '熟练程度'],
        'mapping': {
            '精通': ['精通', '熟练', '流利'],
            '良好': ['良好', '较好'],
            '一般': ['一般', '基础', '入门'],
        },
    },
    'listening_and_speaking_skills': {
        'strategy': 'drop_down_box',
        'chinese': '听说能力',
        'embedding': ['听说能力', '口语能力', '听说'],
        'mapping': {
            '精通': ['精通', '熟练', '流利'],
            '良好': ['良好', '较好'],
            '一般': ['一般', '基础'],
        },
    },
    'reading_and_writing_skills': {
        'strategy': 'drop_down_box',
        'chinese': '读写能力',
        'embedding': ['读写能力', '阅读能力', '读写'],
        'mapping': {
            '精通': ['精通', '熟练'],
            '良好': ['良好', '较好'],
            '一般': ['一般', '基础'],
        },
    },
}

# ===== 自我描述字段配置 =====
SELF_EVALUATION_FIELDS: dict[str, FieldConfig] = {
    'self_evaluation': {
        'strategy': 'textarea',
        'chinese': '自我评价',
        'embedding': ['自我评价', '自我介绍', '个人简介', '简介'],
    },
}

# ===== 奖惩情况字段配置 =====
REWARD_FIELDS: dict[str, FieldConfig] = {
    'award_name': {
        'strategy': 'input',
        'chinese': '获奖名称',
        'embedding': ['获奖名称', '奖项名称', '奖项', '荣誉名称'],
    },
    'award_time': {
        'strategy': 'time',
        'chinese': '获奖时间',
        'embedding': ['获奖时间', '获得时间', '颁奖时间'],
    },
}

# ===== 完整分类配置 =====
FORMATTER_CONFIG: dict[str, CategoryConfig] = {
    'basic_info': {
        'chinese': '基本信息',
        'order': 1,
        'fields': BASIC_INFO_FIELDS,
    },
    'education_background': {
        'chinese': '教育经历',
        'order': 2,
        'fields': EDUCATION_FIELDS,
    },
    'work_experience': {
        'chinese': '工作经历',
        'order': 3,
        'fields': WORK_FIELDS,
    },
    'internship_experience': {
        'chinese': '实习经历',
        'order': 4,
        'fields': INTERNSHIP_FIELDS,
    },
    'job_intention': {
        'chinese': '求职意向',
        'order': 5,
        'fields': JOB_INTENTION_FIELDS,
    },
    'language_proficiency': {
        'chinese': '语言能力',
        'order': 6,
        'fields': LANGUAGE_FIELDS,
    },
    'self_evaluation': {
        'chinese': '自我描述',
        'order': 7,
        'fields': SELF_EVALUATION_FIELDS,
    },
    'rewards_and_punishments': {
        'chinese': '获奖经历',
        'order': 8,
        'fields': REWARD_FIELDS,
    },
}


def parse_resume_key(resume_key: str) -> tuple[str | None, str | None, str | None]:
    """
    解析 resume_key，返回 (category, field, label)

    格式: ;category;index;field@label 或 ;field@label
    示例:
      - ;gender@性别 -> (basic_info, gender, 性别)
      - ;education_background;0;education_level@学历 -> (education_background, education_level, 学历)
    """
    if not resume_key or not resume_key.startswith(';'):
        return None, None, None

    # 分离 label
    label = None
    if '@' in resume_key:
        key_part, label = resume_key.rsplit('@', 1)
    else:
        key_part = resume_key

    # 分离路径
    parts = key_part[1:].split(';')  # 去掉开头的 ;

    if len(parts) == 1:
        # 简单字段: ;field
        field = parts[0]
        # 在所有分类中查找
        for category_name, category_config in FORMATTER_CONFIG.items():
            if field in category_config['fields']:
                return category_name, field, label
    elif len(parts) >= 3:
        # 数组字段: category;index;field
        category = parts[0]
        field = parts[2]
        if category in FORMATTER_CONFIG:
            return category, field, label

    return None, None, label


def get_field_mapping(category: str, field: str) -> dict[str, list[str]] | None:
    """获取字段的下拉选项映射"""
    if category not in FORMATTER_CONFIG:
        return None

    fields = FORMATTER_CONFIG[category]['fields']
    if field not in fields:
        return None

    return fields[field].get('mapping')


def find_best_match(value: str, options: list[str], category: str | None, field: str | None) -> str | None:
    """
    在下拉选项中查找最佳匹配值

    1. 精确匹配
    2. 使用字段的 mapping 进行等价匹配
    3. 包含匹配
    """
    if not value or not options:
        return None

    value = value.strip()

    # 1. 精确匹配
    if value in options:
        return value

    # 2. 使用字段的 mapping 进行等价匹配
    if category and field:
        mapping = get_field_mapping(category, field)
        if mapping:
            for standard_value, equivalents in mapping.items():
                if value in equivalents or standard_value == value:
                    # 在选项中查找标准值或等价值
                    if standard_value in options:
                        return standard_value
                    for equiv in equivalents:
                        if equiv in options:
                            return equiv

    # 3. 包含匹配
    for option in options:
        if option in value or value in option:
            return option

    return None
