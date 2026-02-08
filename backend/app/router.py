from fastapi import APIRouter

from backend.app.actcode.api.router import v1 as actcode_v1
from backend.app.admin.api.router import v1 as admin_v1
from backend.app.bili.api.router import v1 as bili_v1
from backend.app.task.api.router import v1 as task_v1
from backend.app.coulddrive.api.router import v1 as coulddrive_v1
from backend.app.mcp.api.router import v1 as mcp_v1
from backend.app.social.api.router import v1 as social_v1
from backend.app.job.router import v1 as job_v1
from backend.app.question_bank.api.router import v1 as question_bank_v1
from backend.app.gongkao.api.router import v1 as gongkao_v1
from backend.app.jia.api.router import v1 as jia_v1

router = APIRouter()

router.include_router(actcode_v1)
router.include_router(admin_v1)
router.include_router(bili_v1)
router.include_router(task_v1)
router.include_router(job_v1)
router.include_router(coulddrive_v1)
router.include_router(mcp_v1)
router.include_router(social_v1)
router.include_router(question_bank_v1)
router.include_router(gongkao_v1)
router.include_router(jia_v1)
