from fastapi import APIRouter

from backend.plugin.oc.api.v1.jobs import (
    announcement,
    application,
    company,
    config,
    crawler,
    feedback,
    quick_register,
    referral_code,
    resource,
    resume,
    website,
)

router = APIRouter(prefix='/jobs')

router.include_router(company.router, prefix='/company', tags=['公司信息'])
router.include_router(website.router, prefix='/website', tags=['公司网站'])
router.include_router(announcement.router, prefix='/announcement', tags=['招聘公告'])
router.include_router(application.router, prefix='/application', tags=['投递记录'])
router.include_router(crawler.router, prefix='/crawler', tags=['数据爬虫'])
router.include_router(resource.router, prefix='/resources', tags=['笔面试资料包'])
router.include_router(quick_register.router, prefix='/oc_user', tags=['快速注册'])
router.include_router(referral_code.router, prefix='/referral', tags=['内推码广场'])
router.include_router(resume.router, prefix='/resume', tags=['简历管理'])
router.include_router(config.router, prefix='/config', tags=['公开配置'])
router.include_router(feedback.router, prefix='/feedback', tags=['用户反馈'])
