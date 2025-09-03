"""Home Assistant SYMI双向同步集成"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.service import async_register_admin_service

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"
VERSION = "2.1.3"

# 全局同步器字典
SYNC_COORDINATORS = {}

class TwoWaySyncCoordinator:
    """双向同步协调器"""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self.entity1 = config_entry.data["entity1"]
        self.entity2 = config_entry.data["entity2"]
        self.enabled = config_entry.options.get("enabled", config_entry.data.get("enabled", True))
        
        # 同步状态跟踪
        self._syncing = False
        self._last_sync_time = {}
        self._sync_cooldown = 1.0  # 同步冷却时间
        self._retry_count = {}
        self._max_retries = 3
        
        # 性能监控
        self._sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "last_sync_time": None,
            "average_sync_duration": 0.0
        }
        
        # 健康检查
        self._last_health_check = time.time()
        self._health_check_interval = 300  # 5分钟
        
        # 事件监听器
        self._listeners = []
        
        _LOGGER.info(f"初始化双向同步: {self.entity1} <-> {self.entity2}")
    
    async def async_setup(self):
        """设置同步器"""
        # 检查实体存在性
        if not await self._check_entities_exist():
            _LOGGER.error(f"实体不存在，无法设置同步: {self.entity1}, {self.entity2}")
            return False
        
        # 注册状态变化监听器
        self._listeners.append(
            async_track_state_change_event(
                self.hass, [self.entity1], self._handle_entity1_change
            )
        )
        self._listeners.append(
            async_track_state_change_event(
                self.hass, [self.entity2], self._handle_entity2_change
            )
        )
        
        _LOGGER.info(f"双向同步设置完成: {self.entity1} <-> {self.entity2}")
        return True
    
    async def _check_entities_exist(self) -> bool:
        """检查实体是否存在"""
        state1 = self.hass.states.get(self.entity1)
        state2 = self.hass.states.get(self.entity2)
        
        if not state1:
            _LOGGER.error(f"实体 {self.entity1} 不存在")
            return False
        if not state2:
            _LOGGER.error(f"实体 {self.entity2} 不存在")
            return False
        
        return True
    
    def _should_sync(self, entity_id: str) -> bool:
        """检查是否应该同步"""
        if not self.enabled:
            return False
        
        if self._syncing:
            return False
        
        # 检查冷却时间
        last_sync = self._last_sync_time.get(entity_id, 0)
        if time.time() - last_sync < self._sync_cooldown:
            return False
        
        return True
    
    async def _handle_entity1_change(self, event: Event):
        """处理实体1状态变化"""
        if not self._should_sync(self.entity1):
            return
        
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        if old_state and old_state.state == new_state.state:
            return
        
        await self._instant_sync(self.entity1, self.entity2, new_state)
    
    async def _handle_entity2_change(self, event: Event):
        """处理实体2状态变化"""
        if not self._should_sync(self.entity2):
            return
        
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        if old_state and old_state.state == new_state.state:
            return
        
        await self._instant_sync(self.entity2, self.entity1, new_state)
    
    async def _instant_sync(self, source_entity: str, target_entity: str, source_state):
        """即时同步"""
        if self._syncing:
            return
        
        self._syncing = True
        start_time = time.time()
        
        try:
            self._last_sync_time[source_entity] = time.time()
            
            # 检查目标实体可用性
            if not await self._check_entity_availability(target_entity):
                _LOGGER.warning(f"目标实体 {target_entity} 不可用，跳过同步")
                return
            
            # 执行完美同步
            success = await self._perfect_sync(source_entity, target_entity, source_state)
            
            # 更新统计信息
            self._sync_stats["total_syncs"] += 1
            if success:
                self._sync_stats["successful_syncs"] += 1
                self._retry_count[source_entity] = 0
            else:
                self._sync_stats["failed_syncs"] += 1
                self._retry_count[source_entity] = self._retry_count.get(source_entity, 0) + 1
            
            duration = time.time() - start_time
            self._sync_stats["average_sync_duration"] = (
                (self._sync_stats["average_sync_duration"] * (self._sync_stats["total_syncs"] - 1) + duration) /
                self._sync_stats["total_syncs"]
            )
            self._sync_stats["last_sync_time"] = datetime.now().isoformat()
            
        except Exception as e:
            _LOGGER.error(f"同步过程中发生错误: {e}")
            self._sync_stats["failed_syncs"] += 1
        finally:
            self._syncing = False
    
    async def _check_entity_availability(self, entity_id: str) -> bool:
        """检查实体可用性"""
        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    
    def _get_color_temp_value(self, attributes: Dict[str, Any]) -> Optional[int]:
        """获取色温值，支持新旧格式兼容"""
        # 新格式：color_temp_kelvin
        if "color_temp_kelvin" in attributes:
            return attributes["color_temp_kelvin"]
        
        # 旧格式：color_temp (mired值)
        if "color_temp" in attributes:
            mired = attributes["color_temp"]
            if mired and mired > 0:
                return int(1000000 / mired)  # 转换为开尔文
        
        return None
    
    async def _perfect_sync(self, source_entity: str, target_entity: str, source_state) -> bool:
        """完美同步 - 同步所有相关属性"""
        try:
            source_domain = source_entity.split(".")[0]
            target_domain = target_entity.split(".")[0]
            
            # 灯光设备同步
            if source_domain == "light" and target_domain == "light":
                if source_state.state == STATE_ON:
                    service_data = {ATTR_ENTITY_ID: target_entity}
                    
                    # 同步亮度
                    if "brightness" in source_state.attributes:
                        service_data["brightness"] = source_state.attributes["brightness"]
                    
                    # 同步色温
                    color_temp = self._get_color_temp_value(source_state.attributes)
                    if color_temp:
                        service_data["color_temp_kelvin"] = color_temp
                    
                    # 同步颜色
                    if "rgb_color" in source_state.attributes:
                        service_data["rgb_color"] = source_state.attributes["rgb_color"]
                    elif "hs_color" in source_state.attributes:
                        service_data["hs_color"] = source_state.attributes["hs_color"]
                    
                    # 同步效果
                    if "effect" in source_state.attributes:
                        service_data["effect"] = source_state.attributes["effect"]
                    
                    await self.hass.services.async_call("light", SERVICE_TURN_ON, service_data)
                else:
                    await self.hass.services.async_call(
                        "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: target_entity}
                    )
            
            # 窗帘设备同步
            elif source_domain == "cover" and target_domain == "cover":
                if source_state.state == "open":
                    await self.hass.services.async_call(
                        "cover", "open_cover", {ATTR_ENTITY_ID: target_entity}
                    )
                elif source_state.state == "closed":
                    await self.hass.services.async_call(
                        "cover", "close_cover", {ATTR_ENTITY_ID: target_entity}
                    )
                else:
                    # 同步位置
                    if "current_position" in source_state.attributes:
                        position = source_state.attributes["current_position"]
                        await self.hass.services.async_call(
                            "cover", "set_cover_position", 
                            {ATTR_ENTITY_ID: target_entity, "position": position}
                        )
                    
                    # 同步倾斜
                    if "current_tilt_position" in source_state.attributes:
                        tilt = source_state.attributes["current_tilt_position"]
                        await self.hass.services.async_call(
                            "cover", "set_cover_tilt_position", 
                            {ATTR_ENTITY_ID: target_entity, "tilt_position": tilt}
                        )
            
            # 风扇设备同步
            elif source_domain == "fan" and target_domain == "fan":
                if source_state.state == STATE_ON:
                    service_data = {ATTR_ENTITY_ID: target_entity}
                    
                    # 同步速度
                    if "speed" in source_state.attributes:
                        service_data["speed"] = source_state.attributes["speed"]
                    
                    # 同步百分比
                    if "percentage" in source_state.attributes:
                        service_data["percentage"] = source_state.attributes["percentage"]
                    
                    # 同步预设模式
                    if "preset_mode" in source_state.attributes:
                        service_data["preset_mode"] = source_state.attributes["preset_mode"]
                    
                    await self.hass.services.async_call("fan", SERVICE_TURN_ON, service_data)
                else:
                    await self.hass.services.async_call(
                        "fan", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: target_entity}
                    )
            
            # 空调设备同步
            elif source_domain == "climate" and target_domain == "climate":
                service_data = {ATTR_ENTITY_ID: target_entity}
                
                # 同步温度
                if "temperature" in source_state.attributes:
                    service_data["temperature"] = source_state.attributes["temperature"]
                
                # 同步HVAC模式
                if "hvac_mode" in source_state.attributes:
                    await self.hass.services.async_call(
                        "climate", "set_hvac_mode", 
                        {ATTR_ENTITY_ID: target_entity, "hvac_mode": source_state.attributes["hvac_mode"]}
                    )
                
                # 同步风扇模式
                if "fan_mode" in source_state.attributes:
                    await self.hass.services.async_call(
                        "climate", "set_fan_mode", 
                        {ATTR_ENTITY_ID: target_entity, "fan_mode": source_state.attributes["fan_mode"]}
                    )
                
                # 设置温度
                if "temperature" in service_data:
                    await self.hass.services.async_call(
                        "climate", "set_temperature", service_data
                    )
            
            # 其他设备类型的基本开关同步
            else:
                if source_state.state == STATE_ON:
                    domain = target_domain if target_domain in ["switch", "light", "fan"] else "homeassistant"
                    await self.hass.services.async_call(
                        domain, SERVICE_TURN_ON, {ATTR_ENTITY_ID: target_entity}
                    )
                elif source_state.state == STATE_OFF:
                    domain = target_domain if target_domain in ["switch", "light", "fan"] else "homeassistant"
                    await self.hass.services.async_call(
                        domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: target_entity}
                    )
            
            _LOGGER.debug(f"完美同步成功: {source_entity} -> {target_entity}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"完美同步失败 {source_entity} -> {target_entity}: {e}")
            return False
    
    async def manual_sync(self):
        """手动同步"""
        if self._syncing:
            _LOGGER.warning("同步正在进行中，请稍后再试")
            return
        
        try:
            state1 = self.hass.states.get(self.entity1)
            state2 = self.hass.states.get(self.entity2)
            
            if not state1 or not state2:
                _LOGGER.error("无法获取实体状态，手动同步失败")
                return
            
            # 选择更新时间较晚的状态作为源
            if state1.last_updated > state2.last_updated:
                await self._instant_sync(self.entity1, self.entity2, state1)
            else:
                await self._instant_sync(self.entity2, self.entity1, state2)
            
            _LOGGER.info(f"手动同步完成: {self.entity1} <-> {self.entity2}")
            
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "entity1": self.entity1,
            "entity2": self.entity2,
            "enabled": self.enabled,
            "syncing": self._syncing,
            "stats": self._sync_stats.copy(),
            "retry_counts": self._retry_count.copy(),
            "last_health_check": self._last_health_check,
        }
    
    async def async_unload(self):
        """卸载同步器"""
        for listener in self._listeners:
            listener()
        self._listeners.clear()
        _LOGGER.info(f"双向同步已卸载: {self.entity1} <-> {self.entity2}")


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """设置集成"""
    _LOGGER.info(f"Home Assistant SYMI双向同步集成 v{VERSION} 正在初始化...")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置配置条目"""
    _LOGGER.info(f"设置双向同步配置条目: {entry.title}")
    
    # 轻量级重启容错机制
    await asyncio.sleep(0.1)  # 给系统一点时间完成初始化
    
    # 创建同步协调器
    coordinator = TwoWaySyncCoordinator(hass, entry)
    
    # 设置同步器
    if not await coordinator.async_setup():
        _LOGGER.error(f"无法设置同步器: {entry.title}")
        return False
    
    # 存储协调器
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = coordinator
    SYNC_COORDINATORS[entry.entry_id] = coordinator
    
    # 注册服务
    async def manual_sync_service(call: ServiceCall):
        """手动同步服务"""
        config_entry_id = call.data.get("config_entry_id")
        direction = call.data.get("direction")
        
        if config_entry_id and config_entry_id in SYNC_COORDINATORS:
            coordinator = SYNC_COORDINATORS[config_entry_id]
            if direction == "entity1_to_entity2":
                state1 = hass.states.get(coordinator.entity1)
                if state1:
                    await coordinator._instant_sync(coordinator.entity1, coordinator.entity2, state1)
            elif direction == "entity2_to_entity1":
                state2 = hass.states.get(coordinator.entity2)
                if state2:
                    await coordinator._instant_sync(coordinator.entity2, coordinator.entity1, state2)
            else:
                await coordinator.manual_sync()
        else:
            # 同步所有配置
            for coord in SYNC_COORDINATORS.values():
                await coord.manual_sync()
    
    async def toggle_sync_service(call: ServiceCall):
        """切换同步状态服务"""
        config_entry_id = call.data.get("config_entry_id")
        if config_entry_id and config_entry_id in SYNC_COORDINATORS:
            coordinator = SYNC_COORDINATORS[config_entry_id]
            coordinator.enabled = not coordinator.enabled
            _LOGGER.info(f"同步状态已切换为: {'启用' if coordinator.enabled else '禁用'}")
    
    async def reload_service(call: ServiceCall):
        """重新加载集成服务"""
        _LOGGER.info("重新加载双向同步集成...")
        # 重新加载所有配置条目
        for coord in SYNC_COORDINATORS.values():
            await coord.async_unload()
            await coord.async_setup()
        _LOGGER.info("双向同步集成重新加载完成")
    
    # 注册服务（只注册一次）
    if not hass.services.has_service(DOMAIN, "manual_sync"):
        hass.services.async_register(DOMAIN, "manual_sync", manual_sync_service)
    
    if not hass.services.has_service(DOMAIN, "toggle_sync"):
        hass.services.async_register(DOMAIN, "toggle_sync", toggle_sync_service)
    
    if not hass.services.has_service(DOMAIN, "reload"):
        hass.services.async_register(DOMAIN, "reload", reload_service)
    
    _LOGGER.info(f"双向同步配置条目设置完成: {entry.title}")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目"""
    _LOGGER.info(f"卸载双向同步配置条目: {entry.title}")
    
    # 卸载协调器
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_unload()
        del hass.data[DOMAIN][entry.entry_id]
    
    if entry.entry_id in SYNC_COORDINATORS:
        del SYNC_COORDINATORS[entry.entry_id]
    
    _LOGGER.info(f"双向同步配置条目卸载完成: {entry.title}")
    return True