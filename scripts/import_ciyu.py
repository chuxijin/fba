#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考词语批量导入脚本

支持从 Excel/CSV 文件批量导入词语数据到数据库
"""
import asyncio
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import select

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.gongkao.model.ciyu import GkCiyu
from backend.database.db import async_engine, async_db_session


class CiyuImporter:
    """词语导入器"""

    def __init__(self, file_path: str, batch_size: int = 1000):
        """
        初始化导入器

        :param file_path: 文件路径（支持 .xlsx, .csv）
        :param batch_size: 每批导入数量
        """
        self.file_path = file_path
        self.batch_size = batch_size
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicates': 0,
            'errors': []
        }

    def read_file(self) -> pd.DataFrame:
        """读取文件"""
        file_path = Path(self.file_path)

        if not file_path.exists():
            raise FileNotFoundError(f'文件不存在: {self.file_path}')

        print(f'📖 正在读取文件: {file_path.name}')

        if file_path.suffix == '.xlsx':
            df = pd.read_excel(file_path)
        elif file_path.suffix == '.csv':
            # 尝试多种编码格式
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']
            df = None
            last_error = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    print(f'✅ 使用 {encoding} 编码读取成功')
                    break
                except UnicodeDecodeError as e:
                    last_error = e
                    continue

            if df is None:
                raise ValueError(f'无法读取文件，尝试了以下编码均失败: {encodings}\n最后错误: {last_error}')
        else:
            raise ValueError(f'不支持的文件格式: {file_path.suffix}，仅支持 .xlsx 和 .csv')

        print(f'✅ 文件读取成功，共 {len(df)} 条数据')
        return df

    def validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证数据"""
        print('\n🔍 开始数据验证...')

        # 检查必需列
        required_columns = ['word', 'pinyin']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f'缺少必需列: {missing_columns}，当前列: {list(df.columns)}')

        # 删除空行
        original_count = len(df)
        df = df.dropna(subset=['word'])
        removed_count = original_count - len(df)

        if removed_count > 0:
            print(f'⚠️  已删除 {removed_count} 条空数据')

        # 去除首尾空格
        df['word'] = df['word'].astype(str).str.strip()
        df['pinyin'] = df['pinyin'].fillna('').astype(str).str.strip()

        # 去重
        original_count = len(df)
        df = df.drop_duplicates(subset=['word'], keep='first')
        duplicate_count = original_count - len(df)

        if duplicate_count > 0:
            print(f'⚠️  已去除 {duplicate_count} 条重复数据')
            self.stats['duplicates'] = duplicate_count

        print(f'✅ 数据验证完成，有效数据 {len(df)} 条\n')
        return df

    async def check_existing_words(self, words: list[str]) -> set[str]:
        """检查数据库中已存在的词语"""
        async with async_db_session() as session:
            stmt = select(GkCiyu.word).where(GkCiyu.word.in_(words))
            result = await session.execute(stmt)
            existing_words = {row[0] for row in result.fetchall()}
            return existing_words

    async def import_batch(self, batch_df: pd.DataFrame, batch_num: int, total_batches: int) -> None:
        """导入一批数据"""
        print(f'📦 正在导入第 {batch_num}/{total_batches} 批，共 {len(batch_df)} 条...')

        # 检查已存在的词语
        words = batch_df['word'].tolist()
        existing_words = await self.check_existing_words(words)

        # 过滤掉已存在的词语
        batch_df = batch_df[~batch_df['word'].isin(existing_words)]

        if len(existing_words) > 0:
            print(f'⚠️  跳过 {len(existing_words)} 条已存在的词语')
            self.stats['duplicates'] += len(existing_words)

        if len(batch_df) == 0:
            print('✅ 本批次无新数据需要导入\n')
            return

        # 准备插入数据
        ciyu_list = []
        for _, row in batch_df.iterrows():
            try:
                ciyu = GkCiyu(
                    word=row['word'],
                    pinyin=row['pinyin'] if row['pinyin'] else None,
                    category='成语',  # 默认分类
                    created_by=1,  # 系统管理员
                )
                ciyu_list.append(ciyu)
                self.stats['success'] += 1
            except Exception as e:
                error_msg = f"行数据错误: {row['word']} - {str(e)}"
                self.stats['errors'].append(error_msg)
                self.stats['failed'] += 1
                print(f'❌ {error_msg}')

        # 批量插入数据库
        if ciyu_list:
            async with async_db_session() as session:
                try:
                    session.add_all(ciyu_list)
                    await session.commit()
                    print(f'✅ 成功导入 {len(ciyu_list)} 条数据\n')
                except Exception as e:
                    await session.rollback()
                    error_msg = f'数据库插入失败: {str(e)}'
                    print(f'❌ {error_msg}\n')
                    self.stats['errors'].append(error_msg)
                    self.stats['failed'] += len(ciyu_list)
                    self.stats['success'] -= len(ciyu_list)

    async def import_data(self) -> None:
        """执行导入"""
        print('\n' + '='*60)
        print('🚀 开始导入词语数据')
        print('='*60 + '\n')

        # 读取文件
        df = self.read_file()
        self.stats['total'] = len(df)

        # 验证数据
        df = self.validate_data(df)

        # 分批导入
        total_batches = (len(df) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(df), self.batch_size):
            batch_df = df.iloc[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            await self.import_batch(batch_df, batch_num, total_batches)

        # 打印统计信息
        self.print_stats()

    def print_stats(self) -> None:
        """打印统计信息"""
        print('\n' + '='*60)
        print('📊 导入完成统计')
        print('='*60)
        print(f'总数据量:     {self.stats["total"]:>6} 条')
        print(f'成功导入:     {self.stats["success"]:>6} 条 ✅')
        print(f'重复跳过:     {self.stats["duplicates"]:>6} 条 ⚠️')
        print(f'导入失败:     {self.stats["failed"]:>6} 条 ❌')
        print('='*60)

        if self.stats['errors']:
            print('\n❌ 错误详情:')
            for error in self.stats['errors'][:10]:  # 只显示前10条错误
                print(f'  - {error}')
            if len(self.stats['errors']) > 10:
                print(f'  ... 还有 {len(self.stats["errors"]) - 10} 条错误')

        print('\n✨ 导入任务完成！\n')


async def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) < 2:
        print('❌ 使用方法: python import_ciyu.py <文件路径> [每批数量]')
        print('   示例: python import_ciyu.py data/ciyu.xlsx 1000')
        sys.exit(1)

    file_path = sys.argv[1]
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    try:
        importer = CiyuImporter(file_path, batch_size)
        await importer.import_data()
    except Exception as e:
        print(f'\n❌ 导入失败: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
