#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import re

from pathlib import Path

import tomllib

from backend.plugin.render_book.schema.render import RenderTemplateManifest

TEMPLATES_ROOT = Path(__file__).resolve().parents[1] / 'templates'
_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')


def _calculate_template_digest(template_root: Path) -> str:
    """
    计算模板目录内容摘要

    :param template_root: 模板版本目录
    :return:
    """
    digest = hashlib.sha256()
    files = sorted(path for path in template_root.rglob('*') if path.is_file())
    for file_path in files:
        relative_path = file_path.relative_to(template_root).as_posix().encode()
        digest.update(relative_path)
        digest.update(b'\0')
        digest.update(file_path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def _version_key(version: str) -> tuple[int, int, int]:
    """
    解析模板版本排序键

    :param version: 语义化版本号
    :return:
    """
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError(f'模板版本必须使用 x.y.z 格式：{version}')
    major, minor, patch = version.split('.')
    return int(major), int(minor), int(patch)


def _load_manifest(manifest_path: Path, template_key: str, template_version: str) -> RenderTemplateManifest:
    """
    加载并校验模板清单

    :param manifest_path: 模板清单路径
    :param template_key: 目录中的模板键
    :param template_version: 目录中的模板版本
    :return:
    """
    payload = tomllib.loads(manifest_path.read_text(encoding='utf-8'))
    variant_entrypoints = payload.get('variant_entrypoints', {}) or {}
    default_variant = payload.get('default_variant', 'questions_only')
    if default_variant not in variant_entrypoints and payload.get('entrypoint'):
        variant_entrypoints[default_variant] = payload.get('entrypoint', 'main.tex.j2')
    if 'questions_only' not in variant_entrypoints:
        variant_entrypoints['questions_only'] = payload.get('entrypoint', 'main.tex.j2')
    payload['variant_entrypoints'] = variant_entrypoints
    payload['supported_variants'] = list(variant_entrypoints)
    payload['digest'] = _calculate_template_digest(manifest_path.parent)
    manifest = RenderTemplateManifest.model_validate(payload)
    if manifest.key != template_key:
        raise ValueError(f'模板清单 key 与目录不一致：{manifest_path}')
    if manifest.version != template_version:
        raise ValueError(f'模板清单 version 与目录不一致：{manifest_path}')

    _version_key(manifest.version)
    for entrypoint in manifest.variant_entrypoints.values():
        entrypoint_path = manifest_path.parent / entrypoint
        if not entrypoint_path.is_file():
            raise ValueError(f'模板入口文件不存在：{entrypoint_path}')
    return manifest


def get_template_catalog() -> dict[str, dict[str, RenderTemplateManifest]]:
    """扫描所有已发布的模板版本"""
    catalog: dict[str, dict[str, RenderTemplateManifest]] = {}
    if not TEMPLATES_ROOT.is_dir():
        return catalog

    template_dirs = sorted(path for path in TEMPLATES_ROOT.iterdir() if path.is_dir())
    for template_dir in template_dirs:
        versions: dict[str, RenderTemplateManifest] = {}
        version_dirs = sorted(path for path in template_dir.iterdir() if path.is_dir())
        for version_dir in version_dirs:
            manifest_path = version_dir / 'manifest.toml'
            if not manifest_path.is_file():
                continue
            manifest = _load_manifest(manifest_path, template_dir.name, version_dir.name)
            versions[manifest.version] = manifest
        if versions:
            catalog[template_dir.name] = versions
    return catalog


def get_latest_template_manifests() -> dict[str, RenderTemplateManifest]:
    """获取每个模板的最新启用版本"""
    latest_manifests: dict[str, RenderTemplateManifest] = {}
    for template_key, versions in get_template_catalog().items():
        enabled_versions = [manifest for manifest in versions.values() if manifest.enabled]
        if not enabled_versions:
            continue
        latest_manifests[template_key] = max(enabled_versions, key=lambda item: _version_key(item.version))
    return latest_manifests


def resolve_template_manifest(
    catalog: dict[str, dict[str, RenderTemplateManifest]],
    template_key: str,
    template_version: str | None = None,
) -> RenderTemplateManifest | None:
    """
    解析指定模板版本

    :param catalog: 模板版本目录
    :param template_key: 模板键
    :param template_version: 指定版本，为空时取最新启用版本
    :return:
    """
    versions = catalog.get(template_key)
    if not versions:
        return None
    if template_version:
        manifest = versions.get(template_version)
        if manifest is None or not manifest.enabled:
            return None
        return manifest

    enabled_versions = [manifest for manifest in versions.values() if manifest.enabled]
    if not enabled_versions:
        return None
    return max(enabled_versions, key=lambda item: _version_key(item.version))
