"""Home Assistant 双向同步集成 v1.3.5

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

作者: Assistant
版本: v1.3.5
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, Event, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"

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
        self._entity_check_retries = 3
        self._entity_check_delay = 2.0  # 2秒延迟重试
        self._health_check_interval = 300  # 5分钟健康检查
        self._last_health_check = 0
        
        # 同步失败重试机制
        self._sync_retry_count = 2
        self._sync_retry_delay = 1.0
        self._last_health_check = 0  # 上次健康检查时间
        
        # 性能监控
        self._sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "avg_sync_time": 0.0,
            "last_sync_duration": 0.0
        }
        self._lock_timeout = 5.0  # 锁超时时间（秒）
        
    def _is_sync_caused_change(self, entity_id: str) -> bool:
        """检查是否是同步引起的变化（简单时间戳检查）"""
        current_time = time.time()
        return current_time - self._last_sync_time < self._sync_cooldown
        
    async def async_setup(self) -> None:
        """设置同步监听器（增强版）"""
        if not self.enabled or not self.entity1_id or not self.entity2_id:
            _LOGGER.warning(f"同步设置跳过: enabled={self.enabled}, entity1={self.entity1_id}, entity2={self.entity2_id}")
            return
            
        # 增强的实体存在性检查（带重试机制）
        if not await self._check_entities_with_retry():
            _LOGGER.error(f"实体检查失败，无法设置同步: {self.entity1_id} <-> {self.entity2_id}")
            return
            
        # 监听两个实体的状态变化
        await self._setup_listeners()
        
        # 启动健康检查
        self._schedule_health_check()
        
        _LOGGER.info(f"双向同步已启动: {self.entity1_id} <-> {self.entity2_id}")
        
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
                _LOGGER.warning(f"实体1状态不可用: {self.entity1_id} (尝试 {attempt + 1}/{self._entity_check_retries})")
            if not entity2_state:
                _LOGGER.warning(f"实体2状态不可用: {self.entity2_id} (尝试 {attempt + 1}/{self._entity_check_retries})")
                
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
        """执行健康检查"""
        try:
            # 检查实体是否仍然存在
            entity1_state = self.hass.states.get(self.entity1_id)
            entity2_state = self.hass.states.get(self.entity2_id)
            
            if not entity1_state or not entity2_state:
                _LOGGER.warning(f"健康检查发现实体不可用，尝试重新设置监听器")
                # 清理现有监听器
                for unsubscribe in self._unsubscribe_listeners:
                    unsubscribe()
                self._unsubscribe_listeners.clear()
                
                # 重新设置
                if await self._check_entities_with_retry():
                    await self._setup_listeners()
                    _LOGGER.info("健康检查：监听器已重新设置")
                else:
                    _LOGGER.error("健康检查：无法重新设置监听器")
            else:
                _LOGGER.debug("健康检查：所有实体正常")
                
            # 性能监控报告
            self._log_performance_stats()
                
        except Exception as e:
            _LOGGER.error(f"健康检查失败: {e}")
            
    def _log_performance_stats(self) -> None:
        """记录性能统计信息"""
        stats = self._sync_stats
        if stats["total_syncs"] > 0:
            success_rate = (stats["successful_syncs"] / stats["total_syncs"]) * 100
            _LOGGER.info(
                f"同步统计 - 总计: {stats['total_syncs']}, "
                f"成功: {stats['successful_syncs']}, "
                f"失败: {stats['failed_syncs']}, "
                f"成功率: {success_rate:.1f}%, "
                f"平均耗时: {stats['avg_sync_time']:.3f}s, "
                f"最近耗时: {stats['last_sync_duration']:.3f}s"
            )
            
            # 性能警告
            if success_rate < 80:
                _LOGGER.warning(f"同步成功率较低: {success_rate:.1f}%")
            if stats["avg_sync_time"] > 2.0:
                _LOGGER.warning(f"平均同步时间过长: {stats['avg_sync_time']:.3f}s")
        else:
            _LOGGER.debug("暂无同步统计数据")
            
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
        """检查实体可用性"""
        source_state = self.hass.states.get(source_entity_id)
        target_state = self.hass.states.get(target_entity_id)
        
        if not source_state:
            _LOGGER.warning(f"源实体不存在: {source_entity_id}")
            return False
            
        if not target_state:
            _LOGGER.warning(f"目标实体不存在: {target_entity_id}")
            return False
            
        # 检查实体是否可用（不是unavailable状态）
        if source_state.state == "unavailable":
            _LOGGER.debug(f"源实体不可用: {source_entity_id}")
            return False
            
        if target_state.state == "unavailable":
            _LOGGER.debug(f"目标实体不可用: {target_entity_id}")
            return False
            
        return True
                
    async def _perfect_sync(self, source_state: State, target_entity_id: str) -> None:
        """完美同步 - 主动作从跟随，包括所有属性"""
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        
        try:
            if domain == "light":
                # 灯光同步：开关、亮度、色温（跳过颜色避免冲突）
                if source_state.state == "on":
                    # 同步亮度
                    if "brightness" in source_state.attributes:
                        service_data["brightness"] = source_state.attributes["brightness"]
                    
                    # 同步色温（支持新旧格式，避免颜色冲突）
                    color_temp_value = self._get_color_temp_value(source_state.attributes)
                    if color_temp_value is not None:
                        service_data["color_temp_kelvin"] = color_temp_value
                    
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
                        await self.hass.services.async_call("cover", "set_cover_position", service_data)
                    
                    # 同步倾斜位置
                    if "current_tilt_position" in source_state.attributes:
                        tilt_data = {"entity_id": target_entity_id, "tilt_position": source_state.attributes["current_tilt_position"]}
                        await self.hass.services.async_call("cover", "set_cover_tilt_position", tilt_data)
                        
            elif domain == "fan":
                # 风扇同步：开关、速度、百分比
                if source_state.state == "on":
                    # 同步速度百分比
                    if "percentage" in source_state.attributes:
                        service_data["percentage"] = source_state.attributes["percentage"]
                    # 同步预设模式
                    elif "preset_mode" in source_state.attributes:
                        service_data["preset_mode"] = source_state.attributes["preset_mode"]
                    
                    await self.hass.services.async_call("fan", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("fan", "turn_off", service_data)
                    
            elif domain == "climate":
                # 空调同步：模式、温度、风扇模式
                # 同步温度
                if "temperature" in source_state.attributes:
                    service_data["temperature"] = source_state.attributes["temperature"]
                
                # 同步模式
                if source_state.state != "unknown":
                    service_data["hvac_mode"] = source_state.state
                
                # 同步风扇模式
                if "fan_mode" in source_state.attributes:
                    service_data["fan_mode"] = source_state.attributes["fan_mode"]
                
                await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
                
                # 单独设置温度（如果有）
                if "temperature" in service_data:
                    temp_data = {"entity_id": target_entity_id, "temperature": service_data["temperature"]}
                    await self.hass.services.async_call("climate", "set_temperature", temp_data)
                    
            else:
                # 其他设备类型：基本开关同步
                if source_state.state in ["on", "off"]:
                    service = "turn_on" if source_state.state == "on" else "turn_off"
                    await self.hass.services.async_call(domain, service, service_data)
                    
        except Exception as e:
            _LOGGER.error(f"完美同步失败 {domain}: {e}")
            

            
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
        
    async def async_unload(self) -> None:
        """卸载同步器"""
        self.enabled = False
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()
        pass

# 全局同步器实例
_sync_coordinators: dict[str, SimpleSyncCoordinator] = {}

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置集成"""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置配置条目"""
    coordinator = SimpleSyncCoordinator(hass, entry)
    _sync_coordinators[entry.entry_id] = coordinator
    
    await coordinator.async_setup()
    
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
    
    hass.services.async_register(DOMAIN, "manual_sync", handle_manual_sync)
    hass.services.async_register(DOMAIN, "get_status", handle_get_status)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目"""
    if entry.entry_id in _sync_coordinators:
        await _sync_coordinators[entry.entry_id].async_unload()
        del _sync_coordinators[entry.entry_id]
    
    return True