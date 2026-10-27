"""
调度器静态任务目录与 APScheduler 投影。
"""

import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, TypedDict

import pytz
from apscheduler.executors.pool import BasePoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app.adapters.external.server import MoviePilotServerHelper
from app.adapters.system.update import system_update_manager
from app.application.configuration import (
    SchedulerRuntimeConfig,
)
from app.application.mediaserver import get_mediaserver_configs
from app.application.outbox import dispatch_pending_outbox
from app.application.plugin.runtime import get_plugin_manager
from app.application.scheduling import (  # noqa: E402
    JobCatalog,
    JobRecoveryPolicy,
    JobSpec,
)
from app.runtime.execution import IdleCacheReleasingThreadPoolExecutor
from app.runtime.scheduling import TimerUtils
from app.scheduler.contract import _SchedulerOwnerBase
from app.scheduler.services import SchedulerServices
from app.schemas.system import MediaServerConf as _SchemaMediaServerConf


class _MediaServerSchedule(TypedDict):
    """
    媒体服务器同步任务的内部投影。

    :ivar id: 媒体服务器配置标识
    :ivar name: 任务列表中显示的服务器名称
    :ivar server: 媒体服务器类型
    :ivar interval: 两次同步之间的分钟数
    """

    id: str
    name: str
    server: str
    interval: int


def _wallpaper_job_specs(
    services: SchedulerServices,
    wallpaper: str,
) -> tuple[JobSpec, ...]:
    """
    仅在启用壁纸时返回壁纸缓存任务声明。
    """
    if not wallpaper:
        return ()
    return (JobSpec("random_wallpager", "壁纸缓存", services.get_wallpapers, "image"),)


# APScheduler 未提供类型注解，基类在 mypy 中是 Any
# 自主 Agent 任务只需独立的有限触发容量；协程执行仍由原主循环和句柄 owner 托管。
_AGENT_SCHEDULER_WORKERS = 2


class _SchedulerThreadPoolExecutor(BasePoolExecutor):  # type: ignore[misc]
    """
    APScheduler 线程池执行器：定时任务线程按需增长、不收缩，空闲时交还各自的分配器线程缓存。
    """

    def __init__(self, max_workers: int) -> None:
        """
        以空闲时刷新线程缓存的线程池作为 APScheduler 的底层池。
        """
        super().__init__(IdleCacheReleasingThreadPoolExecutor(max_workers))


