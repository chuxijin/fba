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
        question_ordinal: int | None = None,
        question_total: int | None = None,
        consume: bool = False,
        raise_on_deny: bool = True,
    ) -> tuple[QbBank, Decision]:
        """
        校验用户是否可以进入题库刷题

        权益始终绑定题库稳定身份 ID。目录可见性不等于刷题权限。

        传入 question_ordinal 时启用试看策略: 未付费用户可按运营配置的
        trial_policy(如前 5 题)体验, 耗尽后由引擎返回 TRIAL_EXHAUSTED。
        不传则退化为纯准入判定, 用于"能否进入题库"这类没有具体题目的场景。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库稳定身份 ID
        :param question_ordinal: 当前题目在题库中的序号(0 起), 空则不启用试看
        :param question_total: 题库题目总数, 供按比例试看使用
        :param consume: 是否消耗计量额度与按日试看次数
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
                    allow_trial=question_ordinal is not None,
                    consume_trial=consume,
                    sub_resource_ordinal=question_ordinal,
                    sub_resource_total=question_total,
                ),
            )

        if raise_on_deny and not decision.allowed:
            raise errors.ForbiddenError(msg=BankAccessService._deny_message(decision))
        return bank, decision

    @staticmethod
    def _deny_message(decision: Decision) -> str:
        """
        按拒绝原因给出可引导付费的提示

        :param decision: 权益决策
        :return:
        """
        if decision.reason_code == ReasonCode.TRIAL_EXHAUSTED:
            return '免费试刷已结束，开通会员可继续刷题'
        if decision.reason_code == ReasonCode.QUOTA_EXHAUSTED:
            return '本期刷题额度已用完，可升级会员获取更多额度'
        return '当前账号没有此题库的刷题权限，开通对应权益后可刷题'

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
