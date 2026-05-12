#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import oss2

from asgiref.sync import sync_to_async

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.oss.service.providers.base import ProviderUploadContext


class AliyunOssProvider:
    """阿里云 OSS provider"""

    @staticmethod
    def _get_bucket() -> oss2.Bucket:
        """
        Create aliyun oss bucket object.

        :return:
        """
        access_key = str(settings.OSS_ACCESS_KEY).strip()
        secret_key = str(settings.OSS_SECRET_KEY).strip()
        endpoint = str(settings.OSS_ENDPOINT).strip()
        bucket_name = str(settings.OSS_BUCKET_NAME).strip()

        if not access_key or not secret_key or not endpoint or not bucket_name:
            raise errors.RequestError(msg='阿里云 OSS 配置不完整，请检查环境变量与插件配置')

        auth = oss2.Auth(access_key, secret_key)
        return oss2.Bucket(auth, endpoint, bucket_name)

    async def upload(self, context: ProviderUploadContext) -> str:
        """
        Upload file by aliyun oss.

        :param context: upload context
        :return:
        """
        return await self._upload_sync(context)

    async def delete(self, object_key: str) -> bool:
        """
        Delete object by key.

        :param object_key: object key
        :return:
        """
        return await self._delete_sync(object_key)

    @sync_to_async
    def _delete_sync(self, object_key: str) -> bool:
        """
        Delete object by key in sync thread.

        :param object_key: object key
        :return:
        """
        try:
            bucket = self._get_bucket()
            bucket.delete_object(object_key)
            return True
        except errors.RequestError:
            raise
        except Exception as exc:
            log.warning(f'阿里云删除失败 object_key={object_key}: [{type(exc).__name__}] {exc!r}')
            return False

    @sync_to_async
    def _upload_sync(self, context: ProviderUploadContext) -> str:
        """
        Upload file by aliyun oss in sync thread.

        :param context: upload context
        :return:
        """
        try:
            if context.object_expire_days:
                log.warning(
                    f'阿里云 OSS 暂不支持上传接口直设 deleteAfterDays，请在 Bucket 生命周期中按前缀配置过期: {context.object_key}'
                )

            bucket = self._get_bucket()
            context.file.file.seek(0)

            if context.use_signed_url:
                result = bucket.put_object(context.object_key, context.file.file)
                if result.status >= 400:
                    raise RuntimeError(f'aliyun put_object failed, status={result.status}')
                return bucket.sign_url('GET', context.object_key, context.signed_url_expire_seconds)

            result = bucket.put_object(
                context.object_key,
                context.file.file,
                headers={'x-oss-object-acl': 'public-read'},
            )
            if result.status >= 400:
                raise RuntimeError(f'aliyun put_object failed, status={result.status}')
            return result.resp.response.url
        except errors.RequestError:
            raise
        except Exception as exc:
            log.error(f'阿里云上传失败 object_key={context.object_key}: [{type(exc).__name__}] {exc!r}')
            raise errors.RequestError(msg='上传文件失败')
