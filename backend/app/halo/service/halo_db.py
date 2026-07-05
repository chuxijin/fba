from __future__ import annotations

import json
from typing import Any

import pymysql

from backend.core.conf import settings


class HaloDbClient:
    """Halo MySQL 数据库直读客户端（用于 Docsme 文档数据）"""

    def __init__(self) -> None:
        self._host = settings.HALO_DB_HOST
        self._port = settings.HALO_DB_PORT
        self._user = settings.HALO_DB_USER
        self._password = settings.HALO_DB_PASSWORD
        self._database = settings.HALO_DB_NAME

    def _connect(self) -> pymysql.Connection:
        """建立数据库连接"""
        return pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor,
        )

    def fetch_all_doctrees(self) -> list[dict[str, Any]]:
        """
        获取所有 DocTree 节点

        :return: 树节点列表，含 parent/type/priority/permalink/docName
        """
        sql = "SELECT data FROM extensions WHERE name LIKE '/registry/doc.halo.run/doctrees/%'"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                results = []
                for row in cur.fetchall():
                    d = json.loads(row[0])
                    spec = d.get('spec', {})
                    status = d.get('status', {})
                    metad = d.get('metadata', {})
                    results.append({
                        'name': metad.get('name', ''),
                        'title': spec.get('title', ''),
                        'slug': spec.get('slug', ''),
                        'type': spec.get('type', ''),
                        'parent': spec.get('parent', None),
                        'priority': spec.get('priority', 0),
                        'doc_name': spec.get('docName', ''),
                        'project_version_name': spec.get('projectVersionName', ''),
                        'permalink': status.get('permalink', ''),
                        'published': status.get('published', False),
                    })
                return results

    def build_tree(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        将扁平的节点列表构建为嵌套树

        :param nodes: fetch_all_doctrees 返回的节点列表
        :return: 树结构
        """
        by_name: dict[str, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []
        for n in nodes:
            n['children'] = []
            by_name[n['name']] = n

        for n in nodes:
            parent_name = n.get('parent')
            if parent_name and parent_name in by_name:
                by_name[parent_name]['children'].append(n)
            else:
                roots.append(n)

        def sort_key(n):
            return n.get('priority', 0) or 0

        def sort_recursive(items):
            items.sort(key=sort_key)
            for item in items:
                sort_recursive(item.get('children', []))

        sort_recursive(roots)
        return roots

    def fetch_doc_by_name(self, name: str) -> dict[str, Any] | None:
        """
        通过 Doc 资源 name 获取文档元数据

        :param name: Doc UUID 或 DocTree UUID
        :return:
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                # 先试 Doc UUID
                cur.execute(
                    "SELECT data FROM extensions WHERE name = %s",
                    (f'/registry/doc.halo.run/docs/{name}',),
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])

                # 再试 DocTree UUID（从 treetail 找到关联的 Doc）
                cur.execute(
                    "SELECT data FROM extensions WHERE name = %s",
                    (f'/registry/doc.halo.run/doctrees/{name}',),
                )
                row = cur.fetchone()
                if row:
                    d = json.loads(row[0])
                    doc_name = d.get('spec', {}).get('docName', '')
                    if doc_name:
                        cur.execute(
                            "SELECT data FROM extensions WHERE name = %s",
                            (f'/registry/doc.halo.run/docs/{doc_name}',),
                        )
                        row = cur.fetchone()
                        if row:
                            return json.loads(row[0])
        return None

    def fetch_snapshot_content(self, snapshot_name: str) -> str:
        """
        获取快照的 HTML 正文内容

        :param snapshot_name: 快照资源名称
        :return: HTML 内容
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM extensions WHERE name = %s",
                    (f'/registry/content.halo.run/snapshots/{snapshot_name}',),
                )
                row = cur.fetchone()
                if not row:
                    return ''
                d = json.loads(row[0])
                spec = d.get('spec', {})
                return spec.get('contentPatch') or spec.get('rawPatch', '')

    def get_doc_detail(self, name: str) -> dict[str, Any] | None:
        """
        获取文档详情（含正文内容）

        :param name: Doc UUID（或关联的 DocTree UUID）
        :return: 包含 title/permalink/content/updated_at
        """
        doc = self.fetch_doc_by_name(name)
        if not doc:
            return None

        spec = doc.get('spec', {})
        metadata = doc.get('metadata', {})

        # 找到 releaseSnapshot（已发布的内容）
        snapshot_name = spec.get('releaseSnapshot') or spec.get('headSnapshot', '')
        content = self.fetch_snapshot_content(snapshot_name) if snapshot_name else ''

        # 通过关联的 DocTree 获取标题和 permalink
        doc_tree_name = spec.get('docTreeName', '')
        title = ''
        permalink = ''
        if doc_tree_name:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM extensions WHERE name = %s",
                        (f'/registry/doc.halo.run/doctrees/{doc_tree_name}',),
                    )
                    row = cur.fetchone()
                    if row:
                        d = json.loads(row[0])
                        title = d.get('spec', {}).get('title', '')
                        permalink = d.get('status', {}).get('permalink', '')

        updated_at = spec.get('updatedAt') or metadata.get('creationTimestamp', '')
        return {
            'name': metadata.get('name', ''),
            'title': title or spec.get('title', ''),
            'permalink': permalink,
            'content': content,
            'updated_at': updated_at,
        }


halo_db = HaloDbClient()
