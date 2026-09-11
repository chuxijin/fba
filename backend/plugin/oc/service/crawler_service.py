import asyncio
import html as html_lib
import re

from datetime import date, datetime
from typing import Any

import httpx
import sqlalchemy as sa

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.log import log
from backend.plugin.oc.model import OCCompany, OCCompanyWebsite, OCRecruitAnnouncement
from backend.utils.timezone import timezone


class GiveMeOCCrawler:
    """GiveMeOC招聘信息爬虫"""

    def __init__(self) -> None:
        self.base_url = 'https://www.givemeoc.com/wp-admin/admin-ajax.php'
        self.page_urls = {
            'campus': 'https://www.givemeoc.com/',
            'intern': 'https://www.givemeoc.com/internship',
        }
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.givemeoc.com',
            'Referer': 'https://www.givemeoc.com/',
        }
        # 缓存的 nonce 值（会自动获取）
        self._cached_nonce: dict[str, str] = {}

    async def fetch_nonce(self, job_type: str = 'campus', cookie: str | None = None) -> str | None:
        """
        从网页中自动提取 nonce 值

        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :param cookie: Cookie值（可选）
        :return: nonce 值，获取失败返回 None
        """
        page_url = self.page_urls.get(job_type, self.page_urls['campus'])

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        if cookie:
            headers['Cookie'] = cookie

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(page_url, headers=headers)
                response.raise_for_status()
                html = response.text

                # 根据 job_type 选择正确的变量名
                # 校招页面使用 crt_ajax.nonce，实习页面使用 int_ajax.nonce
                var_name = 'int_ajax' if job_type == 'intern' else 'crt_ajax'

                # 匹配 var crt_ajax = {"nonce":"xxx"} 或 var int_ajax = {"nonce":"xxx"}
                pattern = rf'var\s+{var_name}\s*=\s*\{{[^}}]*"nonce"\s*:\s*"([a-f0-9]+)"'
                match = re.search(pattern, html)

                if match:
                    nonce = match.group(1)
                    log.info(f'成功获取 {job_type} 的 nonce: {nonce}')
                    self._cached_nonce[job_type] = nonce
                    return nonce
                log.warning(f'未能从页面提取 nonce，job_type={job_type}')
                return None

        except Exception as e:
            log.error(f'获取 nonce 失败: {e}')
            return None

    async def fetch_page_data(
        self, page: int = 1, job_type: str = 'campus', nonce: str | None = None, cookie: str | None = None, **filters
    ) -> dict[str, Any]:
        """
        获取指定页面的招聘数据

        :param page: 页码
        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :param nonce: nonce值（可选，如果不提供则自动获取）
        :param cookie: Cookie值（可选）
        :param filters: 过滤条件
        :return: API响应数据
        """
        # 使用传入的 nonce，或从缓存获取，或自动获取新的
        if nonce is None:
            nonce = self._cached_nonce.get(job_type)
            if not nonce:
                nonce = await self.fetch_nonce(job_type, cookie)
                if not nonce:
                    log.error(f'无法获取 nonce，job_type={job_type}')
                    return {}

        # 构建headers，如果有cookie则添加
        headers = self.base_headers.copy()
        if cookie:
            headers['Cookie'] = cookie

        if job_type == 'intern':
            # 实习数据
            data = {
                'action': 'int_filter_companies',
                'nonce': nonce,
                'paged': str(page),
                'company_name': filters.get('company_name', ''),
                'company_type': filters.get('company_type', ''),
                'location': filters.get('location', ''),
                'recruitment_type': filters.get('recruitment_type', ''),
                'target_candidates': filters.get('target_candidates', ''),
                'position': filters.get('position', ''),
                'progress_status': filters.get('progress_status', ''),
            }
        else:
            # 校招数据
            data = {
                'action': 'filter_companies',
                'nonce': nonce,
                'paged': str(page),
                'company_name': filters.get('company_name', ''),
                'company_type': filters.get('company_type', ''),
                'location': filters.get('location', ''),
                'recruitment_type': filters.get('recruitment_type', ''),
                'target_candidates': filters.get('target_candidates', ''),
                'position': filters.get('position', ''),
                'progress_status': filters.get('progress_status', ''),
                'should_increment_counter': '1',
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, data=data, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log.error(f'获取第 {page} 页数据失败: {e}')
            return {}

    def parse_html_to_jobs(self, html: str, job_type: str = 'campus') -> list[dict[str, Any]]:  # noqa: C901
        """
        解析HTML内容为招聘信息列表

        :param html: HTML内容
        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :return: 招聘信息列表
        """
        jobs = []

        # 根据数据类型选择CSS class前缀
        prefix = 'int' if job_type == 'intern' else 'crt'

        # 匹配表格行 <tr data-id="...">
        tr_pattern = r'<tr data-id="(\d+)".*?>(.*?)</tr>'
        tr_matches = re.findall(tr_pattern, html, re.DOTALL)

        for data_id, tr_content in tr_matches:
            job_data = {
                'source_id': int(data_id) if data_id.isdigit() else None,
                'company_name': '',
                'company_type': '',
                'company_size': None,
                'industry': '',
                'recruitment_type': '',
                'location': '',
                'recruit_target': '',
                'positions': '',
                'update_time': None,
                'deadline': None,
                'apply_link': None,
                'notice_link': None,
                'referral_code': None,
                'exam_info': None,
                'remark': None,
            }

            # 提取公司名称
            company_match = re.search(rf'<td class="{prefix}-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if company_match:
                job_data['company_name'] = re.sub(r'<[^>]+>', '', company_match.group(1)).strip()

            # 提取公司类型
            type_match = re.search(
                rf'<span class="{prefix}-badge {prefix}-type-([^"]*)"[^>]*>([^<]*)</span>', tr_content
            )
            if type_match:
                job_data['company_type'] = type_match.group(2).strip()

            # 提取公司规模
            company_size_match = re.search(
                rf'<td class="{prefix}-col-company-size"[^>]*>(.*?)</td>', tr_content, re.DOTALL
            )
            if company_size_match:
                company_size_text = re.sub(r'<[^>]+>', '', company_size_match.group(1)).strip()
                if company_size_text and company_size_text != '-':
                    job_data['company_size'] = company_size_text

            # 提取行业（第二个col-company）
            company_matches = re.findall(rf'<td class="{prefix}-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if len(company_matches) >= 2:
                job_data['industry'] = re.sub(r'<[^>]+>', '', company_matches[1]).strip()

            # 提取招聘类型
            recruitment_match = re.search(
                rf'<span class="{prefix}-badge {prefix}-recruitment-([^"]*)"[^>]*>([^<]*)</span>', tr_content
            )
            if recruitment_match:
                job_data['recruitment_type'] = recruitment_match.group(2).strip()

            # 提取工作地点
            location_match = re.search(rf'<td class="{prefix}-col-location"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if location_match:
                job_data['location'] = re.sub(r'<[^>]+>', '', location_match.group(1)).strip()

            # 提取招聘对象
            target_match = re.search(
                rf'<span class="{prefix}-badge {prefix}-target-([^"]*)"[^>]*>([^<]*)</span>', tr_content
            )
            if target_match:
                job_data['recruit_target'] = re.sub(r'<[^>]+>', '', target_match.group(1)).strip()

            # 提取岗位信息
            position_match = re.search(rf'<span class="{prefix}-position-tag"[^>]*>(.*?)</span>', tr_content, re.DOTALL)
            if position_match:
                job_data['positions'] = re.sub(r'<[^>]+>', '', position_match.group(1)).strip()

            # 提取更新时间
            update_time_match = re.search(
                rf'<td class="{prefix}-col-update-time"[^>]*>(.*?)</td>', tr_content, re.DOTALL
            )
            if update_time_match:
                update_time_text = re.sub(r'<[^>]+>', '', update_time_match.group(1)).strip()
                if update_time_text:
                    try:
                        job_data['update_time'] = datetime.strptime(  # noqa: DTZ007
                            update_time_text, '%Y-%m-%d'
                        ).date()
                    except Exception:
                        pass

            # 提取截止日期
            deadline_match = re.search(rf'<td class="{prefix}-col-deadline"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if deadline_match:
                deadline_text = re.sub(r'<[^>]+>', '', deadline_match.group(1)).strip()
                if deadline_text and deadline_text != '招满为止' and deadline_text != '-':
                    # 尝试多种日期格式
                    for fmt in ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d']:
                        try:
                            job_data['deadline'] = datetime.strptime(deadline_text, fmt).strftime(  # noqa: DTZ007
                                '%Y-%m-%d'
                            )
                            break
                        except Exception:
                            continue

            # 提取投递链接
            link_match = re.search(
                rf'<td class="{prefix}-col-links"[^>]*>.*?<a href="([^"]*)"[^>]*>投递</a>', tr_content, re.DOTALL
            )
            if link_match:
                link = link_match.group(1).strip()
                if link and link != '#':
                    job_data['apply_link'] = link

            # 提取招聘公告链接
            notice_match = re.search(
                rf'<td class="{prefix}-col-notice"[^>]*>.*?<a href="([^"]*)"[^>]*>公告</a>', tr_content, re.DOTALL
            )
            if notice_match:
                link = notice_match.group(1).strip()
                if link and link != '#':
                    job_data['notice_link'] = link

            # 提取内推码
            referral_match = re.search(rf'<td class="{prefix}-col-referral"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if referral_match:
                referral_text = re.sub(r'<[^>]+>', '', referral_match.group(1)).strip()
                if referral_text and referral_text != '-':
                    job_data['referral_code'] = referral_text

            # 提取笔试信息
            exam_info_match = re.search(rf'<td class="{prefix}-col-exam-info"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if exam_info_match:
                exam_info_text = re.sub(r'<[^>]+>', '', exam_info_match.group(1)).strip()
                if exam_info_text and exam_info_text != '-':
                    job_data['exam_info'] = exam_info_text

            # 提取备注
            notes_match = re.search(rf'<td class="{prefix}-col-notes"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if notes_match:
                notes_text = re.sub(r'<[^>]+>', '', notes_match.group(1)).strip()
                if notes_text and notes_text != '-':
                    job_data['remark'] = notes_text

            # 只有公司名称和岗位不为空才添加
            if job_data['company_name'] and job_data['positions']:
                jobs.append(job_data)

        return jobs

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        """清理 HTML 实体并规范化空值"""
        if value is None:
            return None
        cleaned = html_lib.unescape(value).strip()
        return cleaned or None

    @staticmethod
    def _is_expired(deadline: str | None, today: date) -> bool:
        """判断公告是否已过截止日期"""
        if not deadline:
            return False
        try:
            end_date = datetime.strptime(deadline, '%Y-%m-%d').date()  # noqa: DTZ007
        except ValueError:
            return False
        return end_date < today

    async def _upsert_company(
        self,
        db: AsyncSession,
        company_name: str,
        company_type: str | None,
        industry: str | None,
        company_size: str | None,
    ) -> OCCompany:
        """
        按公司名称 upsert 公司，仅回填 NULL 字段，不覆盖已有值

        :param db: 数据库会话
        :param company_name: 公司名称
        :param company_type: 公司类型
        :param industry: 所属行业
        :param company_size: 公司规模
        :return: 公司 ORM 对象
        """
        company = await db.scalar(sa.select(OCCompany).where(OCCompany.name == company_name))
        if company is None:
            company = OCCompany(
                name=company_name,
                company_type=company_type,
                industry=industry,
                company_size=company_size,
                extra_info={},
            )
            db.add(company)
            await db.flush()
            return company

        # 仅回填空字段，保护人工维护数据
        changed = False
        if company.company_type is None and company_type:
            company.company_type = company_type
            changed = True
        if company.industry is None and industry:
            company.industry = industry
            changed = True
        if company.company_size is None and company_size:
            company.company_size = company_size
            changed = True
        if changed:
            await db.flush()
        return company

    async def _upsert_websites(self, db: AsyncSession, company: OCCompany, job_data: dict[str, Any]) -> int:
        """
        公司网站 upsert（一对多积累，跨帖去重）

        按来源命名：apply_link -> {公司名}投递入口，notice_link -> {公司名}招聘公告；
        两链接相同时只记一条，以投递入口为准

        :param db: 数据库会话
        :param company: 公司 ORM 对象
        :param job_data: 单条招聘数据
        :return: 新增网站数量
        """
        link_pairs: list[tuple[str | None, str]] = [
            (job_data.get('apply_link'), f'{company.name}投递入口'),
            (job_data.get('notice_link'), f'{company.name}招聘公告'),
        ]
        added = 0
        seen_urls: set[str] = set()
        for url, website_name in link_pairs:
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            exists = await db.scalar(
                sa.select(OCCompanyWebsite.id).where(
                    OCCompanyWebsite.company_id == company.id, OCCompanyWebsite.url == url
                )
            )
            if exists is None:
                db.add(OCCompanyWebsite(company_id=company.id, url=url, name=website_name))
                added += 1
        if added:
            await db.flush()
        return added

    async def _upsert_announcement(
        self, db: AsyncSession, company: OCCompany, job_data: dict[str, Any], source_key: str
    ) -> str:
        """
        公告按 source_key upsert（一帖一公告）

        :param db: 数据库会话
        :param company: 公司 ORM 对象
        :param job_data: 单条招聘数据
        :param source_key: 来源幂等键（如 campus:25567）
        :return: 'created' / 'updated'
        """
        announcement = await db.scalar(
            sa.select(OCRecruitAnnouncement).where(OCRecruitAnnouncement.source_key == source_key)
        )

        if announcement is None:
            announcement = OCRecruitAnnouncement(
                company_id=company.id,
                title=f'{company.name}公告详情',
                recruitment_type=job_data['recruitment_type'] or '未知',
                recruit_target=self._clean_text(job_data.get('recruit_target')) or '未知',
                positions=self._clean_text(job_data.get('positions')),
                end_time=job_data.get('deadline'),
                location=self._clean_text(job_data.get('location')) or '未知',
                exam_info=self._clean_text(job_data.get('exam_info')),
                referral_code=self._clean_text(job_data.get('referral_code')),
                source_key=source_key,
                remark=f'源站更新: {job_data["update_time"] or timezone.now().date()}',
            )
            db.add(announcement)
            await db.flush()
            return 'created'

        # 已存在：以源站最新数据为准更新
        announcement.company_id = company.id
        announcement.recruitment_type = job_data['recruitment_type'] or '未知'
        announcement.recruit_target = self._clean_text(job_data.get('recruit_target')) or '未知'
        announcement.positions = self._clean_text(job_data.get('positions'))
        announcement.end_time = job_data.get('deadline')
        announcement.location = self._clean_text(job_data.get('location')) or '未知'
        announcement.exam_info = self._clean_text(job_data.get('exam_info'))
        announcement.referral_code = self._clean_text(job_data.get('referral_code'))
        announcement.remark = f'源站更新: {job_data["update_time"] or timezone.now().date()}'
        await db.flush()
        return 'updated'

    async def save_job_data(self, db: AsyncSession, job_data: dict[str, Any], job_type: str, today: date) -> str:
        """
        保存单条招聘数据（公司 upsert -> 网站积累 -> 公告 upsert）

        :param db: 数据库会话
        :param job_data: 单条招聘数据
        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :param today: 当前日期
        :return: 'skipped_expired' / 'created' / 'updated'
        """
        # 过期公告直接跳过，防止已清理数据被源站置顶帖"复活"
        if self._is_expired(job_data.get('deadline'), today):
            return 'skipped_expired'

        company = await self._upsert_company(
            db,
            company_name=job_data['company_name'],
            company_type=self._clean_text(job_data.get('company_type')),
            industry=self._clean_text(job_data.get('industry')),
            company_size=self._clean_text(job_data.get('company_size')),
        )
        await self._upsert_websites(db, company, job_data)
        source_key = f'{job_type}:{job_data["source_id"]}'
        return await self._upsert_announcement(db, company, job_data, source_key)

    async def _crawl_page(
        self,
        db: AsyncSession,
        page: int,
        job_type: str,
        nonce: str,
        cookie: str | None,
        delay: float,
        start_page: int,
        today: date,
    ) -> dict[str, Any]:
        """
        爬取并保存单页数据

        :param db: 数据库会话
        :param page: 页码
        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :param nonce: nonce 值
        :param cookie: Cookie值（可选）
        :param delay: 请求间隔（秒）
        :param start_page: 开始页码
        :param today: 当前日期
        :return: {'crawled': int, 'created': int, 'updated': int, 'expired': int, 'errors': list}
        """
        stats = {'crawled': 0, 'created': 0, 'updated': 0, 'expired': 0, 'errors': []}

        response_data = await self.fetch_page_data(page, job_type, nonce, cookie)

        if not response_data.get('success'):
            error_msg = f'第 {page} 页获取失败'
            log.warning(error_msg)
            stats['errors'].append(error_msg)
            return stats

        # 解析HTML
        html = response_data.get('data', {}).get('html', '')
        if not html:
            log.warning(f'第 {page} 页无数据')
            return stats

        jobs = self.parse_html_to_jobs(html, job_type)
        stats['crawled'] = len(jobs)
        log.info(f'第 {page} 页解析到 {len(jobs)} 条招聘信息')

        # 保存到数据库
        for job_data in jobs:
            # 确保有 source_id
            if not job_data.get('source_id'):
                log.warning(f'跳过没有 source_id 的数据: {job_data["company_name"]}')
                continue

            # 用 savepoint 隔离每条记录，单条失败不影响其他
            try:
                async with db.begin_nested():
                    result = await self.save_job_data(db, job_data, job_type, today)
                if result == 'created':
                    stats['created'] += 1
                elif result == 'updated':
                    stats['updated'] += 1
                else:
                    stats['expired'] += 1
            except Exception as e:
                log.warning(f'保存失败: {job_data["company_name"]} - {e!s}')
                stats['errors'].append(f'保存失败: {job_data["company_name"]} - {e!s}')
                continue

        # 请求间隔（倒序爬取，只要不是最后一页就需要延迟）
        if page > start_page:
            await asyncio.sleep(delay)

        return stats

    async def crawl_and_save(
        self,
        db: AsyncSession,
        start_page: int = 1,
        end_page: int = 5,
        job_type: str = 'campus',
        delay: float = 1.0,
        nonce: str | None = None,
        cookie: str | None = None,
    ) -> dict[str, Any]:
        """
        爬取并保存数据

        :param db: 数据库会话
        :param start_page: 开始页码
        :param end_page: 结束页码
        :param job_type: 数据类型 ('campus'=校招, 'intern'=实习)
        :param delay: 请求间隔（秒）
        :param nonce: nonce值（可选，如果不提供则自动获取）
        :param cookie: Cookie值（可选）
        :return: 统计信息
        """
        total_crawled = 0
        total_created = 0
        total_skipped = 0
        total_expired = 0
        errors = []

        job_type_name = '校招' if job_type == 'campus' else '实习'
        today = timezone.now().date()

        # 如果没有传入 nonce，自动获取
        if not nonce:
            log.info('未传入 nonce，正在自动从网页获取...')
            nonce = await self.fetch_nonce(job_type, cookie)
            if not nonce:
                return {
                    'total_crawled': 0,
                    'total_created': 0,
                    'total_updated': 0,
                    'total_skipped': 0,
                    'total_expired': 0,
                    'errors': ['无法自动获取 nonce，请手动传入或检查网站是否可访问'],
                }
            log.info(f'自动获取到 nonce: {nonce}')

        log.info(f'开始爬取{job_type_name}数据，页码范围: {end_page}-{start_page}（倒序）')

        # 从后往前爬，确保最新数据最后写入
        for page in range(end_page, start_page - 1, -1):
            try:
                page_stats = await self._crawl_page(db, page, job_type, nonce, cookie, delay, start_page, today)
            except Exception as e:
                error_msg = f'处理第 {page} 页时出错: {e!s}'
                log.error(error_msg)
                errors.append(error_msg)
                continue
            total_crawled += page_stats['crawled']
            total_created += page_stats['created']
            total_skipped += page_stats['updated']
            total_expired += page_stats['expired']
            errors.extend(page_stats['errors'])

        log.info(
            f'爬取完成！总爬取: {total_crawled}, 新增: {total_created}, '
            f'更新: {total_skipped}, 过期跳过: {total_expired}'
        )

        return {
            'total_crawled': total_crawled,
            'total_created': total_created,
            'total_updated': total_skipped,
            'total_expired': total_expired,
            'errors': errors[:10],  # 只返回前10个错误
        }


# 创建爬虫实例
crawler = GiveMeOCCrawler()
