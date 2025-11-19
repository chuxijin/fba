#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置管理服务"""
import json
from pathlib import Path
from typing import Any


class ConfigService:
    """配置管理服务类"""

    def __init__(self, config_path: str = 'config.json'):
        """
        初始化配置服务

        :param config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}
        self._default_config = {
            'theme': 'light',
            'api_base_url': 'http://localhost:8000',
            'bili_exclude_levels': [],
            'bili_exclude_months': 0,
            'bili_interval_min': 30,
            'bili_interval_max': 60,
        }
        self.load()

    def load(self):
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                # 合并默认配置，确保所有字段都存在
                for key, value in self._default_config.items():
                    if key not in self.config:
                        self.config[key] = value
                # 如果有新字段，保存一次
                self.save()
            except Exception as e:
                print(f'加载配置文件失败: {e}，使用默认配置')
                self.config = self._default_config.copy()
                self.save()
        else:
            # 配置文件不存在，创建默认配置
            self.config = self._default_config.copy()
            self.save()

    def save(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'保存配置文件失败: {e}')

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        :param key: 配置键
        :param default: 默认值
        :return:
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """
        设置配置值并自动保存

        :param key: 配置键
        :param value: 配置值
        :return:
        """
        self.config[key] = value
        self.save()

    def get_all(self) -> dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()

    def reset(self):
        """重置为默认配置"""
        self.config = self._default_config.copy()
        self.save()


# 全局实例
config_service = ConfigService()
