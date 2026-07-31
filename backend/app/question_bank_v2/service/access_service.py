from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import ReasonCode, ResourceType
from backend.app.access.engine.decide import access_decision_engine
from backend.app.access.engine.resolver import rule_resolver
from backend.app.access.schema.engine import AccessContext, Decision
from backend.app.question_bank_v2.crud.crud_bank import bank_dao
from backend.app.question_bank_v2.model.bank import QbBank
from backend.common.exception import errors
from backend.utils.timezone import timezone


class BankAccessService:
    """题库 V2 准入服务类"""

    @staticmethod
    async def ensure_bank_access(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
        raise_on_deny: bool = True,
    ) -> tuple[QbBank, Decision]:
        """
        校验用户是否可以进入题库刷题

        权益始终绑定题库稳定身份 ID。题库不使用试看配额，目录可见性也不等于刷题权限。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库稳定身份 ID
        :param raise_on_deny: 权限不足时是否抛出异常
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if bank is None or bank.status != 'active' or bank.current_revision_id is None:
            raise errors.NotFoundError(msg='题库不存在或尚未发布')

        if bank.owner_id == user_id:
            return bank, Decision.allow(reason_code=ReasonCode.OWNERSHIP)

        if bank.visibility == 'private':
            decision = Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)
        else:
            decision = await access_decision_engine.decide(
                db,
                AccessContext(
                    user_id=user_id,
                    resource_type=ResourceType.QBANK,
                    resource_id=bank.id,
                    action='practice',
                    allow_trial=False,
                    consume_trial=False,
                ),
            )

        if raise_on_deny and not decision.allowed:
            raise errors.ForbiddenError(msg='当前账号没有此题库的刷题权限')
        return bank, decision

    @staticmethod
    async def describe_bank_access(
        *,
        db: AsyncSession,
        bank: QbBank,
        user_id: int | None,
    ) -> tuple[bool, bool | None]:
        """
        描述题库的权益门槛与当前调用者的刷题准入，供详情页在点击前给出正确文案

        :param db: 数据库会话
        :param bank: 题库稳定身份
        :param user_id: 调用者用户 ID；匿名访问时为 None
        :return: (题库是否存在权益门槛, 当前调用者是否可刷题；匿名时为 None)
        """
        rules = await rule_resolver.resolve(
            db,
            resource_type=ResourceType.QBANK,
            resource_id=bank.id,
            ts=timezone.now(),
        )
        requires_entitlement = bool(rules) or bank.visibility == 'private'
        if user_id is None:
            return requires_entitlement, None

        _, decision = await BankAccessService.ensure_bank_access(
            db=db,
            user_id=user_id,
            bank_id=bank.id,
            raise_on_deny=False,
        )
        return requires_entitlement, decision.allowed


bank_access_service: BankAccessService = BankAccessService()
