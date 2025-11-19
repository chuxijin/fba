import asyncio
from datetime import datetime
from typing import Any
from bs4 import BeautifulSoup

from backend.app.job.schema.job_posting import CreateJobPosting
from backend.app.job.service.job_posting_service import job_posting_service
from backend.database.db import async_db_session # Assuming async_session is correctly configured and imported

# Mock Request object for simulating FastAPI's request context
class MockUser:
    def __init__(self, user_id: int):
        self.id = user_id

class MockRequest:
    def __init__(self, user_id: int):
        self.user = MockUser(user_id)
        # Assuming async_session is a sessionmaker or similar factory
        self.state = type('State', (object,), {'async_db_session': async_db_session})()

async def parse_and_save_job_posting():
    html_data = """
    <tr>
        <td class="crt-col-company">德邦快递</td>
        <td class="crt-col-type"><span class="crt-badge crt-type-民企">民企</span></td>
        <td class="crt-col-company">物流/供应链</td>
        <td class="crt-col-recruitment-type"><span class="crt-badge crt-recruitment-秋招">秋招</span></td>
        <td class="crt-col-location">全国,上海</td>
        <td class="crt-col-target"><span class="crt-badge crt-target-2026届">2026届</span></td>
        <td class="crt-col-position">
            <div class="crt-positions">
                <span class="crt-position-tag">经营方向 运营方向 销售方向 运营规划类 解决方案类 产品类 财审类 战略支持类 品牌营销类 仓储与供应链类 人力资源类 科技类 客户体验类</span>                                </div>
        </td>
        <td class="crt-col-status">
            <select class="crt-status-select" data-company-id="11016" data-original-status="未开始">
                <option value="未投递" >未投递</option>
                <option value="已投递" >已投递</option>
                <option value="已笔试" >已笔试</option>
                <option value="已面试" >已面试</option>
                <option value="已挂" >已挂</option>
                <option value="面试通过" >面试通过</option>
                <option value="暂不投递" >暂不投递</option>
            </select>
        </td>
        <td class="crt-col-update-time">2025-09-27</td>
        <td class="crt-col-deadline">招满为止</td>
        <td class="crt-col-links">
            <a href="http://zhaopin.deppon.com/campus" target="_blank" class="crt-link">投递</a>
        </td>
        <td class="crt-col-notice">
            <a href="https://mp.weixin.qq.com/s/gAMUuTFMCA4PY6uUbhTY3A" target="_blank" class="crt-link crt-notice-link">公告</a>
        </td>
        <td class="crt-col-referral">
            -
        </td>
        <td class="crt-col-notes">
            -
        </td>
    </tr>
    """

    soup = BeautifulSoup(html_data, 'html.parser')

    # Extracting company_name and industry carefully due to repeating class
    company_name_tds = soup.find_all('td', class_='crt-col-company')
    company_name = company_name_tds[0].get_text(strip=True) if company_name_tds else None
    industry = company_name_tds[1].get_text(strip=True) if len(company_name_tds) > 1 else None

    company_type_tag = soup.find('td', class_='crt-col-type')
    company_type = company_type_tag.find('span').get_text(strip=True) if company_type_tag and company_type_tag.find('span') else None
    
    recruitment_type_tag = soup.find('td', class_='crt-col-recruitment-type')
    recruitment_type = recruitment_type_tag.find('span').get_text(strip=True) if recruitment_type_tag and recruitment_type_tag.find('span') else None
    
    work_location = soup.find('td', class_='crt-col-location').get_text(strip=True)
    recruitment_object_tag = soup.find('td', class_='crt-col-target')
    recruitment_object = recruitment_object_tag.find('span').get_text(strip=True) if recruitment_object_tag and recruitment_object_tag.find('span') else None
    
    position_div = soup.find('td', class_='crt-col-position').find('div', class_='crt-positions')
    position = position_div.get_text(strip=True) if position_div else None

    delivery_start_str = soup.find('td', class_='crt-col-update-time').get_text(strip=True)
    delivery_start = datetime.strptime(delivery_start_str, '%Y-%m-%d') if delivery_start_str else None

    delivery_end_str = soup.find('td', class_='crt-col-deadline').get_text(strip=True)
    delivery_end = None
    if delivery_end_str and delivery_end_str.lower() != '招满为止':
        try:
            delivery_end = datetime.strptime(delivery_end_str, '%Y-%m-%d')
        except ValueError:
            pass # Keep as None if parsing fails

    delivery_link_tag = soup.find('td', class_='crt-col-links').find('a')
    delivery_link = delivery_link_tag['href'] if delivery_link_tag else None

    recruitment_announcement_tag = soup.find('td', class_='crt-col-notice').find('a')
    recruitment_announcement = recruitment_announcement_tag['href'] if recruitment_announcement_tag else None

    referral_code_text = soup.find('td', class_='crt-col-referral').get_text(strip=True)
    referral_code = referral_code_text if referral_code_text and referral_code_text != '-' else None

    remark_text = soup.find('td', class_='crt-col-notes').get_text(strip=True)
    remark = remark_text if remark_text and remark_text != '-' else None

    # Fields not directly in HTML, setting to None
    salary_range = None
    is_exempt_from_written_test = None
    logo_url = None

    job_posting_data = CreateJobPosting(
        company_name=company_name,
        company_type=company_type,
        industry=industry,
        recruitment_type=recruitment_type,
        work_location=work_location,
        recruitment_object=recruitment_object,
        position=position,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        delivery_link=delivery_link,
        recruitment_announcement=recruitment_announcement,
        referral_code=referral_code,
        remark=remark,
        salary_range=salary_range,
        is_exempt_from_written_test=is_exempt_from_written_test,
        logo_url=logo_url
    )
    
    # Mock a request object for the service layer
    # IMPORTANT: Replace 1 with an actual existing user ID from your database
    mock_user_id = 1 
    mock_request = MockRequest(user_id=mock_user_id)

    print("Parsed Job Posting Data:", job_posting_data.model_dump_json(indent=2))

    try:
        # Save to database
        created_job_posting = await job_posting_service.create(mock_request, job_posting_data, mock_request.user.id)
        print("Successfully saved Job Posting with ID:", created_job_posting.id)
    except Exception as e:
        print(f"Error saving Job Posting: {e}")

if __name__ == "__main__":
    asyncio.run(parse_and_save_job_posting())
