#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import dataclasses

from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar

from msgspec import json as msgspec_json
from pydantic import BaseModel

T = TypeVar('T')
M = TypeVar('M', bound=BaseModel)
D = TypeVar('D')


class Serializer(Protocol[T]):
    """缓存序列化协议"""

    def encode(self, value: T) -> bytes | str: ...

    def decode(self, raw: bytes | str) -> T: ...


class JsonSerializer:
    """通用 JSON 序列化器（dict / list / 标量）"""

    def encode(self, value: Any) -> bytes:
        return msgspec_json.encode(value)

    def decode(self, raw: bytes | str) -> Any:
        return msgspec_json.decode(raw)


class PydanticSerializer(Generic[M]):
    """Pydantic 模型序列化器, 命中走 model_validate_json"""

    def __init__(self, cls: type[M]) -> None:
        """
        初始化 Pydantic 序列化器

        :param cls: 目标 Pydantic 模型类
        """
        self._cls = cls

    def encode(self, value: M) -> str:
        return value.model_dump_json()

    def decode(self, raw: bytes | str) -> M:
        return self._cls.model_validate_json(raw)


class DataclassSerializer(Generic[D]):
    """Dataclass 序列化器, 支持自定义 to_dict / from_dict"""

    def __init__(
        self,
        cls: type[D],
        *,
        to_dict: Callable[[D], Any] | None = None,
        from_dict: Callable[[Any], D] | None = None,
    ) -> None:
        """
        初始化 Dataclass 序列化器

        :param cls: 目标 Dataclass 类型
        :param to_dict: 自定义对象 -> 可序列化结构, 默认走 dataclasses.asdict
        :param from_dict: 自定义可序列化结构 -> 对象, 默认走 cls(**data)
        """
        self._cls = cls
        self._to_dict = to_dict or dataclasses.asdict
        self._from_dict = from_dict or (lambda data: cls(**data))

    def encode(self, value: D) -> bytes:
        return msgspec_json.encode(self._to_dict(value))

    def decode(self, raw: bytes | str) -> D:
        return self._from_dict(msgspec_json.decode(raw))


class RawSerializer:
    """直通序列化器, 用于值本身已是 str / bytes 的场景"""

    def encode(self, value: bytes | str) -> bytes | str:
        return value

    def decode(self, raw: bytes | str) -> bytes | str:
        return raw
