import json

from pathlib import Path

from backend.common.exception import errors

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / 'artifacts'


class OpenAuthDistributionService:
    @staticmethod
    def get_release() -> dict:
        filename = ARTIFACT_DIR / 'skill-release.json'
        if not filename.is_file():
            raise errors.NotFoundError(msg='尚未发布 Skill 安装包，请先运行打包脚本')
        return json.loads(filename.read_text(encoding='utf-8'))

    @staticmethod
    def get_package() -> Path:
        filename = ARTIFACT_DIR / 'youanshang-skill.zip'
        if not filename.is_file():
            raise errors.NotFoundError(msg='Skill 安装包不存在')
        return filename


openauth_distribution_service = OpenAuthDistributionService()
