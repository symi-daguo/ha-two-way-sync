"""Home Assistant双向同步集成 - v1.2.1"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry  # type: ignore[import-untyped]
from homeassistant.core import Event, HomeAssistant, State  # type: ignore[import-untyped]
from homeassistant.helpers.event import async_track_state_change_event  # type: ignore[import-untyped]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"


class SimpleSyncCoordinator:
    """简单的双向同步协调器"""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.entity1_id = config_entry.data.get("entity1")
        self.entity2_id = config_entry.data.get("entity2")
        self.enabled = True
        self._unsubscribe_listeners: list[Callable[[], None]] = []
        self._last_sync_time = 0
        self._anti_bounce_interval = 2.0  # 2秒防抖动，防止循环同步
        
        # 增强的同步锁机制，防止循环同步
        self._sync_in_progress = False
        self._sync_lock = asyncio.Lock()
        self._sync_source = None  # 跟踪当前同步的源实体
        self._sync_ignore_next = set()  # 忽略下一次状态变化的实体集合
        
        # 状态历史跟踪（防抖动）
        self._state_history: dict[str, list[tuple[float, str, dict]]] = {}
        self._max_history_size = 5  # 保留最近5次状态变化
        
        # 状态缓存，避免重复同步相同状态
        self._last_synced_states = {
            self.entity1_id: None,
            self.entity2_id: None
        }
        
        # 同步方向锁定，防止快速反向同步
        self._sync_direction_lock = None
        self._sync_direction_lock_time = 0
        
    def _is_state_changed(self, new_state: State, old_state: State | None) -> bool:
        """检查状态是否发生有意义的变化（增强版）"""
        if old_state is None:
            return True
            
        # 检查是否是刚刚同步过的状态，避免循环同步
        entity_id = new_state.entity_id
        last_synced_state = self._last_synced_states.get(entity_id)
        if last_synced_state and self._states_are_equivalent(new_state, last_synced_state):
            _LOGGER.debug(f"忽略同步引起的状态变化: {entity_id}")
            return False
            
        # 状态值变化
        if new_state.state != old_state.state:
            return True
            
        # 检查重要属性变化（针对不同域）
        domain = new_state.domain
        
        if domain == "light":
            # 灯光：检查亮度、色温、颜色等，增强精度
            important_attrs = ["brightness", "color_temp", "hs_color", "rgb_color", "xy_color"]
            for attr in important_attrs:
                old_val = old_state.attributes.get(attr)
                new_val = new_state.attributes.get(attr)
                
                # 特殊处理亮度值，忽略小于5的变化
                if attr == "brightness":
                    if new_val is not None and old_val is not None:
                        if abs(float(new_val) - float(old_val)) >= 5:
                            return True
                    elif new_val != old_val:
                        return True
                # 特殊处理色温，忽略小于10的变化
                elif attr == "color_temp":
                    if new_val is not None and old_val is not None:
                        if abs(float(new_val) - float(old_val)) >= 10:
                            return True
                    elif new_val != old_val:
                        return True
                else:
                    if not self._values_are_equivalent(old_val, new_val, attr):
                        return True
                    
        elif domain in ["fan", "climate"]:
            # 风扇/空调：检查速度、温度等
            important_attrs = ["speed", "percentage", "temperature", "target_temp_high", "target_temp_low"]
            for attr in important_attrs:
                old_val = old_state.attributes.get(attr)
                new_val = new_state.attributes.get(attr)
                
                # 特殊处理百分比和温度，忽略小变化
                if attr in ["percentage", "temperature"]:
                    if new_val is not None and old_val is not None:
                        if abs(float(new_val) - float(old_val)) >= 2:
                            return True
                    elif new_val != old_val:
                        return True
                else:
                    if not self._values_are_equivalent(old_val, new_val, attr):
                        return True
                    
        elif domain == "cover":
            # 窗帘：检查位置，忽略小于3%的变化
            old_pos = old_state.attributes.get("current_position")
            new_pos = new_state.attributes.get("current_position")
            if old_pos is not None and new_pos is not None:
                if abs(old_pos - new_pos) >= 3:  # 忽略3%以内的变化
                    return True
            elif old_pos != new_pos:
                return True
                
        elif domain == "media_player":
            # 媒体播放器：检查音量，忽略小于0.05的变化
            old_vol = old_state.attributes.get("volume_level")
            new_vol = new_state.attributes.get("volume_level")
            if old_vol is not None and new_vol is not None:
                if abs(float(old_vol) - float(new_vol)) >= 0.05:
                    return True
            elif old_vol != new_vol:
                return True
                
        return False
        
    def _values_are_equivalent(self, old_val, new_val, attr_name: str) -> bool:
        """检查两个值是否等效，忽略微小差异"""
        if old_val == new_val:
            return True
            
        if old_val is None or new_val is None:
            return False
            
        # 对于数值类型，允许小幅误差
        if attr_name in ["brightness", "color_temp"]:
            try:
                old_num = float(old_val)
                new_num = float(new_val)
                # 亮度允许2的误差，色温允许10的误差
                tolerance = 2 if attr_name == "brightness" else 10
                return abs(old_num - new_num) <= tolerance
            except (ValueError, TypeError):
                return False
                
        # 对于颜色值，允许小幅误差
        if attr_name in ["hs_color", "rgb_color", "xy_color"]:
            if isinstance(old_val, (list, tuple)) and isinstance(new_val, (list, tuple)):
                if len(old_val) != len(new_val):
                    return False
                try:
                    for old_component, new_component in zip(old_val, new_val):
                        if abs(float(old_component) - float(new_component)) > 1:
                            return False
                    return True
                except (ValueError, TypeError):
                    return False
                    
        return False
        
    def _colors_are_equivalent(self, color1, color2) -> bool:
        """专门用于颜色比较的方法"""
        if color1 is None and color2 is None:
            return True
        if color1 is None or color2 is None:
            return False
            
        if isinstance(color1, (list, tuple)) and isinstance(color2, (list, tuple)):
            if len(color1) != len(color2):
                return False
            # 颜色容差设为3，避免微小变化触发同步
            return all(abs(a - b) <= 3 for a, b in zip(color1, color2))
            
        return color1 == color2
        
    def _states_are_equivalent(self, state1: State, state2: State) -> bool:
        """检查两个状态是否等效"""
        if state1.state != state2.state:
            return False
            
        # 检查重要属性
        domain = state1.domain
        if domain == "light":
            important_attrs = ["brightness", "color_temp", "hs_color", "rgb_color", "xy_color"]
            for attr in important_attrs:
                if not self._values_are_equivalent(
                    state1.attributes.get(attr),
                    state2.attributes.get(attr),
                    attr
                ):
                    return False
        return True
    
    def _can_sync_now(self, sync_direction: str) -> bool:
        """检查是否可以执行同步，包含增强的防重复和方向锁定机制"""
        current_time = time.time()
        
        # 检查全局防重复间隔（增加到5秒）
        if current_time - self._last_sync_time < 5.0:
            _LOGGER.debug(f"同步被防重复机制阻止: {sync_direction}")
            return False
            
        # 检查同步方向锁定
        if self._sync_direction_lock and self._sync_direction_lock != sync_direction:
            # 如果锁定方向不同，检查是否已过锁定时间（增加到3秒）
            if current_time - self._sync_direction_lock_time < 3.0:  # 3秒方向锁定
                _LOGGER.debug(f"同步被方向锁定阻止: {sync_direction} (当前锁定: {self._sync_direction_lock})")
                return False
            else:
                # 锁定时间已过，清除锁定
                self._sync_direction_lock = None
                
        # 检查是否正在进行同步
        if self._sync_in_progress:
            _LOGGER.debug(f"同步进行中，跳过: {sync_direction}")
            return False
                
        return True
    
    def _mark_sync_time(self, sync_direction: str) -> None:
        """标记同步时间和方向"""
        current_time = time.time()
        self._last_sync_time = current_time
        
        # 设置方向锁定
        self._sync_direction_lock = sync_direction
        self._sync_direction_lock_time = current_time
        
        _LOGGER.debug(f"标记同步时间: {sync_direction} at {current_time}")
        
    async def _delayed_clear_ignore(self, entity_id: str) -> None:
        """延迟清除忽略标记，给状态更新时间"""
        await asyncio.sleep(1.0)  # 等待1秒确保状态更新完成
        self._sync_ignore_next.discard(entity_id)
        _LOGGER.debug(f"清除忽略标记: {entity_id}")
        
    def _record_state_change(self, entity_id: str, state: State) -> None:
        """记录状态变化历史"""
        current_time = time.time()
        if entity_id not in self._state_history:
            self._state_history[entity_id] = []
            
        # 添加新的状态记录
        state_record = (current_time, state.state, dict(state.attributes))
        self._state_history[entity_id].append(state_record)
        
        # 保持历史记录大小
        if len(self._state_history[entity_id]) > self._max_history_size:
            self._state_history[entity_id].pop(0)
            
    def _is_bouncing_state(self, entity_id: str, new_state: State) -> bool:
        """检测是否为抖动状态（快速来回变化）"""
        if entity_id not in self._state_history:
            return False
            
        history = self._state_history[entity_id]
        if len(history) < 3:  # 需要至少3个历史记录
            return False
            
        current_time = time.time()
        recent_changes = [h for h in history if current_time - h[0] <= 5.0]  # 5秒内的变化
        
        if len(recent_changes) >= 3:
            # 检查是否在短时间内反复变化
            states = [h[1] for h in recent_changes]
            if len(set(states)) <= 2 and len(states) >= 3:
                _LOGGER.warning(f"检测到抖动状态: {entity_id}, 最近状态: {states}")
                return True
                
        return False
        
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
        """处理实体1状态变化"""
        if not self.enabled:
            return
            
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
            
        # 记录状态变化历史
        self._record_state_change(new_state.entity_id, new_state)
        
        # 检查是否为抖动状态
        if self._is_bouncing_state(new_state.entity_id, new_state):
            _LOGGER.warning(f"检测到抖动状态，暂停同步: {new_state.entity_id}")
            return
            
        # 检查是否应该忽略此次变化（由同步引起）
        if self.entity1_id in self._sync_ignore_next:
            _LOGGER.debug(f"忽略由同步引起的实体1变化: {self.entity1_id}")
            self._sync_ignore_next.discard(self.entity1_id)
            return
            
        sync_direction = f"{self.entity1_id}->{self.entity2_id}"
        
        # 检查同步锁
        if self._sync_in_progress:
            _LOGGER.debug(f"同步进行中，忽略实体1变化: {self.entity1_id}")
            return
            
        # 检查是否是当前同步的源实体（防止循环）
        if self._sync_source == self.entity1_id:
            _LOGGER.debug(f"检测到可能的循环同步，忽略实体1变化: {self.entity1_id}")
            return
            
        # 检查状态变化
        if not self._is_state_changed(new_state, old_state):
            _LOGGER.debug(f"实体1状态无有意义变化: {self.entity1_id}")
            return
            
        # 检查防重复机制
        if not self._can_sync_now(sync_direction):
            _LOGGER.debug(f"同步被防重复机制阻止: {sync_direction}")
            return
            
        async with self._sync_lock:
            if self._sync_in_progress:
                _LOGGER.debug(f"获取锁后发现同步进行中，跳过: {sync_direction}")
                return
                
            self._sync_in_progress = True
            self._sync_source = self.entity1_id
            try:
                _LOGGER.info(f"开始同步: {sync_direction} (状态: {new_state.state})")
                
                # 标记目标实体忽略下一次变化
                self._sync_ignore_next.add(self.entity2_id)
                
                await self._instant_sync(new_state, self.entity2_id)
                self._mark_sync_time(sync_direction)
                
                # 缓存同步后的状态
                target_state = self.hass.states.get(self.entity2_id)
                if target_state:
                    self._last_synced_states[self.entity2_id] = target_state
                    
                _LOGGER.info(f"同步完成: {sync_direction}")
            except Exception as err:
                _LOGGER.error(f"实体1同步失败: {sync_direction} - {err}", exc_info=True)
                # 同步失败时清除忽略标记
                self._sync_ignore_next.discard(self.entity2_id)
            finally:
                self._sync_in_progress = False
                self._sync_source = None
    
    async def _handle_entity2_change(self, event: Event) -> None:
        """处理实体2状态变化"""
        if not self.enabled:
            return
            
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
            
        # 记录状态变化历史
        self._record_state_change(new_state.entity_id, new_state)
        
        # 检查是否为抖动状态
        if self._is_bouncing_state(new_state.entity_id, new_state):
            _LOGGER.warning(f"检测到抖动状态，暂停同步: {new_state.entity_id}")
            return
            
        # 检查是否应该忽略此次变化（由同步引起）
        if self.entity2_id in self._sync_ignore_next:
            _LOGGER.debug(f"忽略由同步引起的实体2变化: {self.entity2_id}")
            self._sync_ignore_next.discard(self.entity2_id)
            return
            
        sync_direction = f"{self.entity2_id}->{self.entity1_id}"
        
        # 检查同步锁
        if self._sync_in_progress:
            _LOGGER.debug(f"同步进行中，忽略实体2变化: {self.entity2_id}")
            return
            
        # 检查是否是当前同步的源实体（防止循环）
        if self._sync_source == self.entity2_id:
            _LOGGER.debug(f"检测到可能的循环同步，忽略实体2变化: {self.entity2_id}")
            return
            
        # 检查状态变化
        if not self._is_state_changed(new_state, old_state):
            _LOGGER.debug(f"实体2状态无有意义变化: {self.entity2_id}")
            return
            
        # 检查防重复机制
        if not self._can_sync_now(sync_direction):
            _LOGGER.debug(f"同步被防重复机制阻止: {sync_direction}")
            return
            
        async with self._sync_lock:
            if self._sync_in_progress:
                _LOGGER.debug(f"获取锁后发现同步进行中，跳过: {sync_direction}")
                return
                
            self._sync_in_progress = True
            self._sync_source = self.entity2_id
            try:
                _LOGGER.info(f"开始同步: {sync_direction} (状态: {new_state.state})")
                
                # 标记目标实体忽略下一次变化
                self._sync_ignore_next.add(self.entity1_id)
                
                await self._instant_sync(new_state, self.entity1_id)
                self._mark_sync_time(sync_direction)
                
                # 缓存同步后的状态
                target_state = self.hass.states.get(self.entity1_id)
                if target_state:
                    self._last_synced_states[self.entity1_id] = target_state
                    
                _LOGGER.info(f"同步完成: {sync_direction}")
            except Exception as err:
                _LOGGER.error(f"实体2同步失败: {sync_direction} - {err}", exc_info=True)
                # 同步失败时清除忽略标记
                self._sync_ignore_next.discard(self.entity1_id)
            finally:
                self._sync_in_progress = False
                self._sync_source = None
    
    async def _instant_sync(self, source_state: State, target_entity_id: str | None) -> None:
        """立即同步状态 - 使用完美同步模式（增强版）"""
        if not target_entity_id:
            return
            
        # 检查是否存在循环同步
        if self._sync_source == target_entity_id:
            _LOGGER.warning(f"检测到潜在循环同步，跳过: {source_state.entity_id} -> {target_entity_id}")
            return
            
        try:
            _LOGGER.debug(f"执行立即同步: {source_state.entity_id} -> {target_entity_id}")
            _LOGGER.debug(f"源状态: {source_state.state}, 属性: {dict(source_state.attributes)}")
            
            # 使用完美同步模式，确保所有属性都被正确同步
            await self._perfect_sync(source_state, target_entity_id)
            
            _LOGGER.debug(f"立即同步执行完成: {source_state.entity_id} -> {target_entity_id}")
                
        except Exception as err:
            _LOGGER.error(f"立即同步失败: {source_state.entity_id} -> {target_entity_id} - {err}", exc_info=True)
            raise
    
    async def _perfect_sync(self, source_state: State, target_entity_id: str) -> None:
        """完美同步 - 一次性同步所有属性"""
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        
        try:
            if domain == "light":
                # 获取目标实体当前状态，避免不必要的同步
                target_state = self.hass.states.get(target_entity_id)
                
                if source_state.state == "on":
                    # 一次性同步所有灯光属性
                    attrs = {}
                    
                    # 检查是否需要同步亮度
                    source_brightness = source_state.attributes.get("brightness")
                    target_brightness = target_state.attributes.get("brightness") if target_state else None
                    
                    if source_brightness is not None:
                        # 只有亮度差异大于等于5时才同步
                        if target_brightness is None or abs(source_brightness - target_brightness) >= 5:
                            attrs["brightness"] = source_brightness
                    
                    # 检查是否需要同步颜色
                    color_synced = False
                    
                    # 颜色属性 - 智能选择，避免冲突
                    if "hs_color" in source_state.attributes:
                        source_color = source_state.attributes["hs_color"]
                        target_color = target_state.attributes.get("hs_color") if target_state else None
                        if not self._colors_are_equivalent(source_color, target_color):
                            attrs["hs_color"] = source_color
                            color_synced = True
                    elif "rgb_color" in source_state.attributes:
                        source_color = source_state.attributes["rgb_color"]
                        target_color = target_state.attributes.get("rgb_color") if target_state else None
                        if not self._colors_are_equivalent(source_color, target_color):
                            attrs["rgb_color"] = source_color
                            color_synced = True
                    elif "xy_color" in source_state.attributes:
                        source_color = source_state.attributes["xy_color"]
                        target_color = target_state.attributes.get("xy_color") if target_state else None
                        if not self._colors_are_equivalent(source_color, target_color):
                            attrs["xy_color"] = source_color
                            color_synced = True
                    elif "color_temp" in source_state.attributes:
                        source_temp = source_state.attributes["color_temp"]
                        target_temp = target_state.attributes.get("color_temp") if target_state else None
                        if target_temp is None or abs(source_temp - target_temp) >= 10:
                            attrs["color_temp"] = source_temp
                    
                    # 只有在有实际变化时才调用服务
                    if attrs or (target_state and target_state.state != "on"):
                        service_data.update(attrs)
                        await self.hass.services.async_call("light", "turn_on", service_data)
                else:
                    # 关灯
                    if target_state and target_state.state != "off":
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
        """手动触发从实体1到实体2的同步（增强版）"""
        try:
            if not self.entity1_id:
                _LOGGER.error("手动同步失败: 实体1 ID为空")
                return False
                
            entity1_state = self.hass.states.get(self.entity1_id)
            if not entity1_state:
                _LOGGER.error(f"手动同步失败: 实体1不存在 {self.entity1_id}")
                return False
            
            sync_direction = f"{self.entity1_id}->{self.entity2_id}(手动)"
            
            async with self._sync_lock:
                if self._sync_in_progress:
                    _LOGGER.warning(f"手动同步被阻止: 同步进行中 {sync_direction}")
                    return False
                    
                # 手动同步时清除所有忽略标记和同步源
                self._sync_ignore_next.clear()
                self._sync_source = None
                    
                self._sync_in_progress = True
                try:
                    _LOGGER.info(f"开始手动同步: {sync_direction}")
                    await self._instant_sync(entity1_state, self.entity2_id)
                    self._mark_sync_time(sync_direction)
                    
                    # 缓存同步后的状态
                    target_state = self.hass.states.get(self.entity2_id)
                    if target_state:
                        self._last_synced_states[self.entity2_id] = target_state
                        
                    _LOGGER.info(f"手动同步完成: {sync_direction}")
                    return True
                finally:
                    self._sync_in_progress = False
                    
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}", exc_info=True)
            return False
    
    async def manual_sync_entity2_to_entity1(self) -> bool:
        """手动触发从实体2到实体1的同步（增强版）"""
        try:
            if not self.entity2_id:
                _LOGGER.error("手动同步失败: 实体2 ID为空")
                return False
                
            entity2_state = self.hass.states.get(self.entity2_id)
            if not entity2_state:
                _LOGGER.error(f"手动同步失败: 实体2不存在 {self.entity2_id}")
                return False
            
            sync_direction = f"{self.entity2_id}->{self.entity1_id}(手动)"
            
            async with self._sync_lock:
                if self._sync_in_progress:
                    _LOGGER.warning(f"手动同步被阻止: 同步进行中 {sync_direction}")
                    return False
                    
                # 手动同步时清除所有忽略标记和同步源
                self._sync_ignore_next.clear()
                self._sync_source = None
                    
                self._sync_in_progress = True
                try:
                    _LOGGER.info(f"开始手动同步: {sync_direction}")
                    await self._instant_sync(entity2_state, self.entity1_id)
                    self._mark_sync_time(sync_direction)
                    
                    # 缓存同步后的状态
                    target_state = self.hass.states.get(self.entity1_id)
                    if target_state:
                        self._last_synced_states[self.entity1_id] = target_state
                        
                    _LOGGER.info(f"手动同步完成: {sync_direction}")
                    return True
                finally:
                    self._sync_in_progress = False
                    
        except Exception as e:
            _LOGGER.error(f"手动同步失败: {e}", exc_info=True)
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