class SchedulerCatalogOwner(_SchedulerOwnerBase):
    """
    调度器静态任务目录与 APScheduler 投影。
    """

    @staticmethod
    def _get_mediaserver_sync_interval(
        mediaserver: _SchemaMediaServerConf,
        default_interval: Optional[int],
    ) -> Optional[int]:
        """
        获取媒体服务器的有效同步间隔，未设置时回退旧全局配置。
        """
        interval = mediaserver.sync_interval
        if interval is None:
            interval = default_interval
        if interval is None:
            return None
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return None
        return interval if interval > 0 else None

    @classmethod
    def _build_mediaserver_sync_schedules(
        cls,
        mediaservers: List[_SchemaMediaServerConf],
        default_interval: Optional[int],
    ) -> List[_MediaServerSchedule]:
        """
        构建已启用媒体服务器的独立自动同步任务描述。
        """
        schedules: List[_MediaServerSchedule] = []
        job_ids: set[str] = set()
        for mediaserver in mediaservers:
            if not mediaserver or not mediaserver.enabled or not mediaserver.name:
                continue
            interval = cls._get_mediaserver_sync_interval(
                mediaserver=mediaserver,
                default_interval=default_interval,
            )
            if not interval:
                continue
            digest = hashlib.sha256(mediaserver.name.encode("utf-8")).hexdigest()[:12]
            job_id = f"mediaserver_sync_{digest}"
            if job_id in job_ids:
                continue
            job_ids.add(job_id)
            schedules.append(
                {
                    "id": job_id,
                    "name": f"同步媒体服务器 - {mediaserver.name}",
                    "server": mediaserver.name,
                    "interval": interval,
                }
            )
        return schedules

    def _register_database_backup_job(
        self,
        config: SchedulerRuntimeConfig,
    ) -> None:
        """
        在共享调度器中按当前配置维护唯一的数据库备份作业。
        """
        if not config.db_backup_enable or not config.db_backup_cron.strip():
            return

        job_id = "database_backup"
        job = JobSpec(
            job_id,
            "数据库备份",
            self.database_backup,
            "database",
            recovery=JobRecoveryPolicy.DURABLE_QUEUE,
        ).to_runtime_state()
        self._assign_job_generation(job_id, job)
        self._jobs[job_id] = job
        self._scheduler.add_job(
            self.start,
            trigger=TimerUtils.build_schedule_trigger(
                trigger_type="cron",
                trigger_value=config.db_backup_cron,
                timezone_name=config.timezone,
            ),
            id=job_id,
            name="数据库备份",
            kwargs={"job_id": job_id},
            replace_existing=True,
        )

    def _initialize_catalog(self, config: SchedulerRuntimeConfig) -> None:
        """
        构建完整任务目录并投影到尚未启动的 APScheduler。
        """
        services = self._scheduler_services()
        # 各服务的运行状态
        # 精简版：站点（CookieCloud）与订阅相关的定时任务已全部移除。
        self._jobs = JobCatalog(
            [
                JobSpec("mediaserver_sync", "同步媒体服务器", services.sync_mediaserver, "mediaserver"),
                JobSpec(
                    "transfer",
                    "下载文件整理",
                    services.process_transfer,
                    "transfer",
                    recovery=JobRecoveryPolicy.DURABLE_QUEUE,
                ),
                JobSpec(
                    "clear_cache",
                    "缓存清理",
                    self.clear_cache,
                    "runtime",
                    manual=True,
                    recovery=JobRecoveryPolicy.MANUAL_ONLY,
                ),
                JobSpec("data_cleanup", "数据表清理", services.cleanup_data, "database"),
                JobSpec("scheduler_job", "公共定时服务", services.run_modules, "module"),
                *_wallpaper_job_specs(services, config.wallpaper),
                JobSpec("recommend_refresh", "推荐缓存", services.refresh_recommend, "recommend"),
                JobSpec(
                    "plugin_market_refresh",
                    "插件市场缓存",
                    get_plugin_manager().async_get_online_plugins,
                    "plugin",
                    kwargs={"force": True},
                ),
                JobSpec("full_gc", "主动内存回收", self.full_gc, "runtime"),
                JobSpec("agent_heartbeat", "智能体定时任务", self.agent_heartbeat, "agent"),
                JobSpec("usage_report", "安装版本统计上报", MoviePilotServerHelper.report_usage, "server"),
                *(
                    [JobSpec("system_update_check", "检查系统更新", system_update_manager.check_scheduled, "system")]
                    if config.update_check_enabled
                    else []
                ),
            ]
        ).runtime_states()
        for job_id, job in self._jobs.items():
            self._assign_job_generation(job_id, job)

        self._scheduler = BackgroundScheduler(
            timezone=config.timezone,
            executors={
                "default": _SchedulerThreadPoolExecutor(config.scheduler_workers),
                "agent": _SchedulerThreadPoolExecutor(_AGENT_SCHEDULER_WORKERS),
            },
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        )

        self._register_database_backup_job(config)
        outbox_job = JobSpec(
            "outbox_dispatch",
            "重试未完成的后台处理",
            dispatch_pending_outbox,
            "outbox",
            recovery=JobRecoveryPolicy.DURABLE_QUEUE,
        ).to_runtime_state()
        self._assign_job_generation("outbox_dispatch", outbox_job)
        self._jobs["outbox_dispatch"] = outbox_job
        self._scheduler.add_job(
            self.start,
            "interval",
            id="outbox_dispatch",
            name="重试未完成的后台处理",
            seconds=30,
            next_run_time=datetime.now(pytz.timezone(config.timezone)),
            kwargs={"job_id": "outbox_dispatch"},
            replace_existing=True,
        )
        # 精简版：CookieCloud 站点同步任务已移除。

        # 按媒体服务器分别注册自动同步任务
        mediaserver_schedules = self._build_mediaserver_sync_schedules(
            mediaservers=get_mediaserver_configs(include_disabled=True),
            default_interval=config.mediaserver_sync_interval,
        )
        for mediaserver_schedule in mediaserver_schedules:
            job_id = mediaserver_schedule["id"]
            job = JobSpec(
                job_id,
                mediaserver_schedule["name"],
                services.sync_mediaserver,
                "mediaserver",
                kwargs={"server": mediaserver_schedule["server"]},
            ).to_runtime_state()
            self._assign_job_generation(job_id, job)
            self._jobs[job_id] = job
            self._scheduler.add_job(
                self.start,
                "interval",
                id=job_id,
                name=mediaserver_schedule["name"],
                hours=mediaserver_schedule["interval"],
                next_run_time=datetime.now(pytz.timezone(config.timezone)) + timedelta(minutes=10),
                kwargs={"job_id": job_id},
            )

        # 精简版：订阅搜索、订阅元数据更新、订阅刷新、订阅分享等任务已移除。

        # 下载器文件转移（每5分钟）
        self._scheduler.add_job(
            self.start,
            "interval",
            id="transfer",
            name="下载文件整理",
            minutes=5,
            kwargs={"job_id": "transfer"},
        )

        # 仅在启用壁纸时后台刷新壁纸缓存。
        if config.wallpaper:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="random_wallpager",
                name="壁纸缓存",
                minutes=30,
                next_run_time=datetime.now(pytz.timezone(config.timezone)) + timedelta(seconds=1),
                kwargs={"job_id": "random_wallpager"},
            )

        # 公共定时服务
        self._scheduler.add_job(
            self.start,
            "interval",
            id="scheduler_job",
            name="公共定时服务",
            minutes=10,
            kwargs={"job_id": "scheduler_job"},
        )

        # 数据表清理服务，每天凌晨执行一次
        if config.data_cleanup_enable:
            self._scheduler.add_job(
                self.start,
                "cron",
                id="data_cleanup",
                name="数据表清理",
                hour=3,
                minute=30,
                kwargs={"job_id": "data_cleanup"},
            )

        # fnos-lite：站点认证与站点数据刷新已在剥离版中移除，不注册相关定时任务。

        # 推荐缓存
        self._scheduler.add_job(
            self.start,
            "interval",
            id="recommend_refresh",
            name="推荐缓存",
            hours=24,
            next_run_time=datetime.now(pytz.timezone(config.timezone)) + timedelta(seconds=5),
            kwargs={"job_id": "recommend_refresh"},
        )

        # 插件市场缓存
        self._scheduler.add_job(
            self.start,
            "interval",
            id="plugin_market_refresh",
            name="插件市场缓存",
            minutes=30,
            kwargs={"job_id": "plugin_market_refresh"},
        )

        if config.update_check_enabled:
            # 任一更新开关开启即注册，执行时分别检查已启用的主程序或资源。
            self._scheduler.add_job(
                self.start,
                "interval",
                id="system_update_check",
                name="检查系统更新",
                hours=6,
                next_run_time=datetime.now(pytz.timezone(config.timezone)) + timedelta(minutes=1),
                kwargs={"job_id": "system_update_check"},
            )

        # 精简版：订阅日历缓存任务已移除。

        # 主动内存回收
        if config.memory_gc_interval:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="full_gc",
                name="主动内存回收",
                minutes=config.memory_gc_interval,
                kwargs={"job_id": "full_gc"},
            )

        # 智能体定时任务检查
        if config.ai_agent_enable and config.ai_agent_job_interval:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="agent_heartbeat",
                executor="agent",
                name="智能体定时任务",
                hours=config.ai_agent_job_interval,
                kwargs={"job_id": "agent_heartbeat"},
            )

        # 安装版本统计上报
        if config.usage_statistic_share:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="usage_report",
                name="安装版本统计上报",
                hours=12,
                kwargs={"job_id": "usage_report"},
            )

        # 初始化工作流服务
        self.init_workflow_jobs()

        # 恢复 Agent 自主定时任务
        if config.ai_agent_enable:
            self.init_agent_task_jobs()

        # 初始化插件服务
        self.init_plugin_jobs()
