from fastapi import APIRouter

from backend.app.access.api.router import v1 as access_v1
from backend.app.actcode.api.router import v1 as actcode_v1
from backend.app.admin.api.router import v1 as admin_v1
from backend.app.challenge.api.router import v1 as challenge_v1
from backend.app.cms.api.router import v1 as cms_v1
from backend.app.content.api.router import v1 as content_v1
from backend.app.coulddrive.api.router import v1 as coulddrive_v1
from backend.app.gongkao.api.router import v1 as gongkao_v1
from backend.app.growth.api import v1 as growth_v1
from backend.app.halo.api.router import v1 as halo_v1
from backend.app.invite.api.router import v1 as invite_v1
from backend.app.mcp.api.router import v1 as mcp_v1
from backend.app.mydrive.api.router import v1 as mydrive_v1
from backend.app.payment.api.router import v1 as payment_v1
from backend.app.pomodoro.api.router import v1 as pomodoro_v1
from backend.app.quest.api.router import v1 as quest_v1
from backend.app.question_bank.api.router import v1 as question_bank_v1
from backend.app.question_bank_v2.api.router import v1 as question_bank_v2_v1
from backend.app.question_generation.api.router import v1 as question_generation_v1
from backend.app.social.api.router import v1 as social_v1
from backend.app.study_plan.api.router import v1 as study_plan_v1
from backend.app.task.api.router import v1 as task_v1
from backend.app.vocab.api.router import v1 as vocab_v1

router = APIRouter()

router.include_router(access_v1)
router.include_router(growth_v1)
router.include_router(actcode_v1)
router.include_router(admin_v1)
router.include_router(task_v1)
router.include_router(coulddrive_v1)
router.include_router(mcp_v1)
router.include_router(mydrive_v1)
router.include_router(social_v1)
router.include_router(question_bank_v1)
router.include_router(question_bank_v2_v1)
router.include_router(question_generation_v1)
router.include_router(gongkao_v1)
router.include_router(halo_v1)
router.include_router(invite_v1)
router.include_router(payment_v1)
router.include_router(content_v1)
router.include_router(quest_v1)
router.include_router(cms_v1)
router.include_router(challenge_v1)
router.include_router(vocab_v1)
router.include_router(study_plan_v1)
router.include_router(pomodoro_v1)
