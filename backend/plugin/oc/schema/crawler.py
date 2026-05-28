from pydantic import Field

from backend.common.schema import SchemaBase


class CrawlerParam(SchemaBase):
    """爬虫参数"""

    job_type: str = Field(default='campus', description='岗位类型（campus=校招, intern=实习）')
    start_page: int = Field(default=1, ge=1, description='开始页码')
    end_page: int = Field(default=5, ge=1, description='结束页码')
    delay: float = Field(default=1.0, ge=0.1, description='请求间隔（秒）')
    nonce: str | None = Field(default=None, description='nonce值（可选，不传则自动从网页获取）')
    cookie: str | None = Field(default=None, description='Cookie值（可选，用于绕过403限制）')


class CrawlerResult(SchemaBase):
    """爬虫结果"""

    total_crawled: int = Field(description='总爬取数量')
    total_saved: int = Field(description='保存成功数量')
    total_skipped: int = Field(description='跳过数量')
    errors: list[str] = Field(description='错误信息列表')
