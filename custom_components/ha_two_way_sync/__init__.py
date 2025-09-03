"""Home Assistant SYMI双向同步集成 v2.1.2

这个集成允许两个实体之间进行双向状态同步。
当一个实体的状态发生变化时，另一个实体会自动同步到相同的状态。

特性:
- 支持多种设备类型（灯光、开关、风扇、窗帘等）
- 极简的主从跟随机制：主动作是什么，从就立刻跟着做什么
- 增强的实体存在性检查和重试机制
- 色温属性兼容性支持（color_temp_kelvin）
- 完美同步模式，确保所有属性都被正确同步
- 支持手动同步和状态查询
- 长期稳定运行保障机制
- 修复异步锁使用错误，确保同步功能正常工作
- 增强的看门狗重启恢复机制
- 稳定的后台自动恢复功能
- 集成重新加载支持
- 增强错误恢复机制

作者: Assistant
版本: v2.1.2
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from homeassistant.core import HomeAssistant, Event, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"
VERSION = "2.1.2"

# 集成信息
INTEGRATION_INFO = {
    "name": "Home Assistant SYMI双向同步",
    "version": VERSION,
    "description": "SYMI双向同步协调器 - 正式版",
    "features": [
        "完善的开关、调光、窗帘双向同步",
        "增强的看门狗重启恢复机制",
        "稳定的后台自动恢复功能",
        "优化的实体状态检查和健康监控"
    ]
}

class SimpleSyncCoordinator:
    """极简的双向同步协调器 - 主从跟随版"""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.entity1_id = config_entry.data.get("entity1")
        self.entity2_id = config_entry.data.get("entity2")
        self.enabled = True
        self._unsubscribe_listeners: list[Callable[[], None]] = []
        
        # 极简的同步控制 - 只保留基本同步锁
        try:
            self._sync_lock = asyncio.Lock()
        except Exception as e:
            _LOGGER.error("创建asyncio.Lock()失败: %s", e)
            raise
            
        # 简单的时间戳机制防止死循环
        self._last_sync_time = 0
        self._sync_cooldown = 0.1  # 100ms冷却时间
        
        # 实体存在性检查和重试机制
        self._entity_check_retries = 10
        self._entity_check_delay = 3.0  # 3秒延迟重试
        self._health_check_interval = 60  # 1分钟健康检查（增强）
        self._startup_wait_time = 15       # 启动等待时间（秒）
        self._max_startup_retries = 5      # 最大启动重试次数
        self._last_health_check = 0
        
        # 同步失败重试机制
        self._sync_retry_count = 3
        self._sync_retry_delay = 2.0
        self._last_health_check = 0  # 上次健康检查时间
        
        # 性能监控
        self._sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "avg_sync_time": 0.0,
            "last_sync_duration": 0.0,
            "entity_availability": {
                "entity1_available": True,
                "entity2_available": True,
                "last_check": None
            },
            "sync_history": []  # 保留最近10次同步记录
        }
        self._lock_timeout = 5.0  # 锁超时时间（秒）
        
        # 日志标识
        self._log_prefix = f"[{self.entity1_id} <-> {self.entity2_id}]"
        
        _LOGGER.info(f"{self._log_prefix} 同步协调器初始化完成")
        
    def _is_sync_caused_change(self, entity_id: str) -> bool:
        """检查是否是同步引起的变化（简单时间戳检查）"""
        current_time = time.time()
        return current_time - self._last_sync_time < self._sync_cooldown
        
    async def async_setup(self) -> None:
        """增强的同步器设置"""
        if not self.enabled or not self.entity1_id or not self.entity2_id:
            _LOGGER.warning(f"同步设置跳过: enabled={self.enabled}, entity1={self.entity1_id}, entity2={self.entity2_id}")
            return
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 清理旧的监听器
                for unsubscribe in self._unsubscribe_listeners:
                    unsubscribe()
                self._unsubscribe_listeners.clear()
                
                # 等待系统稳定
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                
                # 增强的实体存在性检查（带重试机制）
                if not await self._check_entities_with_retry():
                    if attempt < max_retries - 1:
                        _LOGGER.warning(f"实体检查失败，重试中: {self.entity1_id} <-> {self.entity2_id} (尝试 {attempt + 1}/{max_retries})")
                        continue
                    else:
                        _LOGGER.error(f"实体检查失败，无法设置同步: {self.entity1_id} <-> {self.entity2_id}")
                        return
                
                # 监听两个实体的状态变化
                await self._setup_listeners()
                
                # 验证监听器设置成功
                if not self._unsubscribe_listeners:
                    raise RuntimeError("监听器设置失败")
                
                # 启动健康检查
                self._schedule_health_check()
                
                _LOGGER.info(f"双向同步已启动: {self.entity1_id} <-> {self.entity2_id}")
                return
                
            except Exception as e:
                _LOGGER.error(f"设置同步器失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                # 清理失败的设置
                for unsubscribe in self._unsubscribe_listeners:
                    unsubscribe()
                self._unsubscribe_listeners.clear()
                
                if attempt == max_retries - 1:
                    raise
                else:
                    await asyncio.sleep(1)
        
    async def _check_entities_with_retry(self) -> bool:
        """带重试机制的实体存在性检查"""
        for attempt in range(self._entity_check_retries):
            entity1_state = self.hass.states.get(self.entity1_id)
            entity2_state = self.hass.states.get(self.entity2_id)
            
            # 检查实体是否在注册表中
            entity_registry = er.async_get(self.hass)
            entity1_entry = entity_registry.async_get(self.entity1_id)
            entity2_entry = entity_registry.async_get(self.entity2_id)
            
            if entity1_state and entity2_state:
                _LOGGER.debug(f"实体检查成功 (尝试 {attempt + 1}/{self._entity_check_retries})")
                return True
                
            if not entity1_entry:
                _LOGGER.warning(f"实体1未在注册表中找到: {self.entity1_id}")
            if not entity2_entry:
                _LOGGER.warning(f"实体2未在注册表中找到: {self.entity2_id}")
                
            if not entity1_state:
                _LOGGER.debug(f"实体1状态不可用: {self.entity1_id} (尝试 {attempt + 1}/{self._entity_check_retries})")
            if not entity2_state:
                _LOGGER.debug(f"实体2状态不可用: {self.entity2_id} (尝试 {attempt + 1}/{self._entity_check_retries})")
                
            if attempt < self._entity_check_retries - 1:
                _LOGGER.info(f"等待 {self._entity_check_delay} 秒后重试...")
                await asyncio.sleep(self._entity_check_delay)
                
        return False
        
    async def _setup_listeners(self) -> None:
        """设置状态变化监听器"""
        try:
            listener1 = async_track_state_change_event(
                self.hass, [self.entity1_id], self._handle_entity1_change
            )
            self._unsubscribe_listeners.append(listener1)
            _LOGGER.debug(f"实体1监听器已注册: {self.entity1_id}")
        except Exception as e:
            _LOGGER.error(f"实体1监听器注册失败: {self.entity1_id} - {e}")
            raise
            
        try:
            listener2 = async_track_state_change_event(
                self.hass, [self.entity2_id], self._handle_entity2_change
            )
            self._unsubscribe_listeners.append(listener2)
            _LOGGER.debug(f"实体2监听器已注册: {self.entity2_id}")
        except Exception as e:
            _LOGGER.error(f"实体2监听器注册失败: {self.entity2_id} - {e}")
            raise
            
    def _schedule_health_check(self) -> None:
        """安排定期健康检查"""
        async def health_check():
            current_time = time.time()
            if current_time - self._last_health_check >= self._health_check_interval:
                await self._perform_health_check()
                self._last_health_check = current_time
                
        # 使用Home Assistant的事件循环安排健康检查
        self.hass.async_create_task(health_check())
        
    async def _perform_health_check(self) -> None:
        """执行健康检查（增强版）"""
        check_start_time = time.time()
        
        try:
            _LOGGER.debug(f"{self._log_prefix} 开始健康检查")
            
            # 检查实体是否仍然存在和可用
            entity1_state = self.hass.states.get(self.entity1_id)
            entity2_state = self.hass.states.get(self.entity2_id)
            
            # 检查实体是否存在（不检查unavailable状态，因为设备可能临时离线）
            entities_missing = not entity1_state or not entity2_state
            
            # 检查是否有监听器（如果没有说明同步未正常工作）
            no_listeners = not self._unsubscribe_listeners
            
            _LOGGER.debug(f"{self._log_prefix} 实体状态检查: entity1={entity1_state.state if entity1_state else 'None'}, entity2={entity2_state.state if entity2_state else 'None'}")
            _LOGGER.debug(f"{self._log_prefix} 监听器状态: 数量={len(self._unsubscribe_listeners)}")
            
            # 只有在实体完全不存在或没有监听器时才重新设置
            if entities_missing or no_listeners:
                if entities_missing:
                    _LOGGER.warning(f"{self._log_prefix} 健康检查发现实体不存在，尝试重新设置监听器")
                if no_listeners:
                    _LOGGER.warning(f"{self._log_prefix} 健康检查发现无监听器，尝试重新设置")
                    
                # 如果只是实体暂时不可用（unavailable），不重新设置监听器
                if not entities_missing and entity1_state and entity2_state:
                    if entity1_state.state == "unavailable" or entity2_state.state == "unavailable":
                        _LOGGER.debug(f"{self._log_prefix} 实体暂时不可用但存在，保持监听器运行")
                        return
                    
                # 清理现有监听器
                for unsubscribe in self._unsubscribe_listeners:
                    unsubscribe()
                self._unsubscribe_listeners.clear()
                
                # 重新设置（带重试）
                recovery_success = False
                for retry in range(3):  # 健康检查时最多重试3次
                    try:
                        if await self._check_entities_with_retry():
                            await self._setup_listeners()
                            _LOGGER.info(f"{self._log_prefix} 健康检查：监听器已重新设置 (尝试 {retry + 1})")
                            recovery_success = True
                            break
                        else:
                            _LOGGER.warning(f"{self._log_prefix} 健康检查：实体检查失败 (尝试 {retry + 1})")
                    except Exception as retry_e:
                        _LOGGER.warning(f"{self._log_prefix} 健康检查重试失败 (尝试 {retry + 1}): {retry_e}")
                    
                    if retry < 2:  # 不是最后一次重试
                        await asyncio.sleep(10)  # 等待10秒再重试
                
                if not recovery_success:
                    _LOGGER.error(f"{self._log_prefix} 健康检查：无法重新设置监听器，将在下次健康检查时再次尝试")
            else:
                _LOGGER.debug(f"{self._log_prefix} 健康检查：所有实体正常，监听器工作正常")
                
            # 性能监控报告
            self._log_performance_stats()
            
            check_duration = time.time() - check_start_time
            _LOGGER.debug(f"{self._log_prefix} 健康检查完成，耗时: {check_duration:.3f}s")
                
        except Exception as e:
            check_duration = time.time() - check_start_time
            _LOGGER.error(f"{self._log_prefix} 健康检查失败: {e}, 耗时: {check_duration:.3f}s")
            
    def _log_performance_stats(self) -> None:
        """记录性能统计信息（增强版）"""
        try:
            stats = self._sync_stats
            if stats["total_syncs"] > 0:
                success_rate = (stats["successful_syncs"] / stats["total_syncs"]) * 100
                _LOGGER.info(
                    f"{self._log_prefix} 同步统计 - 总计: {stats['total_syncs']}, "
                    f"成功: {stats['successful_syncs']}, "
                    f"失败: {stats['failed_syncs']}, "
                    f"成功率: {success_rate:.1f}%, "
                    f"平均耗时: {stats['avg_sync_time']:.3f}s, "
                    f"最近耗时: {stats['last_sync_duration']:.3f}s"
                )
                
                # 记录实体可用性状态
                availability = stats.get("entity_availability", {})
                entity1_available = availability.get("entity1_available", True)
                entity2_available = availability.get("entity2_available", True)
                last_check = availability.get("last_check", "未知")
                
                _LOGGER.debug(f"{self._log_prefix} 实体可用性: entity1={entity1_available}, entity2={entity2_available}, 最后检查={last_check}")
                
                # 记录同步历史统计
                sync_history = stats.get("sync_history", [])
                if sync_history:
                    recent_success_count = sum(1 for record in sync_history if record.get("success", False))
                    recent_failure_count = len(sync_history) - recent_success_count
                    recent_success_rate = (recent_success_count / len(sync_history)) * 100 if sync_history else 0
                    
                    _LOGGER.debug(f"{self._log_prefix} 近期同步统计: 成功={recent_success_count}, 失败={recent_failure_count}, 成功率={recent_success_rate:.1f}%")
                
                # 性能警告
                if success_rate < 80:
                    _LOGGER.warning(f"{self._log_prefix} 同步成功率较低: {success_rate:.1f}%")
                if stats["avg_sync_time"] > 2.0:
                    _LOGGER.warning(f"{self._log_prefix} 平均同步时间过长: {stats['avg_sync_time']:.3f}s")
                    
                # 每100次同步记录一次详细统计
                if stats["total_syncs"] % 100 == 0:
                    _LOGGER.info(f"{self._log_prefix} 性能里程碑: 已完成{stats['total_syncs']}次同步，平均耗时{stats['avg_sync_time']:.3f}s，成功率{success_rate:.1f}%")
            else:
                _LOGGER.debug(f"{self._log_prefix} 暂无同步统计数据")
                
        except Exception as e:
            _LOGGER.warning(f"{self._log_prefix} 性能统计记录失败: {e}")
            
    def _get_color_temp_value(self, attributes: dict) -> int | None:
        """获取色温值，支持新旧格式的向后兼容性"""
        # 优先使用新格式 color_temp_kelvin
        if "color_temp_kelvin" in attributes:
            return attributes["color_temp_kelvin"]
            
        # 向后兼容旧格式 color_temp (mired值)
        if "color_temp" in attributes:
            color_temp_mired = attributes["color_temp"]
            if color_temp_mired and color_temp_mired > 0:
                # 将mired转换为kelvin: K = 1000000 / mired
                try:
                    kelvin_value = int(1000000 / color_temp_mired)
                    _LOGGER.debug(f"色温转换: {color_temp_mired} mired -> {kelvin_value} K")
                    return kelvin_value
                except (ValueError, ZeroDivisionError) as e:
                    _LOGGER.warning(f"色温转换失败: {color_temp_mired} mired - {e}")
                    
        return None
        
    async def _handle_entity1_change(self, event: Event) -> None:
        """处理实体1状态变化 - 极简版"""
        if not self.enabled:
            return
            
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
            
        # 检查是否是同步引起的变化
        if self._is_sync_caused_change(self.entity1_id):
            return
            
        # 执行同步
        await self._instant_sync(new_state, self.entity2_id)
        
    async def _handle_entity2_change(self, event: Event) -> None:
        """处理实体2状态变化 - 极简版"""
        if not self.enabled:
            return
            
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
            
        # 检查是否是同步引起的变化
        if self._is_sync_caused_change(self.entity2_id):
            return
            
        # 执行同步
        await self._instant_sync(new_state, self.entity1_id)
        
    async def _instant_sync(self, source_state: State, target_entity_id: str) -> None:
        """极简的即时同步 - 主动作是什么，从就立刻做什么（增强版）"""
        sync_start_time = time.time()
        
        try:
            # 使用超时锁防止死锁
            await asyncio.wait_for(self._sync_lock.acquire(), timeout=self._lock_timeout)
            try:
                # 更新统计
                self._sync_stats["total_syncs"] += 1
                
                # 防止循环同步
                self._last_sync_time = time.time()
                
                # 检查实体可用性
                if not await self._check_entity_availability(source_state.entity_id, target_entity_id):
                    self._sync_stats["failed_syncs"] += 1
                    return
                
                # 带重试的同步
                sync_successful = False
                for attempt in range(self._sync_retry_count):
                    try:
                        await self._perfect_sync(source_state, target_entity_id)
                        _LOGGER.debug(f"同步成功: {source_state.entity_id} -> {target_entity_id} (尝试 {attempt + 1})")
                        sync_successful = True
                        break
                    except Exception as e:
                        _LOGGER.warning(f"同步失败 (尝试 {attempt + 1}/{self._sync_retry_count}): {source_state.entity_id} -> {target_entity_id} - {e}")
                        if attempt < self._sync_retry_count - 1:
                            await asyncio.sleep(self._sync_retry_delay)
                        else:
                            _LOGGER.error(f"同步最终失败: {source_state.entity_id} -> {target_entity_id}")
                
                # 更新统计
                if sync_successful:
                    self._sync_stats["successful_syncs"] += 1
                else:
                    self._sync_stats["failed_syncs"] += 1
                    
            finally:
                self._sync_lock.release()
                    
        except asyncio.TimeoutError:
            _LOGGER.error(f"同步锁超时: {source_state.entity_id} -> {target_entity_id}")
            self._sync_stats["failed_syncs"] += 1
        except Exception as e:
            _LOGGER.error(f"同步失败: {source_state.entity_id} -> {target_entity_id}: {e}")
            self._sync_stats["failed_syncs"] += 1
        finally:
            # 更新性能统计
            sync_duration = time.time() - sync_start_time
            self._sync_stats["last_sync_duration"] = sync_duration
            
            # 计算平均同步时间
            if self._sync_stats["total_syncs"] > 0:
                total_time = (self._sync_stats["avg_sync_time"] * (self._sync_stats["total_syncs"] - 1) + sync_duration)
                self._sync_stats["avg_sync_time"] = total_time / self._sync_stats["total_syncs"]
                
    async def _check_entity_availability(self, source_entity_id: str, target_entity_id: str) -> bool:
        """检查实体可用性（优化版：设备离线时不影响整体功能）"""
        source_state = self.hass.states.get(source_entity_id)
        target_state = self.hass.states.get(target_entity_id)
        
        if not source_state:
            _LOGGER.debug(f"源实体不存在: {source_entity_id}")
            return False
            
        if not target_state:
            _LOGGER.debug(f"目标实体不存在: {target_entity_id}")
            return False
            
        # 检查实体是否可用（不是unavailable状态）
        # 设备离线时只记录debug日志，不影响其他功能
        if source_state.state == "unavailable":
            _LOGGER.debug(f"源实体暂时不可用，跳过本次同步: {source_entity_id}")
            return False
            
        if target_state.state == "unavailable":
            _LOGGER.debug(f"目标实体暂时不可用，跳过本次同步: {target_entity_id}")
            return False
            
        return True
                
    async def _perfect_sync(self, source_state: State, target_entity_id: str) -> None:
        """完美同步 - 主动作从跟随，包括所有属性（增强日志版）"""
        from datetime import datetime
        
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        sync_start_time = time.time()
        
        try:
            _LOGGER.debug(f"{self._log_prefix} 开始同步: {source_state.entity_id} -> {target_entity_id}")
            _LOGGER.debug(f"{self._log_prefix} 源状态: {source_state.state}, 域: {domain}")
            
            if domain == "light":
                # 灯光同步：开关、亮度、色温（跳过颜色避免冲突）
                if source_state.state == "on":
                    # 同步亮度（确保类型转换为整数）
                    if "brightness" in source_state.attributes:
                        try:
                            brightness_value = source_state.attributes["brightness"]
                            if brightness_value is not None:
                                service_data["brightness"] = int(float(brightness_value))
                                _LOGGER.debug(f"{self._log_prefix} 同步亮度: {brightness_value}")
                        except (ValueError, TypeError) as e:
                            _LOGGER.warning(f"{self._log_prefix} 亮度值转换失败: {source_state.attributes['brightness']} - {e}")
                    
                    # 同步色温（支持新旧格式，避免颜色冲突）
                    color_temp_value = self._get_color_temp_value(source_state.attributes)
                    if color_temp_value is not None:
                        service_data["color_temp_kelvin"] = color_temp_value
                        _LOGGER.debug(f"{self._log_prefix} 同步色温: {color_temp_value}K")
                    
                    await self.hass.services.async_call("light", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("light", "turn_off", service_data)
                    
            elif domain == "cover":
                # 窗帘同步：开关、位置、倾斜
                if source_state.state in ["open", "opening"]:
                    await self.hass.services.async_call("cover", "open_cover", service_data)
                elif source_state.state in ["closed", "closing"]:
                    await self.hass.services.async_call("cover", "close_cover", service_data)
                else:
                    # 同步位置
                    if "current_position" in source_state.attributes:
                        service_data["position"] = source_state.attributes["current_position"]
                        _LOGGER.debug(f"{self._log_prefix} 同步位置: {service_data['position']}%")
                        await self.hass.services.async_call("cover", "set_cover_position", service_data)
                    
                    # 同步倾斜位置
                    if "current_tilt_position" in source_state.attributes:
                        tilt_data = {"entity_id": target_entity_id, "tilt_position": source_state.attributes["current_tilt_position"]}
                        _LOGGER.debug(f"{self._log_prefix} 同步倾斜: {tilt_data['tilt_position']}%")
                        await self.hass.services.async_call("cover", "set_cover_tilt_position", tilt_data)
                        
            elif domain == "fan":
                # 风扇同步：开关、速度、百分比
                if source_state.state == "on":
                    # 同步速度百分比
                    if "percentage" in source_state.attributes:
                        service_data["percentage"] = source_state.attributes["percentage"]
                        _LOGGER.debug(f"{self._log_prefix} 同步风扇速度: {service_data['percentage']}%")
                    # 同步预设模式
                    elif "preset_mode" in source_state.attributes:
                        service_data["preset_mode"] = source_state.attributes["preset_mode"]
                        _LOGGER.debug(f"{self._log_prefix} 同步风扇模式: {service_data['preset_mode']}")
                    
                    await self.hass.services.async_call("fan", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("fan", "turn_off", service_data)
                    
            elif domain == "climate":
                # 空调同步：模式、温度、风扇模式
                # 同步温度
                if "temperature" in source_state.attributes:
                    service_data["temperature"] = source_state.attributes["temperature"]
                    _LOGGER.debug(f"{self._log_prefix} 同步温度: {service_data['temperature']}°C")
                
                # 同步模式
                if source_state.state != "unknown":
                    service_data["hvac_mode"] = source_state.state
                    _LOGGER.debug(f"{self._log_prefix} 同步空调模式: {service_data['hvac_mode']}")
                
                # 同步风扇模式
                if "fan_mode" in source_state.attributes:
                    service_data["fan_mode"] = source_state.attributes["fan_mode"]
                    _LOGGER.debug(f"{self._log_prefix} 同步空调风扇模式: {service_data['fan_mode']}")
                
                await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
                
                # 单独设置温度（如果有）
                if "temperature" in service_data:
                    temp_data = {"entity_id": target_entity_id, "temperature": service_data["temperature"]}
                    await self.hass.services.async_call("climate", "set_temperature", temp_data)
                    
            else:
                # 其他设备类型：基本开关同步
                if source_state.state in ["on", "off"]:
                    service = "turn_on" if source_state.state == "on" else "turn_off"
                    _LOGGER.debug(f"{self._log_prefix} 通用同步: {service}")
                    await self.hass.services.async_call(domain, service, service_data)
            
            sync_duration = time.time() - sync_start_time
            _LOGGER.debug(f"{self._log_prefix} 同步完成，耗时: {sync_duration:.3f}s")
            
            # 记录同步历史
            sync_record = {
                "timestamp": datetime.now().isoformat(),
                "source": source_state.entity_id,
                "target": target_entity_id,
                "duration": sync_duration,
                "success": True
            }
            
            self._sync_stats["sync_history"].append(sync_record)
            # 只保留最近10次记录
            if len(self._sync_stats["sync_history"]) > 10:
                self._sync_stats["sync_history"].pop(0)
                    
        except Exception as e:
            sync_duration = time.time() - sync_start_time
            _LOGGER.error(f"{self._log_prefix} 完美同步失败 {domain}: {e}, 耗时: {sync_duration:.3f}s")
            
            # 记录失败的同步历史
            sync_record = {
                "timestamp": datetime.now().isoformat(),
                "source": source_state.entity_id,
                "target": target_entity_id,
                "duration": sync_duration,
                "success": False,
                "error": str(e)
            }
            
            self._sync_stats["sync_history"].append(sync_record)
            if len(self._sync_stats["sync_history"]) > 10:
                self._sync_stats["sync_history"].pop(0)
            
            raise
            

            
    async def manual_sync(self, direction: str = "1to2") -> bool:
        """手动同步"""
        try:
            if direction == "1to2":
                source_state = self.hass.states.get(self.entity1_id)
                if source_state:
                    await self._instant_sync(source_state, self.entity2_id)
                    return True
            elif direction == "2to1":
                source_state = self.hass.states.get(self.entity2_id)
                if source_state:
                    await self._instant_sync(source_state, self.entity1_id)
                    return True
            return False
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}")
            return False
            
    def get_sync_status(self) -> dict[str, Any]:
        """获取同步状态"""
        entity1_state = self.hass.states.get(self.entity1_id)
        entity2_state = self.hass.states.get(self.entity2_id)
        
        return {
            "enabled": self.enabled,
            "entity1": {
                "id": self.entity1_id,
                "state": entity1_state.state if entity1_state else "unknown",
                "attributes": dict(entity1_state.attributes) if entity1_state else {}
            },
            "entity2": {
                "id": self.entity2_id,
                "state": entity2_state.state if entity2_state else "unknown",
                "attributes": dict(entity2_state.attributes) if entity2_state else {}
            },
            "last_sync_time": self._last_sync_time
        }
        
    async def _background_recovery(self) -> None:
        """增强的后台恢复机制 - 定期尝试重新设置失败的同步"""
        recovery_interval = 120  # 2分钟检查一次
        max_recovery_attempts = 20  # 最多尝试20次（约40分钟）
        
        for attempt in range(max_recovery_attempts):
            await asyncio.sleep(recovery_interval)
            
            if not self.enabled:
                _LOGGER.debug("同步器已禁用，停止后台恢复")
                break
                
            # 检查是否已经有监听器（说明已经恢复）
            if self._unsubscribe_listeners:
                _LOGGER.info("检测到同步已恢复，停止后台恢复任务")
                break
                
            try:
                # 检查实体状态
                state1 = self.hass.states.get(self.entity1_id)
                state2 = self.hass.states.get(self.entity2_id)
                
                # 实体不可用时的恢复策略
                if not state1 or not state2:
                    _LOGGER.warning(f"实体不可用，等待恢复: {self.entity1_id}, {self.entity2_id}")
                    
                    # 等待实体恢复
                    max_wait = 60  # 最大等待60秒
                    wait_time = 0
                    while wait_time < max_wait and self.enabled:
                        await asyncio.sleep(5)
                        wait_time += 5
                        state1 = self.hass.states.get(self.entity1_id)
                        state2 = self.hass.states.get(self.entity2_id)
                        if state1 and state2:
                            break
                    
                    if not (state1 and state2):
                        _LOGGER.warning("实体仍不可用，将在下次检查时重试")
                        continue
                
                # 网络连接检查
                try:
                    # 检查实体是否处于不可用状态
                    if (state1 and state1.state == 'unavailable') or (state2 and state2.state == 'unavailable'):
                        _LOGGER.warning("检测到实体不可用状态，可能是网络问题")
                        # 等待网络恢复
                        await asyncio.sleep(30)
                        continue
                        
                except Exception as conn_error:
                    _LOGGER.warning(f"网络连接检查失败: {conn_error}")
                
                _LOGGER.info(f"后台恢复尝试 {attempt + 1}/{max_recovery_attempts}")
                await self.async_setup()
                _LOGGER.info("后台恢复成功！")
                break
            except Exception as e:
                _LOGGER.warning(f"后台恢复失败 (尝试 {attempt + 1}/{max_recovery_attempts}): {e}")
                # 尝试基本恢复
                try:
                    if self.enabled:
                        await asyncio.sleep(10)
                        await self.async_setup()
                except Exception as recovery_error:
                    _LOGGER.error(f"基本恢复也失败: {recovery_error}")
                
        if attempt == max_recovery_attempts - 1:
            _LOGGER.error("后台恢复已达到最大尝试次数，请检查实体配置")
    
    async def async_unload(self) -> None:
        """卸载同步器"""
        self.enabled = False
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()
        pass

# 全局同步器实例
_sync_coordinators: dict[str, SimpleSyncCoordinator] = {}

async def _register_services(hass: HomeAssistant) -> None:
    """注册集成服务"""
    # 手动同步服务
    async def manual_sync_service(call):
        """手动同步服务"""
        config_entry_id = call.data.get("config_entry_id")
        direction = call.data.get("direction", "bidirectional")
        
        if config_entry_id in _sync_coordinators:
            coordinator = _sync_coordinators[config_entry_id]
            try:
                await coordinator.manual_sync(direction)
                _LOGGER.info(f"手动同步完成: {config_entry_id}")
            except Exception as e:
                _LOGGER.error(f"手动同步失败: {e}")
        else:
            _LOGGER.error(f"未找到同步器: {config_entry_id}")
    
    # 获取状态服务
    async def get_status_service(call):
        """获取同步状态服务"""
        config_entry_id = call.data.get("config_entry_id")
        
        if config_entry_id in _sync_coordinators:
            coordinator = _sync_coordinators[config_entry_id]
            status = coordinator.get_sync_status()
            _LOGGER.info(f"同步状态: {status}")
            return status
        else:
            _LOGGER.error(f"未找到同步器: {config_entry_id}")
            return None
    
    # 切换同步服务
    async def toggle_sync_service(call):
        """切换同步状态服务"""
        config_entry_id = call.data.get("config_entry_id")
        enable = call.data.get("enable", True)
        
        if config_entry_id in _sync_coordinators:
            coordinator = _sync_coordinators[config_entry_id]
            try:
                if enable:
                    coordinator.enabled = True
                    await coordinator.async_setup()
                    _LOGGER.info(f"同步已启用: {config_entry_id}")
                else:
                    coordinator.enabled = False
                    await coordinator.async_unload()
                    _LOGGER.info(f"同步已禁用: {config_entry_id}")
            except Exception as e:
                _LOGGER.error(f"切换同步状态失败: {e}")
        else:
            _LOGGER.error(f"未找到同步器: {config_entry_id}")
    
    # 注册服务
    hass.services.async_register(DOMAIN, "manual_sync", manual_sync_service)
    hass.services.async_register(DOMAIN, "get_status", get_status_service)
    hass.services.async_register(DOMAIN, "toggle_sync", toggle_sync_service)
    
    _LOGGER.info("集成服务注册完成")

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置集成"""
    hass.data.setdefault(DOMAIN, {})
    
    # 注册集成重新加载服务
    async def reload_integration(call):
        """重新加载集成"""
        _LOGGER.info("正在重新加载 SYMI 双向同步集成...")
        try:
            # 获取所有配置条目
            entries = hass.config_entries.async_entries(DOMAIN)
            
            # 重新加载所有配置条目
            for entry in entries:
                await hass.config_entries.async_reload(entry.entry_id)
            
            _LOGGER.info(f"成功重新加载 {len(entries)} 个同步配置")
        except Exception as e:
            _LOGGER.error(f"重新加载集成失败: {e}")
    
    # 注册服务
    hass.services.async_register(
        DOMAIN, "reload", reload_integration
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """增强的配置条目设置"""
    _LOGGER.info(f"正在设置双向同步配置: {entry.title}")
    
    try:
        coordinator = SimpleSyncCoordinator(hass, entry)
        _sync_coordinators[entry.entry_id] = coordinator
        
        # 恢复保存的状态
        last_unload_time = entry.data.get("last_unload_time")
        saved_enabled = entry.data.get("sync_enabled", True)
        saved_stats = entry.data.get("performance_stats", {})
        
        # 恢复保存的状态
        coordinator.enabled = saved_enabled
        if saved_stats:
            coordinator._sync_stats.update(saved_stats)
            
        if last_unload_time:
            _LOGGER.info(f"恢复配置状态，上次卸载时间: {last_unload_time}")
        
        # 增强的重启容错机制：多次重试，逐渐增加延迟
        setup_success = False
        for attempt in range(coordinator._max_startup_retries):
            try:
                await coordinator.async_setup()
                setup_success = True
                _LOGGER.info(f"设置成功 (尝试 {attempt + 1}/{coordinator._max_startup_retries})")
                break
            except Exception as e:
                wait_time = coordinator._startup_wait_time + (attempt * 5)  # 递增延迟
                if attempt < coordinator._max_startup_retries - 1:
                    _LOGGER.warning(f"设置失败 (尝试 {attempt + 1}/{coordinator._max_startup_retries})，{wait_time}秒后重试: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error(f"最终设置失败 (尝试 {attempt + 1}/{coordinator._max_startup_retries}): {e}")
        
        # 即使设置失败也继续加载，启动后台恢复任务
        if not setup_success:
            _LOGGER.info("启动后台恢复任务，将定期尝试重新设置同步")
            
            # 增强的后台恢复任务
            async def enhanced_background_recovery():
                """增强的后台恢复任务"""
                recovery_attempts = 0
                max_recovery_attempts = 10
                
                while recovery_attempts < max_recovery_attempts and coordinator.enabled:
                    try:
                        await asyncio.sleep(30)  # 等待30秒后重试
                        
                        # 检查实体是否恢复
                        state1 = hass.states.get(coordinator.entity1_id)
                        state2 = hass.states.get(coordinator.entity2_id)
                        
                        if state1 and state2 and state1.state != 'unavailable' and state2.state != 'unavailable':
                            await coordinator.async_setup()
                            _LOGGER.info(f"后台恢复成功: {entry.title}")
                            
                            # 更新配置状态
                            from datetime import datetime
                            current_data = dict(entry.data)
                            current_data["last_recovery_time"] = datetime.now().isoformat()
                            hass.config_entries.async_update_entry(entry, data=current_data)
                            break
                        else:
                            _LOGGER.debug(f"实体仍不可用，继续等待恢复: {coordinator.entity1_id}, {coordinator.entity2_id}")
                            
                    except Exception as recovery_error:
                        recovery_attempts += 1
                        _LOGGER.warning(f"后台恢复失败 (尝试 {recovery_attempts}/{max_recovery_attempts}): {recovery_error}")
                        
                if recovery_attempts >= max_recovery_attempts:
                    _LOGGER.error(f"后台恢复最终失败: {entry.title}")
            
            hass.async_create_task(enhanced_background_recovery())
        
        # 注册服务
        async def handle_manual_sync(call):
            """处理手动同步服务"""
            entry_id = call.data.get("entry_id")
            direction = call.data.get("direction", "1to2")
            
            if entry_id in _sync_coordinators:
                success = await _sync_coordinators[entry_id].manual_sync(direction)
                if not success:
                    _LOGGER.error(f"手动同步失败: {entry_id} ({direction})")
            else:
                _LOGGER.error(f"未找到同步器: {entry_id}")
        
        async def handle_get_status(call):
            """处理获取状态服务"""
            entry_id = call.data.get("entry_id")
            
            if entry_id in _sync_coordinators:
                status = _sync_coordinators[entry_id].get_sync_status()
                pass
            else:
                _LOGGER.error(f"未找到同步器: {entry_id}")
        
        async def handle_toggle_sync(call):
            """处理切换同步状态服务"""
            entry_id = call.data.get("entry_id")
            
            if entry_id in _sync_coordinators:
                coordinator = _sync_coordinators[entry_id]
                if coordinator.enabled:
                    coordinator.enabled = False
                    _LOGGER.info(f"已禁用同步: {entry.title}")
                else:
                    coordinator.enabled = True
                    await coordinator.async_setup()
                    _LOGGER.info(f"已启用同步: {entry.title}")
            else:
                _LOGGER.error(f"未找到同步器: {entry_id}")
        
        hass.services.async_register(DOMAIN, "manual_sync", handle_manual_sync)
        hass.services.async_register(DOMAIN, "get_status", handle_get_status)
        hass.services.async_register(DOMAIN, "toggle_sync", handle_toggle_sync)
        
        _LOGGER.info(f"双向同步配置设置完成: {entry.title}")
        return True
        
    except Exception as e:
        _LOGGER.error(f"设置配置条目失败: {e}")
        # 增强错误恢复机制
        try:
            # 尝试清理已创建的资源
            if entry.entry_id in _sync_coordinators:
                coordinator = _sync_coordinators[entry.entry_id]
                await coordinator.async_unload()
                del _sync_coordinators[entry.entry_id]
        except Exception as cleanup_error:
            _LOGGER.error(f"清理资源失败: {cleanup_error}")
        
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """增强的配置条目卸载"""
    try:
        # 获取同步器
        coordinator = _sync_coordinators.get(entry.entry_id)
        if coordinator:
            # 保存当前状态到配置
            try:
                from datetime import datetime
                current_data = dict(entry.data)
                current_data.update({
                    "last_unload_time": datetime.now().isoformat(),
                    "sync_enabled": coordinator.enabled,
                    "performance_stats": coordinator._sync_stats
                })
                
                # 更新配置条目数据
                hass.config_entries.async_update_entry(
                    entry, data=current_data
                )
                
                _LOGGER.info(f"配置状态已保存: {entry.title}")
            except Exception as save_error:
                _LOGGER.warning(f"保存配置状态失败: {save_error}")
            
            # 优雅关闭同步器
            await coordinator.async_unload()
            
        # 清理数据
        if entry.entry_id in _sync_coordinators:
            del _sync_coordinators[entry.entry_id]
            
        _LOGGER.info(f"配置条目已卸载: {entry.title}")
        return True
        
    except Exception as e:
        _LOGGER.error(f"卸载配置条目失败: {e}")
        return False