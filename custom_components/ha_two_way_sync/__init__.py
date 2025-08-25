"""Home Assistant双向同步集成 - v1.1.0"""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry  # type: ignore[import-untyped]
from homeassistant.core import Event, HomeAssistant, State  # type: ignore[import-untyped]
from homeassistant.helpers.event import async_track_state_change_event  # type: ignore[import-untyped]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"


class SimpleSyncCoordinator:
    """简化的双向同步协调器 - 专注于实时同步，解决回弹问题"""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._config = config_entry.data
        self.entity1_id: str | None = config_entry.data.get("entity1")
        self.entity2_id: str | None = config_entry.data.get("entity2")
        self.enabled: bool = config_entry.data.get("enabled", True)
        self._unsubscribe_listeners: list = []
        
        # 简化的防重复机制 - 只使用时间戳防止短时间内重复同步
        self._last_sync_times: dict[str, float] = {}  # 记录每个同步方向的最后执行时间
        self._anti_bounce_interval: float = 0.05  # 50ms防重复间隔，足够防止回弹又保证实时性
        
        # 同步模式配置
        self._sync_mode: str = config_entry.options.get(
            "sync_mode", 
            config_entry.data.get("sync_mode", "perfect")
        )  # perfect/basic
        
    def _is_state_changed(self, new_state: State, old_state: State | None) -> bool:
        """检查状态是否发生了有意义的变化 - 简化版本"""
        if not old_state:
            return True
        
        # 状态变化
        if new_state.state != old_state.state:
            return True
        
        # 重要属性变化检测
        domain = new_state.domain
        important_attrs = []
        
        if domain == "light":
            important_attrs = ["brightness", "color_temp", "rgb_color", "xy_color", "hs_color"]
        elif domain == "fan":
            important_attrs = ["speed", "percentage", "preset_mode", "oscillating"]
        elif domain == "climate":
            important_attrs = ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode"]
        elif domain == "cover":
            important_attrs = ["position", "tilt_position"]
        elif domain == "media_player":
            important_attrs = ["volume_level", "source"]
        elif domain == "humidifier":
            important_attrs = ["humidity", "mode"]
        elif domain == "water_heater":
            important_attrs = ["temperature", "operation_mode"]
        
        # 检查重要属性是否变化
        for attr in important_attrs:
            if old_state.attributes.get(attr) != new_state.attributes.get(attr):
                return True
        
        return False
    
    def _can_sync_now(self, sync_direction: str) -> bool:
        """检查是否可以立即同步 - 简单的防重复机制"""
        current_time = time.time()
        last_sync = self._last_sync_times.get(sync_direction, 0)
        return (current_time - last_sync) > self._anti_bounce_interval
    
    def _mark_sync_time(self, sync_direction: str) -> None:
        """记录同步时间"""
        self._last_sync_times[sync_direction] = time.time()
        
    async def async_setup(self) -> None:
        """设置同步监听器"""
        if not self.enabled or not self.entity1_id or not self.entity2_id:
            _LOGGER.warning(f"同步设置跳过: enabled={self.enabled}, entity1={self.entity1_id}, entity2={self.entity2_id}")
            return
            
        # 检查实体是否存在
        entity1_state = self.hass.states.get(self.entity1_id)
        entity2_state = self.hass.states.get(self.entity2_id)
        
        if not entity1_state:
            _LOGGER.error(f"实体1不存在: {self.entity1_id}")
            return
        if not entity2_state:
            _LOGGER.error(f"实体2不存在: {self.entity2_id}")
            return
            
        _LOGGER.info(f"双向同步设置: {self.entity1_id}({entity1_state.state}) <-> {self.entity2_id}({entity2_state.state})")
            
        # 监听两个实体的状态变化
        try:
            listener1 = async_track_state_change_event(
                self.hass, [self.entity1_id], self._handle_entity1_change
            )
            self._unsubscribe_listeners.append(listener1)
            _LOGGER.debug(f"实体1监听器注册成功: {self.entity1_id}")
        except Exception as e:
            _LOGGER.error(f"实体1监听器注册失败: {self.entity1_id} - {e}")
            return
            
        try:
            listener2 = async_track_state_change_event(
                self.hass, [self.entity2_id], self._handle_entity2_change
            )
            self._unsubscribe_listeners.append(listener2)
            _LOGGER.debug(f"实体2监听器注册成功: {self.entity2_id}")
        except Exception as e:
            _LOGGER.error(f"实体2监听器注册失败: {self.entity2_id} - {e}")
            return
        
        _LOGGER.info(f"双向同步已启用: {self.entity1_id} <-> {self.entity2_id}")
        
    async def _handle_entity1_change(self, event: Event) -> None:
        """处理实体1的状态变化"""
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            if not new_state or not old_state:
                return
            
            # 检查状态是否真的变化了
            if not self._is_state_changed(new_state, old_state):
                return
            
            # 检查防重复机制
            sync_direction = f"{self.entity1_id}->{self.entity2_id}"
            if not self._can_sync_now(sync_direction):
                return
            
            # 记录同步时间并立即同步
            self._mark_sync_time(sync_direction)
            _LOGGER.debug(f"同步触发: {self.entity1_id} -> {self.entity2_id}")
            await self._instant_sync(new_state, self.entity2_id)
            
        except Exception as err:
            _LOGGER.error(f"处理实体1状态变化失败: {err}")
    
    async def _handle_entity2_change(self, event: Event) -> None:
        """处理实体2的状态变化"""
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            if not new_state or not old_state:
                return
            
            # 检查状态是否真的变化了
            if not self._is_state_changed(new_state, old_state):
                return
            
            # 检查防重复机制
            sync_direction = f"{self.entity2_id}->{self.entity1_id}"
            if not self._can_sync_now(sync_direction):
                return
            
            # 记录同步时间并立即同步
            self._mark_sync_time(sync_direction)
            _LOGGER.debug(f"同步触发: {self.entity2_id} -> {self.entity1_id}")
            await self._instant_sync(new_state, self.entity1_id)
            
        except Exception as err:
            _LOGGER.error(f"处理实体2状态变化失败: {err}")
    
    async def _instant_sync(self, source_state: State, target_entity_id: str | None) -> None:
        """立即同步方法 - 一次性同步所有属性，无延迟，无监控"""
        if not target_entity_id:
            return
            
        try:
            # 检查目标实体是否存在
            target_state = self.hass.states.get(target_entity_id)
            if not target_state:
                _LOGGER.error(f"目标实体不存在: {target_entity_id}")
                return
                
            source_domain = source_state.domain
            target_domain = target_entity_id.split(".")[0]
            
            # 根据同步模式选择同步方式
            if self._sync_mode == "perfect" and source_domain == target_domain:
                await self._perfect_sync(source_state, target_entity_id)
            else:
                await self._basic_sync(source_state, target_entity_id)
                
        except Exception as err:
            _LOGGER.error(f"立即同步失败: {source_state.entity_id} -> {target_entity_id} - {err}")
    
    async def _perfect_sync(self, source_state: State, target_entity_id: str) -> None:
        """完美同步 - 一次性同步所有属性"""
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        
        try:
            if domain == "light":
                if source_state.state == "on":
                    # 一次性同步所有灯光属性
                    attrs = {}
                    # 亮度
                    if "brightness" in source_state.attributes:
                        attrs["brightness"] = source_state.attributes["brightness"]
                    
                    # 颜色属性 - 智能选择，避免冲突
                    if "hs_color" in source_state.attributes:
                        attrs["hs_color"] = source_state.attributes["hs_color"]
                    elif "rgb_color" in source_state.attributes:
                        attrs["rgb_color"] = source_state.attributes["rgb_color"]
                    elif "xy_color" in source_state.attributes:
                        attrs["xy_color"] = source_state.attributes["xy_color"]
                    elif "color_temp" in source_state.attributes:
                        attrs["color_temp"] = source_state.attributes["color_temp"]
                    
                    service_data.update(attrs)
                    await self.hass.services.async_call("light", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("light", "turn_off", service_data)
                    
            elif domain == "switch":
                service = "turn_on" if source_state.state == "on" else "turn_off"
                await self.hass.services.async_call("switch", service, service_data)
                
            elif domain == "cover":
                if source_state.state == "open":
                    await self.hass.services.async_call("cover", "open_cover", service_data)
                elif source_state.state == "closed":
                    await self.hass.services.async_call("cover", "close_cover", service_data)
                elif "position" in source_state.attributes:
                    service_data["position"] = source_state.attributes["position"]
                    await self.hass.services.async_call("cover", "set_cover_position", service_data)
                    
            elif domain == "fan":
                if source_state.state == "on":
                    attrs = {k: v for k, v in source_state.attributes.items() 
                            if k in ["speed", "percentage", "preset_mode", "oscillating"]}
                    service_data.update(attrs)
                    await self.hass.services.async_call("fan", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("fan", "turn_off", service_data)
                    
            elif domain == "climate":
                attrs = {k: v for k, v in source_state.attributes.items() 
                        if k in ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode"]}
                service_data.update(attrs)
                if "hvac_mode" in attrs:
                    await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
                if "temperature" in attrs:
                    await self.hass.services.async_call("climate", "set_temperature", service_data)
                    
            elif domain == "humidifier":
                if source_state.state == "on":
                    attrs = {k: v for k, v in source_state.attributes.items() 
                            if k in ["humidity", "mode"]}
                    service_data.update(attrs)
                    await self.hass.services.async_call("humidifier", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("humidifier", "turn_off", service_data)
                    
            elif domain == "media_player":
                if source_state.state == "playing":
                    await self.hass.services.async_call("media_player", "media_play", service_data)
                elif source_state.state == "paused":
                    await self.hass.services.async_call("media_player", "media_pause", service_data)
                elif source_state.state == "off":
                    await self.hass.services.async_call("media_player", "turn_off", service_data)
                # 同步音量
                if "volume_level" in source_state.attributes:
                    service_data["volume_level"] = source_state.attributes["volume_level"]
                    await self.hass.services.async_call("media_player", "volume_set", service_data)
                    
            elif domain == "input_boolean":
                service = "turn_on" if source_state.state == "on" else "turn_off"
                await self.hass.services.async_call("input_boolean", service, service_data)
                
            elif domain == "input_select":
                service_data["option"] = source_state.state
                await self.hass.services.async_call("input_select", "select_option", service_data)
                
            elif domain == "input_number":
                # 使用字符串避免类型问题，Home Assistant会自动转换
                service_data["value"] = source_state.state
                await self.hass.services.async_call("input_number", "set_value", service_data)
                
            elif domain == "input_text":
                service_data["value"] = source_state.state
                await self.hass.services.async_call("input_text", "set_value", service_data)
                
            # 其他设备类型...
            else:
                await self._basic_sync(source_state, target_entity_id)
                
        except Exception as err:
            _LOGGER.error(f"完美同步失败: {domain} - {err}")
            raise
    
    async def _basic_sync(self, source_state: State, target_entity_id: str) -> None:
        """基础同步 - 只同步开关状态"""
        target_domain = target_entity_id.split(".")[0]
        service_data = {"entity_id": target_entity_id}
        
        try:
            # 判断源实体是否为"开"状态
            is_on = source_state.state in ["on", "open", "playing", "cleaning", "heating", "cooling", "auto"]
            
            if target_domain in ["light", "switch", "fan", "humidifier", "input_boolean"]:
                service = "turn_on" if is_on else "turn_off"
                await self.hass.services.async_call(target_domain, service, service_data)
            elif target_domain == "cover":
                service = "open_cover" if is_on else "close_cover"
                await self.hass.services.async_call("cover", service, service_data)
            elif target_domain == "climate":
                hvac_mode = "heat" if is_on else "off"
                service_data["hvac_mode"] = hvac_mode
                await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
            elif target_domain == "media_player":
                if is_on:
                    await self.hass.services.async_call("media_player", "media_play", service_data)
                else:
                    await self.hass.services.async_call("media_player", "media_pause", service_data)
            elif target_domain in ["scene", "script"]:
                if is_on:
                    await self.hass.services.async_call(target_domain, "turn_on", service_data)
                    
        except Exception as err:
            _LOGGER.error(f"基础同步失败: {target_domain} - {err}")
            raise
    
    async def manual_sync_entity1_to_entity2(self) -> bool:
        """手动触发从实体1到实体2的同步"""
        try:
            if not self.entity1_id:
                return False
            entity1_state = self.hass.states.get(self.entity1_id)
            if not entity1_state:
                return False
            
            await self._instant_sync(entity1_state, self.entity2_id)
            return True
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}")
            return False
    
    async def manual_sync_entity2_to_entity1(self) -> bool:
        """手动触发从实体2到实体1的同步"""
        try:
            if not self.entity2_id:
                return False
            entity2_state = self.hass.states.get(self.entity2_id)
            if not entity2_state:
                return False
            
            await self._instant_sync(entity2_state, self.entity1_id)
            return True
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}")
            return False
    
    async def get_sync_status(self) -> dict[str, Any] | None:
        """获取同步状态信息"""
        try:
            entity1_state = self.hass.states.get(self.entity1_id) if self.entity1_id else None
            entity2_state = self.hass.states.get(self.entity2_id) if self.entity2_id else None
            
            return {
                "enabled": self.enabled,
                "listeners_count": len(self._unsubscribe_listeners),
                "entity1": {
                    "id": self.entity1_id,
                    "exists": entity1_state is not None,
                    "state": entity1_state.state if entity1_state else None,
                    "domain": entity1_state.domain if entity1_state else None
                },
                "entity2": {
                    "id": self.entity2_id,
                    "exists": entity2_state is not None,
                    "state": entity2_state.state if entity2_state else None,
                    "domain": entity2_state.domain if entity2_state else None
                }
            }
        except Exception as e:
            _LOGGER.error(f"获取同步状态失败: {e}")
            return None
    
    async def async_unload(self) -> None:
        """卸载同步监听器"""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """设置集成"""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置集成"""
    try:
        entity1_id = entry.data.get("entity1")
        entity2_id = entry.data.get("entity2")
        
        if not entity1_id or not entity2_id:
            _LOGGER.error("配置数据不完整，缺少实体ID")
            return False
            
        # 验证实体是否存在
        if not hass.states.get(entity1_id):
            _LOGGER.error(f"实体1不存在: {entity1_id}")
            return False
            
        if not hass.states.get(entity2_id):
            _LOGGER.error(f"实体2不存在: {entity2_id}")
            return False
        
        _LOGGER.info(f"开始设置双向同步集成: {entity1_id} <-> {entity2_id}")
        
        # 创建协调器
        coordinator = SimpleSyncCoordinator(hass, entry)
        await coordinator.async_setup()
        
        hass.data[DOMAIN][entry.entry_id] = coordinator
        
        # 注册服务（仅在第一次时注册）
        if not hass.services.has_service(DOMAIN, "manual_sync"):
            async def handle_manual_sync(call) -> None:
                """处理手动同步服务"""
                try:
                    entity1 = call.data.get("entity1")
                    entity2 = call.data.get("entity2")
                    
                    if entity1 and entity2:
                        _LOGGER.info(f"开始手动同步: {entity1} -> {entity2}")
                        state1 = hass.states.get(entity1)
                        if state1:
                            # 查找对应的协调器
                            target_coordinator = None
                            for coord in hass.data[DOMAIN].values():
                                if hasattr(coord, 'entity1_id') and hasattr(coord, 'entity2_id'):
                                    if (coord.entity1_id == entity1 and coord.entity2_id == entity2) or \
                                       (coord.entity1_id == entity2 and coord.entity2_id == entity1):
                                        target_coordinator = coord
                                        break
                            
                            if target_coordinator:
                                await target_coordinator._instant_sync(state1, entity2)
                                _LOGGER.info("手动同步完成")
                            else:
                                _LOGGER.error("手动同步失败: 未找到对应的同步配置")
                        else:
                            _LOGGER.error(f"手动同步失败: 实体 {entity1} 不存在")
                except Exception as err:
                    _LOGGER.error(f"手动同步失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "manual_sync", handle_manual_sync)
            _LOGGER.info("已注册手动同步服务")
        
        if not hass.services.has_service(DOMAIN, "toggle_sync"):
            async def handle_toggle_sync(call) -> None:
                """处理切换同步状态服务"""
                try:
                    entity1 = call.data.get("entity1")
                    entity2 = call.data.get("entity2")
                    
                    # 查找对应的协调器
                    target_coordinator = None
                    for coord in hass.data[DOMAIN].values():
                        if hasattr(coord, 'entity1_id') and hasattr(coord, 'entity2_id'):
                            if (coord.entity1_id == entity1 and coord.entity2_id == entity2) or \
                               (coord.entity1_id == entity2 and coord.entity2_id == entity1):
                                target_coordinator = coord
                                break
                    
                    if target_coordinator:
                        old_status = target_coordinator.enabled
                        target_coordinator.enabled = not target_coordinator.enabled
                        _LOGGER.info(f"同步状态已从 {'启用' if old_status else '禁用'} 切换为 {'启用' if target_coordinator.enabled else '禁用'}")
                    else:
                        _LOGGER.error("切换同步状态失败: 未找到对应的同步配置")
                except Exception as err:
                    _LOGGER.error(f"切换同步状态失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "toggle_sync", handle_toggle_sync)
            _LOGGER.info("已注册切换同步状态服务")
        
        _LOGGER.info(f"双向同步集成设置完成: {entity1_id} <-> {entity2_id}")
        return True
        
    except Exception as err:
        _LOGGER.error(f"设置集成失败: {err}", exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目"""
    try:
        _LOGGER.info(f"开始卸载双向同步集成: {entry.entry_id}")
        
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator:
            await coordinator.async_unload()
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.info("双向同步集成卸载完成")
        else:
            _LOGGER.warning(f"未找到协调器: {entry.entry_id}")
        
        # 如果没有更多的配置条目，移除服务
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "manual_sync")
            hass.services.async_remove(DOMAIN, "toggle_sync")
            _LOGGER.info("已移除双向同步服务")
        
        return True
        
    except Exception as err:
        _LOGGER.error(f"卸载集成失败: {err}", exc_info=True)
        return False