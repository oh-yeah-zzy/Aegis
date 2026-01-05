"""
威胁检测服务模块

检测和响应以下安全威胁：
- 暴力破解攻击：单 IP 短时间内大量登录失败
- 凭据填充攻击：单 IP 尝试多个不同用户登录
- 异常登录模式：检测可疑的登录行为

当检测到威胁时，可以自动响应：
- 记录安全事件
- 自动封禁 IP
- 触发告警（可扩展）
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_config import security_settings

logger = logging.getLogger(__name__)


class ThreatDetector:
    """
    威胁检测器

    分析认证事件日志，检测各种安全威胁。
    检测到威胁后可以自动触发响应措施。
    """

    async def check_brute_force(
        self,
        ip: str,
        db: AsyncSession,
    ) -> bool:
        """
        检测暴力破解攻击

        规则：单 IP 在时间窗口内登录失败次数超过阈值

        Args:
            ip: 客户端 IP 地址
            db: 数据库会话

        Returns:
            True 如果检测到暴力破解攻击
        """
        if not security_settings.threat_detection_enabled:
            return False

        # 避免循环导入
        from app.db.models.audit import AuthEvent

        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=security_settings.threat_brute_force_window
        )

        # 查询该 IP 在时间窗口内的登录失败次数
        result = await db.execute(
            select(func.count(AuthEvent.id)).where(
                AuthEvent.ip == ip,
                AuthEvent.event_type == "login",
                AuthEvent.result == "failure",
                AuthEvent.ts >= window_start,
            )
        )
        count = result.scalar() or 0

        is_attack = count >= security_settings.threat_brute_force_threshold

        if is_attack:
            logger.warning(
                f"检测到暴力破解攻击: IP={ip}, "
                f"失败次数={count}, "
                f"阈值={security_settings.threat_brute_force_threshold}, "
                f"时间窗口={security_settings.threat_brute_force_window}秒"
            )

        return is_attack

    async def check_credential_stuffing(
        self,
        ip: str,
        db: AsyncSession,
    ) -> bool:
        """
        检测凭据填充攻击

        规则：单 IP 在时间窗口内尝试登录多个不同用户

        Args:
            ip: 客户端 IP 地址
            db: 数据库会话

        Returns:
            True 如果检测到凭据填充攻击
        """
        if not security_settings.threat_detection_enabled:
            return False

        # 避免循环导入
        from app.db.models.audit import AuthEvent

        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=security_settings.threat_credential_stuffing_window
        )

        # 查询该 IP 在时间窗口内尝试的不同用户数
        # 通过 details 字段中的用户名或 principal_id 来统计
        result = await db.execute(
            select(func.count(func.distinct(AuthEvent.principal_id))).where(
                AuthEvent.ip == ip,
                AuthEvent.event_type == "login",
                AuthEvent.result == "failure",
                AuthEvent.ts >= window_start,
                AuthEvent.principal_id.isnot(None),  # 只统计有用户信息的记录
            )
        )
        unique_users = result.scalar() or 0

        is_attack = unique_users >= security_settings.threat_credential_stuffing_threshold

        if is_attack:
            logger.warning(
                f"检测到凭据填充攻击: IP={ip}, "
                f"尝试用户数={unique_users}, "
                f"阈值={security_settings.threat_credential_stuffing_threshold}, "
                f"时间窗口={security_settings.threat_credential_stuffing_window}秒"
            )

        return is_attack

    async def auto_ban_ip(
        self,
        ip: str,
        reason: str,
        ban_type: str,
        db: AsyncSession,
        duration: Optional[int] = None,
    ) -> Optional[str]:
        """
        自动封禁 IP

        Args:
            ip: 要封禁的 IP 地址
            reason: 封禁原因
            ban_type: 封禁类型（auto_brute_force、auto_credential_stuffing 等）
            db: 数据库会话
            duration: 封禁时长（秒），None 使用配置默认值

        Returns:
            封禁记录 ID，如果未启用自动封禁则返回 None
        """
        if not security_settings.ip_auto_ban_enabled:
            logger.info(f"自动封禁已禁用，跳过封禁 IP: {ip}")
            return None

        # 避免循环导入
        from app.db.models.ip_ban import IPBanRecord
        from app.db.models.audit import AuthEvent

        if duration is None:
            duration = security_settings.ip_auto_ban_duration

        now = datetime.now(timezone.utc)

        # 检查是否已有活跃的封禁记录
        existing = await db.execute(
            select(IPBanRecord).where(
                IPBanRecord.ip == ip,
                IPBanRecord.unbanned_at.is_(None),
                (IPBanRecord.expires_at.is_(None)) | (IPBanRecord.expires_at > now),
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.info(f"IP {ip} 已被封禁，跳过重复封禁")
            return None

        # 创建封禁记录
        ban_record = IPBanRecord(
            ip=ip,
            reason=reason,
            ban_type=ban_type,
            banned_at=now,
            expires_at=now + timedelta(seconds=duration),
            created_by=None,  # None 表示系统自动封禁
        )
        db.add(ban_record)

        # 记录安全事件到审计日志
        event = AuthEvent(
            event_type="ip_auto_banned",
            principal_type="system",
            ip=ip,
            result="success",
            details={
                "reason": reason,
                "ban_type": ban_type,
                "duration_seconds": duration,
                "expires_at": (now + timedelta(seconds=duration)).isoformat(),
                "ban_record_id": ban_record.id,
            },
        )
        db.add(event)

        logger.warning(
            f"自动封禁 IP: {ip}, "
            f"原因={reason}, "
            f"类型={ban_type}, "
            f"时长={duration}秒"
        )

        return ban_record.id

    async def check_and_respond(
        self,
        ip: str,
        db: AsyncSession,
    ) -> Optional[str]:
        """
        检测威胁并自动响应

        综合检测多种威胁类型，检测到威胁后自动执行响应措施。

        Args:
            ip: 客户端 IP 地址
            db: 数据库会话

        Returns:
            检测到的威胁类型，None 表示无威胁
        """
        if not security_settings.threat_detection_enabled:
            return None

        # 检测暴力破解攻击
        if await self.check_brute_force(ip, db):
            if security_settings.threat_auto_ban_on_detection:
                await self.auto_ban_ip(
                    ip=ip,
                    reason="暴力破解攻击检测：短时间内大量登录失败",
                    ban_type="auto_brute_force",
                    db=db,
                )
            return "brute_force"

        # 检测凭据填充攻击
        if await self.check_credential_stuffing(ip, db):
            if security_settings.threat_auto_ban_on_detection:
                await self.auto_ban_ip(
                    ip=ip,
                    reason="凭据填充攻击检测：尝试登录多个不同用户",
                    ban_type="auto_credential_stuffing",
                    db=db,
                )
            return "credential_stuffing"

        return None

    async def get_threat_stats(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> dict:
        """
        获取威胁统计信息

        Args:
            db: 数据库会话
            hours: 统计时间范围（小时）

        Returns:
            包含威胁统计信息的字典
        """
        from app.db.models.audit import AuthEvent
        from app.db.models.ip_ban import IPBanRecord

        window_start = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 统计登录失败次数
        login_failures = await db.execute(
            select(func.count(AuthEvent.id)).where(
                AuthEvent.event_type == "login",
                AuthEvent.result == "failure",
                AuthEvent.ts >= window_start,
            )
        )

        # 统计自动封禁次数
        auto_bans = await db.execute(
            select(func.count(IPBanRecord.id)).where(
                IPBanRecord.ban_type.like("auto_%"),
                IPBanRecord.banned_at >= window_start,
            )
        )

        # 统计当前活跃的封禁数
        now = datetime.now(timezone.utc)
        active_bans = await db.execute(
            select(func.count(IPBanRecord.id)).where(
                IPBanRecord.unbanned_at.is_(None),
                (IPBanRecord.expires_at.is_(None)) | (IPBanRecord.expires_at > now),
            )
        )

        # 统计不同 IP 的登录失败
        unique_failed_ips = await db.execute(
            select(func.count(func.distinct(AuthEvent.ip))).where(
                AuthEvent.event_type == "login",
                AuthEvent.result == "failure",
                AuthEvent.ts >= window_start,
            )
        )

        return {
            "time_range_hours": hours,
            "login_failures": login_failures.scalar() or 0,
            "auto_bans": auto_bans.scalar() or 0,
            "active_bans": active_bans.scalar() or 0,
            "unique_failed_ips": unique_failed_ips.scalar() or 0,
        }


# 全局威胁检测器单例
threat_detector = ThreatDetector()
