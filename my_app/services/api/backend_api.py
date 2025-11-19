#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后端 API 服务 - 账号管理"""
import httpx

from my_app.services.config_service import config_service


class BackendAPIService:
    """后端 API 服务类"""

    def __init__(self):
        """初始化后端 API 服务"""
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（懒加载）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @property
    def base_url(self) -> str:
        """从配置文件获取 API 基础 URL"""
        return config_service.get('api_base_url')

    async def get_account_list(
        self,
        account_name: str | None = None,
        mid: str | None = None,
        status: int | None = None,
        category_id: int | None = None,
    ) -> list[dict]:
        """
        获取账号列表

        :param account_name: 账号名称
        :param mid: B 站用户 MID
        :param status: 状态
        :param category_id: 分类 ID
        :return: 账号列表
        """
        try:
            url = f'{self.base_url}/api/v1/bili/account'
            params = {}
            if account_name:
                params['account_name'] = account_name
            if mid:
                params['mid'] = mid
            if status is not None:
                params['status'] = status
            if category_id:
                params['category_id'] = category_id

            response = await self.client.get(url, params=params)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data', [])
            return []
        except Exception as e:
            print(f'获取账号列表失败: {e}')
            return []

    async def get_account(self, pk: int) -> dict | None:
        """
        获取账号详情

        :param pk: 账号 ID
        :return: 账号信息
        """
        try:
            url = f'{self.base_url}/api/v1/bili/account/{pk}'
            response = await self.client.get(url)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data')
            return None
        except Exception as e:
            print(f'获取账号详情失败: {e}')
            return None

    async def create_account(self, account_data: dict) -> bool:
        """
        创建账号

        :param account_data: 账号数据
        :return: 是否成功
        """
        try:
            url = f'{self.base_url}/api/v1/bili/account'
            response = await self.client.post(url, json=account_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'创建账号失败: {e}')
            return False

    async def update_account(self, pk: int, account_data: dict) -> bool:
        """
        更新账号

        :param pk: 账号 ID
        :param account_data: 账号数据
        :return: 是否成功
        """
        try:
            url = f'{self.base_url}/api/v1/bili/account/{pk}'
            response = await self.client.put(url, json=account_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'更新账号失败: {e}')
            return False

    async def delete_account(self, pk: int) -> bool:
        """
        删除账号

        :param pk: 账号 ID
        :return: 是否成功
        """
        try:
            url = f'{self.base_url}/api/v1/bili/account/{pk}'
            response = await self.client.delete(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'删除账号失败: {e}')
            return False

    async def get_category_list(self) -> list[dict]:
        """获取分类列表"""
        try:
            url = f'{self.base_url}/api/v1/bili/category'
            response = await self.client.get(url)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data', [])
            return []
        except Exception as e:
            print(f'获取分类列表失败: {e}')
            return []

    async def get_duplicate_check_list(
        self,
        mid: str | None = None,
        operation_type: str | None = None,
        is_active: bool | None = None,
        work_id: int | None = None,
        execution_log_id: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict | None:
        """
        分页获取操作记录列表

        :param mid: 用户 MID
        :param operation_type: 操作类型
        :param is_active: 是否主动
        :param work_id: 作品 ID
        :param execution_log_id: 任务执行记录 ID
        :param page: 页码
        :param size: 每页数量
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/duplicate_check'
            params = {'page': page, 'size': size}
            if mid:
                params['mid'] = mid
            if operation_type:
                params['operation_type'] = operation_type
            if is_active is not None:
                params['is_active'] = is_active
            if work_id:
                params['work_id'] = work_id
            if execution_log_id:
                params['execution_log_id'] = execution_log_id

            response = await self.client.get(url, params=params)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data', {})
            return None
        except Exception as e:
            print(f'获取操作记录列表失败: {e}')
            return None

    async def create_duplicate_check(self, record_data: dict) -> bool:
        """
        创建操作记录

        :param record_data: 记录数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/duplicate_check'
            response = await self.client.post(url, json=record_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'创建操作记录失败: {e}')
            return False

    async def update_duplicate_check(self, pk: int, record_data: dict) -> bool:
        """
        更新操作记录

        :param pk: 记录 ID
        :param record_data: 记录数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/duplicate_check/{pk}'
            response = await self.client.put(url, json=record_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'更新操作记录失败: {e}')
            return False

    async def delete_duplicate_check(self, pk: int) -> bool:
        """
        删除操作记录

        :param pk: 记录 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/duplicate_check/{pk}'
            response = await self.client.delete(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'删除操作记录失败: {e}')
            return False

    # ==================== 话术模板 API ====================

    async def get_template_list(
        self,
        name: str | None = None,
        template_type: str | None = None,
        status: int | None = None,
        category_id: int | None = None,
    ) -> list[dict]:
        """
        获取话术模板列表

        :param name: 模板名称
        :param template_type: 模板类型
        :param status: 状态
        :param category_id: 分类 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/template'
            params = {}
            if name:
                params['name'] = name
            if template_type:
                params['template_type'] = template_type
            if status is not None:
                params['status'] = status
            if category_id:
                params['category_id'] = category_id

            response = await self.client.get(url, params=params)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data', [])
            return []
        except Exception as e:
            print(f'获取话术列表失败: {e}')
            return []

    async def create_template(self, template_data: dict) -> bool:
        """
        创建话术模板

        :param template_data: 模板数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/template'
            response = await self.client.post(url, json=template_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'创建话术失败: {e}')
            return False

    async def update_template(self, pk: int, template_data: dict) -> bool:
        """
        更新话术模板

        :param pk: 模板 ID
        :param template_data: 模板数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/template/{pk}'
            response = await self.client.put(url, json=template_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'更新话术失败: {e}')
            return False

    async def delete_template(self, pk: int) -> bool:
        """
        删除话术模板

        :param pk: 模板 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/template/{pk}'
            response = await self.client.delete(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'删除话术失败: {e}')
            return False

    # ==================== 分类 API ====================

    async def get_category_tree(self) -> list[dict]:
        """获取分类树形结构"""
        try:
            url = f'{self.base_url}/api/v1/bili/category'
            response = await self.client.get(url)
            data = response.json()

            if data.get('code') == 200:
                return data.get('data', [])
            return []
        except Exception as e:
            print(f'获取分类树失败: {e}')
            return []

    async def create_category(self, category_data: dict) -> bool:
        """
        创建分类

        :param category_data: 分类数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/category'
            response = await self.client.post(url, json=category_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'创建分类失败: {e}')
            return False

    async def update_category(self, pk: int, category_data: dict) -> bool:
        """
        更新分类

        :param pk: 分类 ID
        :param category_data: 分类数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/category/{pk}'
            response = await self.client.put(url, json=category_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'更新分类失败: {e}')
            return False

    async def delete_category(self, pk: int) -> bool:
        """
        删除分类

        :param pk: 分类 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/category/{pk}'
            response = await self.client.delete(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'删除分类失败: {e}')
            return False

    # ==================== 任务配置 API ====================

    async def get_or_create_work_by_bvid(self, bvid: str) -> dict | None:
        """
        根据 BVID 获取或创建作品

        :param bvid: BVID
        :return: 作品信息（包含 ID）
        """
        try:
            url = f'{self.base_url}/api/v1/bili/work/get_or_create'
            response = await self.client.post(url, json={'bvid': bvid})
            data = response.json()

            return data.get('data') if data.get('code') == 200 else None
        except Exception as e:
            print(f'获取或创建作品失败: {e}')
            return None

    async def get_bili_task_configs(self, params: dict | None = None) -> dict | None:
        """
        获取任务配置列表（分页）

        :param params: 查询参数
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config'
            response = await self.client.get(url, params=params or {})
            data = response.json()

            return data if data.get('code') == 200 else None
        except Exception as e:
            print(f'获取任务配置列表失败: {e}')
            return None

    async def get_bili_task_config(self, pk: int) -> dict | None:
        """
        获取任务配置详情

        :param pk: 任务配置 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config/{pk}'
            response = await self.client.get(url)
            data = response.json()

            return data.get('data') if data.get('code') == 200 else None
        except Exception as e:
            print(f'获取任务配置详情失败: {e}')
            return None

    async def create_bili_task_config(self, task_config_data: dict) -> bool:
        """
        创建任务配置

        :param task_config_data: 任务配置数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config'
            response = await self.client.post(url, json=task_config_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'创建任务配置失败: {e}')
            raise Exception(str(e))

    async def update_bili_task_config(self, pk: int, task_config_data: dict) -> bool:
        """
        更新任务配置

        :param pk: 任务配置 ID
        :param task_config_data: 任务配置数据
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config/{pk}'
            response = await self.client.put(url, json=task_config_data)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'更新任务配置失败: {e}')
            raise Exception(str(e))

    async def delete_bili_task_config(self, pk: int) -> bool:
        """
        删除任务配置

        :param pk: 任务配置 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config/{pk}'
            response = await self.client.delete(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'删除任务配置失败: {e}')
            raise Exception(str(e))

    async def execute_task_config_now(self, pk: int) -> bool:
        """
        立即执行任务配置

        :param pk: 任务配置 ID
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_config/{pk}/execute'
            response = await self.client.post(url)
            data = response.json()

            return data.get('code') == 200
        except Exception as e:
            print(f'执行任务失败: {e}')
            raise Exception(str(e))

    # ==================== 任务执行记录 API ====================

    async def get_task_execution_logs(
        self,
        task_config_id: int | None = None,
        task_name: str | None = None,
        execution_status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict | None:
        """
        分页获取任务执行记录列表

        :param task_config_id: 任务配置 ID
        :param task_name: 任务名称
        :param execution_status: 执行状态
        :param page: 页码
        :param size: 每页数量
        :return:
        """
        try:
            url = f'{self.base_url}/api/v1/bili/task_execution_log'
            params = {'page': page, 'size': size}
            if task_config_id:
                params['task_config_id'] = task_config_id
            if task_name:
                params['task_name'] = task_name
            if execution_status:
                params['execution_status'] = execution_status

            response = await self.client.get(url, params=params)
            data = response.json()

            return data if data.get('code') == 200 else None
        except Exception as e:
            print(f'获取任务执行记录失败: {e}')
            return None

    async def close(self):
        """关闭客户端"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# 全局实例
backend_api_service = BackendAPIService()
