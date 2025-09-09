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
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"
VERSION = "2.1.4"

# 全局同步器字典
SYNC_COORDINATORS = {}

# 实体检查重试配置
ENTITY_CHECK_RETRY_DELAY = 30  # 30秒后重试
ENTITY_CHECK_MAX_RETRIES = 10  # 最多重试10次
ENTITY_CHECK_INTERVAL = timedelta(seconds=30)  # 定期检查间隔

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
        self._sync_cooldown = 2.0  # 增加同步冷却时间到2秒
        self._retry_count = {}
        self._max_retries = 3
        self._sync_source = None  # 记录同步源，防止循环

        # 实体状态跟踪
        self._entities_ready = False
        self._entity_check_retries = 0
        self._entity_check_timer = None

        # 性能监控
        self._sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "last_sync_time": None,
            "average_sync_duration": 0.0,
            "entities_ready": False,
            "last_entity_check": None
        }

        # 健康检查
        self._last_health_check = time.time()
        self._health_check_interval = 300  # 5分钟

        # 事件监听器
        self._listeners = []

        _LOGGER.info(f"初始化双向同步: {self.entity1} <-> {self.entity2}")
    
    async def async_setup(self):
        """设置同步器"""
        # 延迟启动，给HA时间加载所有实体
        await asyncio.sleep(2)

        # 尝试检查实体存在性
        if await self._check_entities_exist():
            await self._setup_listeners()
            self._entities_ready = True
            self._sync_stats["entities_ready"] = True
            _LOGGER.info(f"双向同步设置完成: {self.entity1} <-> {self.entity2}")
            return True
        else:
            # 实体不存在，启动定期检查
            _LOGGER.warning(f"实体暂时不可用，将定期检查: {self.entity1}, {self.entity2}")
            await self._start_entity_check_timer()
            return True  # 不返回False，而是继续尝试

    async def _setup_listeners(self):
        """设置事件监听器"""
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

        # 添加健康检查定时器
        self._listeners.append(
            async_track_time_interval(
                self.hass, self._health_check, ENTITY_CHECK_INTERVAL
            )
        )

    async def _start_entity_check_timer(self):
        """启动实体检查定时器"""
        if self._entity_check_timer:
            self._entity_check_timer()

        self._entity_check_timer = async_track_time_interval(
            self.hass, self._periodic_entity_check, ENTITY_CHECK_INTERVAL
        )
        self._listeners.append(self._entity_check_timer)

    async def _periodic_entity_check(self, now):
        """定期检查实体是否可用"""
        if self._entities_ready:
            return

        if self._entity_check_retries >= ENTITY_CHECK_MAX_RETRIES:
            _LOGGER.error(f"实体检查重试次数已达上限，停止检查: {self.entity1}, {self.entity2}")
            return

        self._entity_check_retries += 1
        self._sync_stats["last_entity_check"] = datetime.now().isoformat()

        if await self._check_entities_exist():
            _LOGGER.info(f"实体现在可用，启用同步: {self.entity1} <-> {self.entity2}")
            await self._setup_listeners()
            self._entities_ready = True
            self._sync_stats["entities_ready"] = True

            # 停止实体检查定时器
            if self._entity_check_timer:
                self._entity_check_timer()
                self._entity_check_timer = None
        else:
            _LOGGER.debug(f"实体仍不可用，将在{ENTITY_CHECK_RETRY_DELAY}秒后重试 (第{self._entity_check_retries}次)")

    async def _health_check(self, now):
        """健康检查"""
        if not self._entities_ready:
            return

        # 检查实体是否仍然存在
        if not await self._check_entities_exist():
            _LOGGER.warning(f"检测到实体不可用，重新启动检查: {self.entity1}, {self.entity2}")
            self._entities_ready = False
            self._sync_stats["entities_ready"] = False
            self._entity_check_retries = 0
            await self._start_entity_check_timer()

        self._last_health_check = time.time()
    
    async def _check_entities_exist(self) -> bool:
        """检查实体是否存在"""
        state1 = self.hass.states.get(self.entity1)
        state2 = self.hass.states.get(self.entity2)

        missing_entities = []
        if not state1:
            missing_entities.append(self.entity1)
        if not state2:
            missing_entities.append(self.entity2)

        if missing_entities:
            if self._entity_check_retries == 0:
                _LOGGER.warning(f"以下实体不存在或尚未加载: {', '.join(missing_entities)}")
            else:
                _LOGGER.debug(f"实体检查第{self._entity_check_retries}次: {', '.join(missing_entities)} 仍不可用")
            return False

        _LOGGER.debug(f"实体检查通过: {self.entity1}, {self.entity2}")
        return True
    
    def _should_sync(self, entity_id: str) -> bool:
        """检查是否应该同步"""
        if not self.enabled:
            _LOGGER.debug(f"同步已禁用: {entity_id}")
            return False

        if not self._entities_ready:
            _LOGGER.debug(f"实体尚未准备就绪: {entity_id}")
            return False

        if self._syncing:
            _LOGGER.debug(f"同步正在进行中，跳过: {entity_id}")
            return False

        # 防止循环同步：如果当前同步源就是这个实体，跳过
        if self._sync_source == entity_id:
            _LOGGER.debug(f"防止循环同步，跳过: {entity_id}")
            return False

        # 检查冷却时间
        last_sync = self._last_sync_time.get(entity_id, 0)
        if time.time() - last_sync < self._sync_cooldown:
            _LOGGER.debug(f"同步冷却中，跳过: {entity_id}")
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
        self._sync_source = source_entity  # 记录同步源
        start_time = time.time()

        try:
            self._last_sync_time[source_entity] = time.time()

            # 检查目标实体可用性
            if not await self._check_entity_availability(target_entity):
                _LOGGER.warning(f"目标实体 {target_entity} 不可用，跳过同步")
                return

            _LOGGER.debug(f"开始同步: {source_entity} -> {target_entity}")

            # 执行完美同步
            success = await self._perfect_sync(source_entity, target_entity, source_state)

            # 更新统计信息
            self._sync_stats["total_syncs"] += 1
            if success:
                self._sync_stats["successful_syncs"] += 1
                self._retry_count[source_entity] = 0
                _LOGGER.debug(f"同步成功: {source_entity} -> {target_entity}")
            else:
                self._sync_stats["failed_syncs"] += 1
                self._retry_count[source_entity] = self._retry_count.get(source_entity, 0) + 1
                _LOGGER.warning(f"同步失败: {source_entity} -> {target_entity}")

            duration = time.time() - start_time
            self._sync_stats["average_sync_duration"] = (
                (self._sync_stats["average_sync_duration"] * (self._sync_stats["total_syncs"] - 1) + duration) /
                self._sync_stats["total_syncs"]
            )
            self._sync_stats["last_sync_time"] = datetime.now().isoformat()

        except Exception as e:
            _LOGGER.error(f"同步过程中发生错误 {source_entity} -> {target_entity}: {e}")
            self._sync_stats["failed_syncs"] += 1
        finally:
            self._syncing = False
            self._sync_source = None  # 清除同步源记录
    
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
        # 停止所有监听器
        for listener in self._listeners:
            if callable(listener):
                listener()
        self._listeners.clear()

        # 停止实体检查定时器
        if self._entity_check_timer:
            self._entity_check_timer()
            self._entity_check_timer = None

        # 重置状态
        self._syncing = False
        self._sync_source = None
        self._entities_ready = False

        _LOGGER.info(f"双向同步已卸载: {self.entity1} <-> {self.entity2}")


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """设置集成"""
    _LOGGER.info(f"Home Assistant SYMI双向同步集成 v{VERSION} 正在初始化...")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置配置条目"""
    _LOGGER.info(f"设置双向同步配置条目: {entry.title}")

    try:
        # 创建同步协调器
        coordinator = TwoWaySyncCoordinator(hass, entry)

        # 设置同步器（现在总是返回True，即使实体暂时不可用）
        await coordinator.async_setup()

        # 存储协调器
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][entry.entry_id] = coordinator
        SYNC_COORDINATORS[entry.entry_id] = coordinator

    except Exception as e:
        _LOGGER.error(f"设置配置条目时发生错误 {entry.title}: {e}")
        return False
    
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
        try:
            # 重新加载所有配置条目
            reload_count = 0
            for coord in SYNC_COORDINATORS.values():
                try:
                    await coord.async_unload()
                    await coord.async_setup()
                    reload_count += 1
                    _LOGGER.debug(f"重新加载同步器: {coord.entity1} <-> {coord.entity2}")
                except Exception as e:
                    _LOGGER.error(f"重新加载同步器失败 {coord.entity1} <-> {coord.entity2}: {e}")

            _LOGGER.info(f"双向同步集成重新加载完成，成功重载 {reload_count} 个同步器")
        except Exception as e:
            _LOGGER.error(f"重新加载集成时发生错误: {e}")
    
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