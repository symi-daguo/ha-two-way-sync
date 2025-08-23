"""Home Assistant双向同步集成"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.exceptions import ServiceNotFound, HomeAssistantError
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"


class SimpleSyncCoordinator:
    """简单的双向同步协调器"""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self._config = config_entry.data
        self.entity1_id = config_entry.data.get("entity1")
        self.entity2_id = config_entry.data.get("entity2")
        self.enabled = config_entry.data.get("enabled", True)
        self._sync_in_progress = False
        self._unsubscribe_listeners = []
        # 增强的死循环检测机制和内存管理
        self._last_sync_times = {}  # 记录每个实体的最后同步时间
        self._sync_cooldown = 0.15  # 同步冷却时间（秒）- 优化为150ms
        self._state_cache = {}  # 状态缓存，用于去重和内存管理
        self._max_cache_size = 100  # 最大缓存大小，防止内存溢出
        
    async def async_setup(self):
        """设置同步监听器"""
        if not self.enabled or not self.entity1_id or not self.entity2_id:
            return
            
        # 监听两个实体的状态变化
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass, [self.entity1_id], self._handle_entity1_change
            )
        )
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass, [self.entity2_id], self._handle_entity2_change
            )
        )
        
        _LOGGER.info(f"双向同步已启用: {self.entity1_id} <-> {self.entity2_id}")
    
    def _check_important_attrs_changed(self, new_state: State, old_state: State) -> bool:
        """检查重要属性是否发生变化"""
        domain = new_state.domain
        important_attrs = []
        
        # 根据域类型定义重要属性
        if domain == "light":
            important_attrs = ["brightness", "color_temp", "rgb_color", "xy_color", "hs_color"]
        elif domain == "fan":
            important_attrs = ["speed", "percentage", "preset_mode", "oscillating"]
        elif domain == "climate":
            important_attrs = ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode"]
        elif domain == "cover":
            important_attrs = ["position", "tilt_position"]
        elif domain == "media_player":
            important_attrs = ["volume_level", "source", "sound_mode"]
        elif domain == "humidifier":
            important_attrs = ["humidity", "mode"]
        elif domain == "water_heater":
            important_attrs = ["temperature", "operation_mode"]
        elif domain in ["input_number", "input_select", "input_text"]:
            # 对于输入实体，状态本身就是重要的
            return False
        
        # 检查重要属性是否发生变化
        for attr in important_attrs:
            old_val = old_state.attributes.get(attr)
            new_val = new_state.attributes.get(attr)
            if old_val != new_val:
                _LOGGER.debug(f"检测到重要属性变化: {attr} {old_val} -> {new_val}")
                return True
        
        return False
    
    def _is_significant_change(self, new_state: State, old_state: State) -> bool:
        """智能同步判断：检查状态变化是否有意义"""
        if old_state is None:
            return True
        
        # 状态变化总是有意义的
        if new_state.state != old_state.state:
            return True
        
        # 检查重要属性是否变化
        if self._check_important_attrs_changed(new_state, old_state):
            return True
        
        # 检查last_changed时间，避免重复处理相同事件
        if new_state.last_changed == old_state.last_changed:
            return False
        
        return False
    
    def _should_batch_sync(self, entity_id: str) -> bool:
        """判断是否应该进行批量同步优化"""
        # 检查最近的同步频率
        current_time = time.time()
        recent_syncs = [t for t in self._last_sync_times.values() 
                       if current_time - t < 1.0]  # 1秒内的同步次数
        
        # 如果1秒内同步次数超过5次，启用批量优化
        return len(recent_syncs) > 5
    
    def _clean_state_cache(self):
        """清理状态缓存，防止内存溢出"""
        if len(self._state_cache) > self._max_cache_size:
            # 保留最近的一半缓存
            items = list(self._state_cache.items())
            items.sort(key=lambda x: x[1].get('timestamp', 0))
            keep_count = self._max_cache_size // 2
            self._state_cache = dict(items[-keep_count:])
            _LOGGER.debug(f"状态缓存已清理，保留 {keep_count} 个最新条目")
    
    def _validate_light_attributes(self, attributes):
        """验证灯光属性的有效性"""
        validated_attrs = {}
        
        # 验证亮度值 (0-255)
        if "brightness" in attributes:
            brightness = attributes["brightness"]
            if isinstance(brightness, (int, float)) and 0 <= brightness <= 255:
                validated_attrs["brightness"] = int(brightness)
        
        # 验证色温值 (通常在153-500之间)
        if "color_temp" in attributes:
            color_temp = attributes["color_temp"]
            if isinstance(color_temp, (int, float)) and 153 <= color_temp <= 500:
                validated_attrs["color_temp"] = int(color_temp)
        
        # 验证HS颜色值
        if "hs_color" in attributes:
            hs_color = attributes["hs_color"]
            if (isinstance(hs_color, (list, tuple)) and len(hs_color) == 2 and
                isinstance(hs_color[0], (int, float)) and isinstance(hs_color[1], (int, float)) and
                0 <= hs_color[0] <= 360 and 0 <= hs_color[1] <= 100):
                validated_attrs["hs_color"] = [float(hs_color[0]), float(hs_color[1])]
        
        # 验证RGB颜色值
        if "rgb_color" in attributes:
            rgb_color = attributes["rgb_color"]
            if (isinstance(rgb_color, (list, tuple)) and len(rgb_color) == 3 and
                all(isinstance(c, (int, float)) and 0 <= c <= 255 for c in rgb_color)):
                validated_attrs["rgb_color"] = [int(c) for c in rgb_color]
        
        # 验证XY颜色值
        if "xy_color" in attributes:
            xy_color = attributes["xy_color"]
            if (isinstance(xy_color, (list, tuple)) and len(xy_color) == 2 and
                all(isinstance(c, (int, float)) and 0 <= c <= 1 for c in xy_color)):
                validated_attrs["xy_color"] = [float(c) for c in xy_color]
        
        return validated_attrs
    
    async def _sync_light_attributes(self, source_state: State, target_entity_id: str):
        """新的灯光属性同步函数，支持渐进式同步和智能属性处理"""
        try:
            # 验证并获取有效属性
            validated_attrs = self._validate_light_attributes(source_state.attributes)
            
            if not validated_attrs:
                # 如果没有有效属性，只进行基础开关同步
                service_data = {"entity_id": target_entity_id}
                await self.hass.services.async_call("light", "turn_on", service_data)
                _LOGGER.debug(f"灯光基础开关同步: {target_entity_id}")
                return
            
            # 渐进式同步策略：分步骤同步不同属性
            await self._progressive_light_sync(target_entity_id, validated_attrs)
            
        except Exception as e:
            _LOGGER.error(f"灯光属性同步失败: {target_entity_id} - {e}")
            # 错误恢复：回退到基础同步
            try:
                service_data = {"entity_id": target_entity_id}
                await self.hass.services.async_call("light", "turn_on", service_data)
                _LOGGER.debug(f"灯光错误恢复同步: {target_entity_id}")
            except Exception as recovery_err:
                _LOGGER.error(f"灯光错误恢复失败: {target_entity_id} - {recovery_err}")
    
    async def _progressive_light_sync(self, target_entity_id: str, validated_attrs: dict):
        """渐进式灯光同步：先同步关键属性，再同步次要属性"""
        service_data = {"entity_id": target_entity_id}
        
        # 第一步：同步亮度（关键属性）
        if "brightness" in validated_attrs:
            brightness_data = service_data.copy()
            brightness_data["brightness"] = validated_attrs["brightness"]
            
            try:
                await self.hass.services.async_call("light", "turn_on", brightness_data)
                _LOGGER.debug(f"亮度同步成功: {target_entity_id} = {validated_attrs['brightness']}")
                # 短暂延迟确保状态稳定
                await asyncio.sleep(0.05)
            except Exception as e:
                _LOGGER.warning(f"亮度同步失败: {target_entity_id} - {e}")
        
        # 第二步：同步颜色属性（次要属性）
        color_attrs = {}
        
        # 智能颜色属性选择：优先级 hs_color > rgb_color > xy_color > color_temp
        if "hs_color" in validated_attrs:
            color_attrs["hs_color"] = validated_attrs["hs_color"]
        elif "rgb_color" in validated_attrs:
            color_attrs["rgb_color"] = validated_attrs["rgb_color"]
        elif "xy_color" in validated_attrs:
            color_attrs["xy_color"] = validated_attrs["xy_color"]
        elif "color_temp" in validated_attrs:
            color_attrs["color_temp"] = validated_attrs["color_temp"]
        
        # 如果有颜色属性，进行颜色同步
        if color_attrs:
            color_data = service_data.copy()
            color_data.update(color_attrs)
            
            try:
                await self.hass.services.async_call("light", "turn_on", color_data)
                _LOGGER.debug(f"颜色同步成功: {target_entity_id} = {color_attrs}")
            except Exception as e:
                _LOGGER.warning(f"颜色同步失败: {target_entity_id} - {e}")
                
                # 如果颜色同步失败，尝试单独同步色温
                if "color_temp" in validated_attrs and "color_temp" not in color_attrs:
                    try:
                        temp_data = service_data.copy()
                        temp_data["color_temp"] = validated_attrs["color_temp"]
                        await self.hass.services.async_call("light", "turn_on", temp_data)
                        _LOGGER.debug(f"色温恢复同步成功: {target_entity_id} = {validated_attrs['color_temp']}")
                    except Exception as temp_err:
                        _LOGGER.warning(f"色温恢复同步失败: {target_entity_id} - {temp_err}")
    
    def _is_duplicate_state(self, entity_id: str, state: State) -> bool:
        """检查是否为重复状态，用于去重"""
        cache_key = f"{entity_id}_{state.state}"
        current_time = time.time()
        
        # 生成状态指纹（包含重要属性）
        important_attrs = []
        domain = state.domain
        if domain == "light":
            important_attrs = ["brightness", "color_temp", "rgb_color", "xy_color", "hs_color"]
        elif domain == "fan":
            important_attrs = ["speed", "percentage", "preset_mode", "oscillating"]
        elif domain == "climate":
            important_attrs = ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode"]
        elif domain == "cover":
            important_attrs = ["position", "tilt_position"]
        
        state_fingerprint = f"{state.state}_{hash(tuple(state.attributes.get(attr) for attr in important_attrs))}"
        
        if cache_key in self._state_cache:
            cached_data = self._state_cache[cache_key]
            # 如果状态指纹相同且时间间隔很短，认为是重复状态
            if (cached_data.get('fingerprint') == state_fingerprint and 
                current_time - cached_data.get('timestamp', 0) < 1.0):  # 1秒内的重复状态
                return True
        
        # 更新缓存
        self._state_cache[cache_key] = {
            'fingerprint': state_fingerprint,
            'timestamp': current_time
        }
        
        # 定期清理缓存
        if len(self._state_cache) > self._max_cache_size:
            self._clean_state_cache()
        
        return False
    
    async def _handle_entity1_change(self, event: Event):
        """处理实体1的状态变化"""
        if self._sync_in_progress:
            return
            
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            if not new_state or not old_state:
                _LOGGER.debug("状态变化事件数据不完整，跳过同步")
                return
            
            # 使用精确的变化检测
            if not self._is_significant_change(new_state, old_state):
                _LOGGER.debug(f"状态未发生有意义变化，跳过同步: {self.entity1_id}")
                return
            
            # 检查是否为重复状态
            if self._is_duplicate_state(self.entity1_id, new_state):
                _LOGGER.debug(f"检测到重复状态，跳过同步: {self.entity1_id}")
                return
            
            # 定期清理状态缓存
            await self._clean_state_cache()
            
            # 智能同步判断和冷却时间检查
            sync_key = f"{self.entity1_id}->{self.entity2_id}"
            current_time = time.time()
            
            # 批量同步优化
            if self._should_batch_sync(self.entity1_id):
                # 高频同步时增加冷却时间
                effective_cooldown = self._sync_cooldown * 1.5
                _LOGGER.debug(f"检测到高频同步，启用批量优化: {sync_key}")
            else:
                effective_cooldown = self._sync_cooldown
            
            if sync_key in self._last_sync_times:
                time_since_last = current_time - self._last_sync_times[sync_key]
                if time_since_last < effective_cooldown:
                    _LOGGER.debug(f"冷却时间未到，跳过同步: {time_since_last:.2f}s < {effective_cooldown}s")
                    return
            
            # 记录同步时间
            self._last_sync_times[sync_key] = current_time
            
            _LOGGER.debug(f"实体1状态变化: {self.entity1_id} -> {new_state.state}")
            await self._sync_to_entity(new_state, self.entity2_id)
        except Exception as err:
            _LOGGER.error(f"处理实体1状态变化事件时发生错误: {err}", exc_info=True)
    
    async def _handle_entity2_change(self, event: Event):
        """处理实体2的状态变化"""
        if self._sync_in_progress:
            return
            
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            if not new_state or not old_state:
                _LOGGER.debug("状态变化事件数据不完整，跳过同步")
                return
            
            # 使用精确的变化检测
            if not self._is_significant_change(new_state, old_state):
                _LOGGER.debug(f"状态未发生有意义变化，跳过同步: {self.entity2_id}")
                return
            
            # 检查是否为重复状态
            if self._is_duplicate_state(self.entity2_id, new_state):
                _LOGGER.debug(f"检测到重复状态，跳过同步: {self.entity2_id}")
                return
            
            # 定期清理状态缓存
            await self._clean_state_cache()
            
            # 智能同步判断和冷却时间检查
            sync_key = f"{self.entity2_id}->{self.entity1_id}"
            current_time = time.time()
            
            # 批量同步优化
            if self._should_batch_sync(self.entity2_id):
                # 高频同步时增加冷却时间
                effective_cooldown = self._sync_cooldown * 1.5
                _LOGGER.debug(f"检测到高频同步，启用批量优化: {sync_key}")
            else:
                effective_cooldown = self._sync_cooldown
            
            if sync_key in self._last_sync_times:
                time_since_last = current_time - self._last_sync_times[sync_key]
                if time_since_last < effective_cooldown:
                    _LOGGER.debug(f"冷却时间未到，跳过同步: {time_since_last:.2f}s < {effective_cooldown}s")
                    return
            
            # 记录同步时间
            self._last_sync_times[sync_key] = current_time
            
            _LOGGER.debug(f"实体2状态变化: {self.entity2_id} -> {new_state.state}")
            await self._sync_to_entity(new_state, self.entity1_id)
        except Exception as err:
            _LOGGER.error(f"处理实体2状态变化事件时发生错误: {err}", exc_info=True)
    
    async def _sync_to_entity(self, source_state: State, target_entity_id: str):
        """同步状态到目标实体"""
        self._sync_in_progress = True
        sync_start_time = datetime.now().timestamp()
        
        try:
            # 类型检查：确保source_state是State对象
            if not hasattr(source_state, 'domain') or not hasattr(source_state, 'entity_id'):
                _LOGGER.error(f"参数错误：source_state必须是State对象，实际类型: {type(source_state)}")
                return
            
            # 检查目标实体是否存在
            target_state = self.hass.states.get(target_entity_id)
            if not target_state:
                _LOGGER.error(f"目标实体 {target_entity_id} 不存在，无法同步")
                return
                
            source_domain = source_state.domain
            target_domain = target_entity_id.split(".")[0]
            
            _LOGGER.debug(f"开始同步: {source_state.entity_id}({source_domain}) -> {target_entity_id}({target_domain})")
            
            # 获取同步模式配置
            sync_mode = self._config.get("sync_mode", "perfect")
            
            # 根据配置的同步模式选择同步方式
            if sync_mode == "perfect":
                # 完美同步模式：相同类型实体完美同步，不同类型实体基础同步
                if source_domain == target_domain:
                    _LOGGER.debug(f"执行完美同步: {source_domain} -> {target_domain}")
                    await self._perfect_sync(source_state, target_entity_id)
                else:
                    _LOGGER.debug(f"执行基础同步（不同类型）: {source_domain} -> {target_domain}")
                    await self._basic_sync(source_state, target_entity_id)
            else:
                # 基础同步模式：所有实体都只同步开关状态
                _LOGGER.debug(f"执行基础同步（配置模式）: {source_domain} -> {target_domain}")
                await self._basic_sync(source_state, target_entity_id)
                
            # 记录同步耗时
            sync_duration = datetime.now().timestamp() - sync_start_time
            _LOGGER.debug(f"同步完成，耗时: {sync_duration:.3f}秒")
            _LOGGER.info(f"同步完成: {source_state.entity_id} -> {target_entity_id}")
                
        except ServiceNotFound as err:
            _LOGGER.error(f"同步失败，服务不存在: {err}")
        except HomeAssistantError as err:
            _LOGGER.error(f"同步失败，Home Assistant错误: {err}")
        except Exception as err:
            _LOGGER.error(f"同步过程中发生未知错误: {err}", exc_info=True)
        finally:
            # 快速重置标志，提升响应速度
            await asyncio.sleep(0.01)  # 减少延迟到10毫秒，提升大量设备同步效率
            self._sync_in_progress = False
    
    async def _perfect_sync(self, source_state: State, target_entity_id: str):
        """完美同步 - 同步所有属性"""
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        
        try:
            if domain == "light":
                if source_state.state == "on":
                    # 重新设计的灯光同步逻辑，支持亮度和色温独立同步
                    await self._sync_light_attributes(source_state, target_entity_id)
                else:
                    try:
                        await self.hass.services.async_call("light", "turn_off", service_data)
                        _LOGGER.debug(f"灯光关闭同步成功: {target_entity_id}")
                    except Exception as light_err:
                        _LOGGER.error(f"灯光关闭同步失败: {target_entity_id} - {light_err}")
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
                # 同步空调/地暖状态和温度设置
                attrs = {k: v for k, v in source_state.attributes.items() 
                        if k in ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode", "preset_mode"]}
                service_data.update(attrs)
                if "hvac_mode" in attrs:
                    await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
                if "temperature" in attrs:
                    await self.hass.services.async_call("climate", "set_temperature", service_data)
            elif domain == "humidifier":
                # 同步新风/加湿器状态
                if source_state.state == "on":
                    attrs = {k: v for k, v in source_state.attributes.items() 
                            if k in ["humidity", "mode"]}
                    service_data.update(attrs)
                    await self.hass.services.async_call("humidifier", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("humidifier", "turn_off", service_data)
            elif domain == "water_heater":
                # 同步热水器状态和温度
                attrs = {k: v for k, v in source_state.attributes.items() 
                        if k in ["temperature", "operation_mode"]}
                service_data.update(attrs)
                if "temperature" in attrs:
                    await self.hass.services.async_call("water_heater", "set_temperature", service_data)
                if "operation_mode" in attrs:
                    await self.hass.services.async_call("water_heater", "set_operation_mode", service_data)
            elif domain == "vacuum":
                # 同步扫地机状态
                if source_state.state == "cleaning":
                    await self.hass.services.async_call("vacuum", "start", service_data)
                elif source_state.state == "docked":
                    await self.hass.services.async_call("vacuum", "return_to_base", service_data)
                elif source_state.state == "paused":
                    await self.hass.services.async_call("vacuum", "pause", service_data)
            elif domain == "media_player":
                # 同步媒体播放器状态
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
            elif domain == "scene":
                # 激活场景
                await self.hass.services.async_call("scene", "turn_on", service_data)
            elif domain == "script":
                # 执行脚本
                await self.hass.services.async_call("script", "turn_on", service_data)
            elif domain == "input_boolean":
                service = "turn_on" if source_state.state == "on" else "turn_off"
                await self.hass.services.async_call("input_boolean", service, service_data)
            elif domain == "input_select":
                service_data["option"] = source_state.state
                await self.hass.services.async_call("input_select", "select_option", service_data)
            elif domain == "input_number":
                service_data["value"] = float(source_state.state)
                await self.hass.services.async_call("input_number", "set_value", service_data)
            elif domain == "input_text":
                service_data["value"] = source_state.state
                await self.hass.services.async_call("input_text", "set_value", service_data)
            else:
                _LOGGER.warning(f"完美同步暂不支持域类型: {domain}")
        except ServiceNotFound as err:
            _LOGGER.error(f"完美同步失败，服务不存在: {domain} - {err}")
            raise
        except Exception as err:
            _LOGGER.error(f"完美同步失败: {domain} - {err}")
            raise
    
    async def _basic_sync(self, source_state: State, target_entity_id: str):
        """基础同步 - 只同步开关状态"""
        target_domain = target_entity_id.split(".")[0]
        service_data = {"entity_id": target_entity_id}
        
        try:
            # 判断源实体是否为"开"状态
            is_on = source_state.state in ["on", "open", "playing", "cleaning", "heating", "cooling", "auto", "heat", "cool"]
            
            if target_domain in ["light", "switch", "fan", "humidifier", "input_boolean"]:
                service = "turn_on" if is_on else "turn_off"
                await self.hass.services.async_call(target_domain, service, service_data)
            elif target_domain == "cover":
                service = "open_cover" if is_on else "close_cover"
                await self.hass.services.async_call("cover", service, service_data)
            elif target_domain == "climate":
                # 空调/地暖基础同步：开启制热或关闭
                hvac_mode = "heat" if is_on else "off"
                service_data["hvac_mode"] = hvac_mode
                await self.hass.services.async_call("climate", "set_hvac_mode", service_data)
            elif target_domain == "water_heater":
                # 热水器基础同步
                operation_mode = "eco" if is_on else "off"
                service_data["operation_mode"] = operation_mode
                await self.hass.services.async_call("water_heater", "set_operation_mode", service_data)
            elif target_domain == "vacuum":
                # 扫地机基础同步
                if is_on:
                    await self.hass.services.async_call("vacuum", "start", service_data)
                else:
                    await self.hass.services.async_call("vacuum", "return_to_base", service_data)
            elif target_domain == "media_player":
                # 媒体播放器基础同步
                if is_on:
                    await self.hass.services.async_call("media_player", "media_play", service_data)
                else:
                    await self.hass.services.async_call("media_player", "media_pause", service_data)
            elif target_domain in ["scene", "script"]:
                # 场景和脚本只能激活
                if is_on:
                    await self.hass.services.async_call(target_domain, "turn_on", service_data)
            elif target_domain == "input_select":
                # 输入选择器基础同步（设置为第一个或最后一个选项）
                target_state = self.hass.states.get(target_entity_id)
                if target_state and "options" in target_state.attributes:
                    options = target_state.attributes["options"]
                    if options:
                        option = options[0] if is_on else options[-1]
                        service_data["option"] = option
                        await self.hass.services.async_call("input_select", "select_option", service_data)
            elif target_domain == "input_number":
                # 输入数字基础同步（设置为最大值或最小值）
                target_state = self.hass.states.get(target_entity_id)
                if target_state:
                    max_val = target_state.attributes.get("max", 100)
                    min_val = target_state.attributes.get("min", 0)
                    value = max_val if is_on else min_val
                    service_data["value"] = value
                    await self.hass.services.async_call("input_number", "set_value", service_data)
            else:
                # 其他域类型暂不支持基础同步
                _LOGGER.warning(f"基础同步暂不支持目标域类型: {target_domain}")
                
        except ServiceNotFound as err:
            _LOGGER.error(f"基础同步失败，服务不存在: {target_domain} - {err}")
            raise
        except Exception as err:
            _LOGGER.error(f"基础同步失败: {target_domain} - {err}")
            raise
    
    async def async_unload(self):
        """卸载同步监听器"""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
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
            async def handle_manual_sync(call):
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
                                await target_coordinator._sync_to_entity(state1, entity2)
                                _LOGGER.info("手动同步完成")
                            else:
                                _LOGGER.error(f"手动同步失败: 未找到对应的同步配置")
                        else:
                            _LOGGER.error(f"手动同步失败: 实体 {entity1} 不存在")
                except Exception as err:
                    _LOGGER.error(f"手动同步失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "manual_sync", handle_manual_sync)
            _LOGGER.info("已注册手动同步服务")
        
        if not hass.services.has_service(DOMAIN, "toggle_sync"):
            async def handle_toggle_sync(call):
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
                        _LOGGER.error(f"切换同步状态失败: 未找到对应的同步配置")
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