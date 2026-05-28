from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ResourceSchemaBase(SchemaBase):
    """资料包基础模型"""

    title: str = Field(description='资料包标题')
    image: str | None = Field(None, description='图片地址')
    baidu_link: str | None = Field(None, description='百度云链接')
    extract_code: str | None = Field(None, description='提取码')


class CreateResourceParam(ResourceSchemaBase):
    """创建资料包参数"""

    pass


class GetResourceDetail(ResourceSchemaBase):
    """获取资料包详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='资料包ID')
