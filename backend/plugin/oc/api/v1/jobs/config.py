from fastapi import APIRouter

from backend.database.db import CurrentSession
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.plugin.config.crud.crud_config import config_dao
from backend.plugin.config.enums import ConfigType
from backend.utils.serializers import select_list_serialize

router = APIRouter()


@router.get('/shop', summary='获取店铺配置', description='获取店铺二维码和链接（公开接口）')
async def get_shop_config(db: CurrentSession) -> ResponseSchemaModel:
    """
    获取店铺配置（无需登录）
    """
    try:
        configs = await config_dao.get_all(db, ConfigType.shop)
        if not configs:
            return response_base.success(data={})

        config_dict = {c['key']: c['value'] for c in select_list_serialize(configs)}

        # 检查是否启用
        if not int(config_dict.get('SHOP_CONFIG_STATUS', 0)):
            return response_base.success(data={})

        return response_base.success(
            data={
                'shop_url': config_dict.get('SHOP_URL', ''),
                'shop_qr_code': config_dict.get('SHOP_QR_CODE', ''),
            }
        )
    except Exception:
        return response_base.success(data={})
