#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class MembershipEntitlementCode:
    """会员权益编码"""

    QBANK_VIP_BANK: str = 'qbank.vip_bank'
    QBANK_SVIP_BANK: str = 'qbank.svip_bank'
    QBANK_ADVANCED_FILTER: str = 'qbank.advanced_filter'
    QBANK_KNOWLEDGE_PRACTICE: str = 'qbank.knowledge_practice'


QBANK_ENTITLEMENT_CODES: tuple[str, ...] = (
    MembershipEntitlementCode.QBANK_VIP_BANK,
    MembershipEntitlementCode.QBANK_SVIP_BANK,
    MembershipEntitlementCode.QBANK_ADVANCED_FILTER,
    MembershipEntitlementCode.QBANK_KNOWLEDGE_PRACTICE,
)
