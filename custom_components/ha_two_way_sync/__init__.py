"""Home Assistant双向同步集成"""
import asyncio
import logging
import time
import inspect
from datetime import datetime
from typing import Any, Dict, Optional, Callable

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
        
        # 步进设备管理
        self._action_states = {}  # 动作状态跟踪 {entity_id: {state, start_time, master_entity, target_values}}
        self._progressive_attributes = {
            'light': ['brightness', 'color_temp', 'rgb_color', 'xy_color', 'hs_color'],
            'cover': ['position', 'tilt_position'],
            'climate': ['temperature', 'target_temp_high', 'target_temp_low'],
            'fan': ['percentage', 'speed'],
            'media_player': ['volume_level'],
            'humidifier': ['humidity'],
            'water_heater': ['temperature']
        }
        self._action_completion_timeout = config_entry.options.get(
            "action_completion_timeout", 
            config_entry.data.get("action_completion_timeout", 3.0)
        )  # 动作完成检测超时时间
        self._progressive_sync_mode = config_entry.options.get(
            "progressive_sync_mode", 
            config_entry.data.get("progressive_sync_mode", "smart")
        )  # smart/realtime/master_slave
        self._sync_mode = config_entry.options.get(
            "sync_mode", 
            config_entry.data.get("sync_mode", "perfect")
        )  # perfect/basic
        self._stability_check_interval = 0.5  # 属性值稳定性检查间隔（秒）
        
    def _validate_async_method(self, method: Callable, method_name: str) -> bool:
        """验证方法是否为async方法，防止async/sync混用错误"""
        try:
            if inspect.iscoroutinefunction(method):
                return True
            else:
                _LOGGER.error(f"方法类型错误: {method_name} 应该是async方法但实际是普通方法")
                return False
        except Exception as e:
            _LOGGER.error(f"方法类型验证失败: {method_name} - {e}")
            return False
    
    def _is_progressive_device(self, entity_id: str) -> bool:
        """检测是否为步进设备（需要特殊同步处理的设备）"""
        try:
            state = self.hass.states.get(entity_id)
            if not state:
                return False
            
            domain = state.domain
            return domain in self._progressive_attributes
        except Exception as e:
            _LOGGER.error(f"步进设备检测失败: {entity_id} - {e}")
            return False
    
    def _get_progressive_attributes(self, entity_id: str) -> list:
        """获取实体的步进属性列表"""
        try:
            state = self.hass.states.get(entity_id)
            if not state:
                return []
            
            domain = state.domain
            return self._progressive_attributes.get(domain, [])
        except Exception as e:
            _LOGGER.error(f"获取步进属性失败: {entity_id} - {e}")
            return []
    
    def _has_progressive_change(self, old_state, new_state) -> bool:
        """检测是否包含步进属性的变化"""
        try:
            if not old_state or not new_state:
                return False
            
            progressive_attrs = self._get_progressive_attributes(new_state.entity_id)
            if not progressive_attrs:
                return False
            
            # 检查步进属性是否有变化
            for attr in progressive_attrs:
                old_value = old_state.attributes.get(attr)
                new_value = new_state.attributes.get(attr)
                
                if old_value != new_value:
                    _LOGGER.debug(f"[PROGRESSIVE] 检测到步进属性变化: {new_state.entity_id}.{attr} {old_value} -> {new_value}")
                    return True
            
            return False
        except Exception as e:
            _LOGGER.error(f"步进变化检测失败: {e}")
            return False
    
    def _is_instant_operation(self, old_state, new_state) -> bool:
        """检测是否为瞬时操作（如开关）"""
        try:
            if not old_state or not new_state:
                return True
            
            # 只有状态变化，没有步进属性变化，认为是瞬时操作
            state_changed = old_state.state != new_state.state
            has_progressive = self._has_progressive_change(old_state, new_state)
            
            return state_changed and not has_progressive
        except Exception as e:
            _LOGGER.error(f"瞬时操作检测失败: {e}")
            return True
    
    def _get_action_state(self, entity_id: str) -> str:
        """获取实体的动作状态"""
        return self._action_states.get(entity_id, {}).get('state', 'idle')
    
    def _set_action_state(self, entity_id: str, state: str, master_entity: str = None, target_values: dict = None):
        """设置实体的动作状态"""
        if entity_id not in self._action_states:
            self._action_states[entity_id] = {}
        
        self._action_states[entity_id].update({
            'state': state,
            'start_time': time.time(),
            'master_entity': master_entity,
            'target_values': target_values or {}
        })
        
        _LOGGER.debug(f"[ACTION_STATE] {entity_id} 状态变更: {state}, 主控: {master_entity}")
    
    def _clear_action_state(self, entity_id: str):
        """清除实体的动作状态"""
        if entity_id in self._action_states:
            del self._action_states[entity_id]
            _LOGGER.debug(f"[ACTION_STATE] {entity_id} 状态已清除")
    
    def _is_action_in_progress(self, entity_id: str) -> bool:
        """检查实体是否正在执行动作"""
        state = self._get_action_state(entity_id)
        return state in ['starting', 'in_progress']
    
    def _is_action_timeout(self, entity_id: str) -> bool:
        """检查动作是否超时"""
        action_info = self._action_states.get(entity_id)
        if not action_info:
            return False
        
        elapsed = time.time() - action_info.get('start_time', 0)
        return elapsed > self._action_completion_timeout
    
    def _get_master_entity(self, entity_id: str) -> str:
        """获取实体的主控设备"""
        return self._action_states.get(entity_id, {}).get('master_entity')
    
    def _is_slave_entity(self, entity_id: str, other_entity_id: str) -> bool:
        """检查实体是否为从设备"""
        master = self._get_master_entity(entity_id)
        return master == other_entity_id
    
    async def _start_progressive_action(self, entity_id: str, target_state, master_entity: str = None):
        """开始步进动作"""
        try:
            # 提取目标值
            target_values = {}
            progressive_attrs = self._get_progressive_attributes(entity_id)
            
            for attr in progressive_attrs:
                if hasattr(target_state, 'attributes') and attr in target_state.attributes:
                    target_values[attr] = target_state.attributes[attr]
            
            # 设置动作状态
            self._set_action_state(
                entity_id, 
                'starting', 
                master_entity or entity_id,
                target_values
            )
            
            _LOGGER.info(f"[PROGRESSIVE] 开始步进动作: {entity_id}, 目标值: {target_values}, 主控: {master_entity or entity_id}")
            
        except Exception as e:
            _LOGGER.error(f"开始步进动作失败: {entity_id} - {e}")
    
    async def _update_action_progress(self, entity_id: str, current_state):
        """更新动作进度"""
        try:
            action_info = self._action_states.get(entity_id)
            if not action_info:
                return
            
            current_state_name = action_info.get('state')
            if current_state_name == 'starting':
                # 从starting转换到in_progress
                self._set_action_state(
                    entity_id,
                    'in_progress',
                    action_info.get('master_entity'),
                    action_info.get('target_values')
                )
                _LOGGER.debug(f"[PROGRESSIVE] {entity_id} 动作进行中")
            
        except Exception as e:
            _LOGGER.error(f"更新动作进度失败: {entity_id} - {e}")
    
    async def _handle_progressive_sync(self, source_entity_id: str, target_entity_id: str, new_state: State, old_state: State):
        """处理步进设备的立即同步逻辑 - 主动触发设备为主控，从设备立即执行最新操作"""
        try:
            _LOGGER.info(f"[PROGRESSIVE] 开始立即同步: {source_entity_id} -> {target_entity_id}")
            
            # 主动触发的设备自动成为主控设备
            master_entity = source_entity_id
            slave_entity = target_entity_id
            
            _LOGGER.info(f"[PROGRESSIVE] 主从关系确定: 主控={master_entity} (主动触发), 从设备={slave_entity}")
            
            # 取消所有之前的同步任务（支持快速连续操作）
            sync_key = f"{master_entity}->{slave_entity}"
            if not hasattr(self, '_progressive_sync_tasks'):
                self._progressive_sync_tasks = {}
            
            # 取消该同步对的所有之前任务
            if sync_key in self._progressive_sync_tasks:
                for task in self._progressive_sync_tasks[sync_key]:
                    if not task.done():
                        _LOGGER.info(f"[PROGRESSIVE] 取消之前的同步任务，执行最新操作")
                        task.cancel()
                self._progressive_sync_tasks[sync_key].clear()
            else:
                self._progressive_sync_tasks[sync_key] = []
            
            # 从设备立即执行主控设备的最新目标值（不等待，不监控过程）
            _LOGGER.info(f"[PROGRESSIVE] 从设备立即执行主控设备的最新目标值: {slave_entity}")
            _LOGGER.info(f"[PROGRESSIVE] 目标状态: {new_state.state}, 属性: {dict(new_state.attributes)}")
            
            # 创建新的立即同步任务
            sync_task = asyncio.create_task(self._immediate_sync(new_state, slave_entity))
            self._progressive_sync_tasks[sync_key].append(sync_task)
            
            # 等待同步完成（立即执行）
            await sync_task
            
            # 记录主控设备的最新操作时间和状态
            self._last_master_action_time = time.time()
            self._last_master_entity = master_entity
            self._last_master_state = new_state
            
            _LOGGER.info(f"[PROGRESSIVE] 立即同步完成: {master_entity} -> {slave_entity}")
            
        except asyncio.CancelledError:
            _LOGGER.info(f"[PROGRESSIVE] 同步任务被取消（快速连续操作）: {source_entity_id} -> {target_entity_id}")
        except Exception as e:
            _LOGGER.error(f"[PROGRESSIVE] 立即同步失败: {source_entity_id} -> {target_entity_id} - {e}")
    
    # 移除复杂的动作监控逻辑，改为立即同步机制
    # 不再需要 _monitor_action_completion_optimized 方法
    
    # 移除复杂的状态检查和最终同步逻辑
    # 立即同步机制不需要这些方法：
    # - _check_action_stability
    # - _check_state_stability  
    # - _perform_final_sync
    # - _perform_final_confirmation
        
    async def async_setup(self):
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
            
        _LOGGER.info(f"[DEBUG] 实体状态检查通过: {self.entity1_id}({entity1_state.state}) <-> {self.entity2_id}({entity2_state.state})")
        _LOGGER.info(f"[DEBUG] 实体1域: {entity1_state.domain}, 实体2域: {entity2_state.domain}")
        _LOGGER.info(f"[DEBUG] 实体1属性: {dict(entity1_state.attributes)}")
        _LOGGER.info(f"[DEBUG] 实体2属性: {dict(entity2_state.attributes)}")
            
        # 监听两个实体的状态变化
        _LOGGER.info(f"[DEBUG] 开始注册事件监听器...")
        
        try:
            listener1 = async_track_state_change_event(
                self.hass, [self.entity1_id], self._handle_entity1_change
            )
            self._unsubscribe_listeners.append(listener1)
            _LOGGER.info(f"[DEBUG] 实体1监听器注册成功: {self.entity1_id}")
        except Exception as e:
            _LOGGER.error(f"[DEBUG] 实体1监听器注册失败: {self.entity1_id} - {e}")
            return
            
        try:
            listener2 = async_track_state_change_event(
                self.hass, [self.entity2_id], self._handle_entity2_change
            )
            self._unsubscribe_listeners.append(listener2)
            _LOGGER.info(f"[DEBUG] 实体2监听器注册成功: {self.entity2_id}")
        except Exception as e:
            _LOGGER.error(f"[DEBUG] 实体2监听器注册失败: {self.entity2_id} - {e}")
            return
        
        _LOGGER.info(f"[DEBUG] 双向同步已启用: {self.entity1_id} <-> {self.entity2_id}")
        _LOGGER.info(f"[DEBUG] 事件监听器已注册，监听器数量: {len(self._unsubscribe_listeners)}")
        
        # 验证监听器状态
        await self._verify_listeners_health()
    
    async def _verify_listeners_health(self):
        """验证事件监听器的健康状态"""
        try:
            _LOGGER.info(f"[DEBUG] 开始验证监听器健康状态...")
            
            # 检查监听器数量
            expected_listeners = 2
            actual_listeners = len(self._unsubscribe_listeners)
            _LOGGER.info(f"[DEBUG] 监听器数量检查: 期望={expected_listeners}, 实际={actual_listeners}")
            
            if actual_listeners != expected_listeners:
                _LOGGER.error(f"[DEBUG] 监听器数量不匹配！期望{expected_listeners}个，实际{actual_listeners}个")
                return False
            
            # 检查实体是否仍然存在
            entity1_exists = self.hass.states.get(self.entity1_id) is not None
            entity2_exists = self.hass.states.get(self.entity2_id) is not None
            _LOGGER.info(f"[DEBUG] 实体存在性检查: {self.entity1_id}={entity1_exists}, {self.entity2_id}={entity2_exists}")
            
            if not entity1_exists or not entity2_exists:
                _LOGGER.error(f"[DEBUG] 实体不存在！entity1={entity1_exists}, entity2={entity2_exists}")
                return False
            
            # 检查监听器是否可调用
            for i, listener in enumerate(self._unsubscribe_listeners):
                if not callable(listener):
                    _LOGGER.error(f"[DEBUG] 监听器{i}不可调用！")
                    return False
            
            _LOGGER.info(f"[DEBUG] 监听器健康检查通过！")
            return True
            
        except Exception as e:
             _LOGGER.error(f"[DEBUG] 监听器健康检查失败: {e}")
             return False
     
    async def manual_sync_entity1_to_entity2(self, force: bool = False):
        """手动触发从实体1到实体2的同步（调试用）"""
        _LOGGER.info(f"[MANUAL] 手动触发同步: {self.entity1_id} -> {self.entity2_id}, force={force}")
        
        try:
            entity1_state = self.hass.states.get(self.entity1_id)
            if not entity1_state:
                _LOGGER.error(f"[MANUAL] 实体1不存在: {self.entity1_id}")
                return False
            
            _LOGGER.info(f"[MANUAL] 实体1当前状态: {entity1_state.state}")
            _LOGGER.info(f"[MANUAL] 实体1属性: {dict(entity1_state.attributes)}")
            
            # 强制同步
            self._syncing = True
            await self._sync_to_entity(entity1_state, self.entity2_id)
            self._syncing = False
            
            _LOGGER.info(f"[MANUAL] 手动同步完成")
            return True
            
        except Exception as e:
            _LOGGER.error(f"[MANUAL] 手动同步失败: {e}")
            self._syncing = False
            return False
    
    async def manual_sync_entity2_to_entity1(self, force: bool = False):
        """手动触发从实体2到实体1的同步（调试用）"""
        _LOGGER.info(f"[MANUAL] 手动触发同步: {self.entity2_id} -> {self.entity1_id}, force={force}")
        
        try:
            entity2_state = self.hass.states.get(self.entity2_id)
            if not entity2_state:
                _LOGGER.error(f"[MANUAL] 实体2不存在: {self.entity2_id}")
                return False
            
            _LOGGER.info(f"[MANUAL] 实体2当前状态: {entity2_state.state}")
            _LOGGER.info(f"[MANUAL] 实体2属性: {dict(entity2_state.attributes)}")
            
            # 强制同步
            self._syncing = True
            await self._sync_to_entity(entity2_state, self.entity1_id)
            self._syncing = False
            
            _LOGGER.info(f"[MANUAL] 手动同步完成")
            return True
            
        except Exception as e:
            _LOGGER.error(f"[MANUAL] 手动同步失败: {e}")
            self._syncing = False
            return False
    
    async def get_sync_status(self):
        """获取同步状态信息（调试用）"""
        try:
            entity1_state = self.hass.states.get(self.entity1_id)
            entity2_state = self.hass.states.get(self.entity2_id)
            
            status = {
                "enabled": self.enabled,
                "syncing": self._syncing,
                "listeners_count": len(self._unsubscribe_listeners),
                "entity1": {
                    "id": self.entity1_id,
                    "exists": entity1_state is not None,
                    "state": entity1_state.state if entity1_state else None,
                    "domain": entity1_state.domain if entity1_state else None,
                    "attributes": dict(entity1_state.attributes) if entity1_state else None
                },
                "entity2": {
                    "id": self.entity2_id,
                    "exists": entity2_state is not None,
                    "state": entity2_state.state if entity2_state else None,
                    "domain": entity2_state.domain if entity2_state else None,
                    "attributes": dict(entity2_state.attributes) if entity2_state else None
                },
                "last_sync_times": {
                    "entity1": self._last_sync_time.get(self.entity1_id),
                    "entity2": self._last_sync_time.get(self.entity2_id)
                }
            }
            
            _LOGGER.info(f"[STATUS] 同步状态: {status}")
            return status
            
        except Exception as e:
            _LOGGER.error(f"[STATUS] 获取同步状态失败: {e}")
            return None
     
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
    
    def _is_significant_change(self, new_state: State, old_state: State, force_sync: bool = False) -> bool:
        """智能同步判断：检查状态变化是否有意义"""
        _LOGGER.info(f"[DEBUG] 状态变化检测开始: entity={new_state.entity_id}")
        _LOGGER.info(f"[DEBUG] 新状态: {new_state.state}, 旧状态: {old_state.state if old_state else None}")
        
        if old_state is None:
            _LOGGER.info(f"[DEBUG] 旧状态为空，认为是有意义变化")
            return True
        
        # 强制同步模式
        if force_sync:
            _LOGGER.info(f"[DEBUG] 强制同步模式，跳过检测")
            return True
        
        # 状态变化总是有意义的
        if new_state.state != old_state.state:
            _LOGGER.info(f"[DEBUG] 状态发生变化: {old_state.state} -> {new_state.state}")
            return True
        
        # 检查重要属性是否变化
        attrs_changed = self._check_important_attrs_changed(new_state, old_state)
        _LOGGER.info(f"[DEBUG] 重要属性变化检测结果: {attrs_changed}")
        if attrs_changed:
            return True
        
        # 放宽时间检查条件 - 如果last_changed时间不同，也认为是有意义的变化
        time_changed = new_state.last_changed != old_state.last_changed
        _LOGGER.info(f"[DEBUG] 时间变化检测: {time_changed}")
        if time_changed:
            # 检查时间差是否足够大（避免微小时间差导致的误判）
            time_diff = abs((new_state.last_changed - old_state.last_changed).total_seconds())
            _LOGGER.info(f"[DEBUG] 时间差: {time_diff}秒")
            if time_diff > 0.1:  # 大于0.1秒的时间差认为是有意义的
                return True
        
        # 对于灯光设备，额外检查更多属性变化
        if new_state.domain == "light":
            light_attrs = ["brightness", "color_temp", "rgb_color", "xy_color", "hs_color", "effect", "white_value"]
            for attr in light_attrs:
                old_val = old_state.attributes.get(attr)
                new_val = new_state.attributes.get(attr)
                if old_val != new_val:
                    _LOGGER.info(f"[DEBUG] 灯光属性变化: {attr} {old_val} -> {new_val}")
                    return True
        
        _LOGGER.info(f"[DEBUG] 未检测到有意义的状态变化")
        return False
    
    def _should_batch_sync(self, entity_id: str) -> bool:
        """判断是否应该进行批量同步优化"""
        # 检查最近的同步频率
        current_time = time.time()
        recent_syncs = [t for t in self._last_sync_times.values() 
                       if current_time - t < 1.0]  # 1秒内的同步次数
        
        # 如果1秒内同步次数超过5次，启用批量优化
        return len(recent_syncs) > 5
    
    async def _clean_state_cache(self):
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
        
        # 验证色温值 (扩大范围以支持更多设备，通常在100-1000之间)
        if "color_temp" in attributes:
            color_temp = attributes["color_temp"]
            if isinstance(color_temp, (int, float)) and 100 <= color_temp <= 1000:
                validated_attrs["color_temp"] = int(color_temp)
                _LOGGER.debug(f"色温验证通过: {color_temp}")
            else:
                _LOGGER.warning(f"色温值超出范围: {color_temp} (有效范围: 100-1000)")
        
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
                if "color_temp" in validated_attrs:
                    await self._sync_color_temperature(target_entity_id, validated_attrs["color_temp"], service_data)
    
    async def _sync_color_temperature(self, target_entity_id: str, color_temp: int, base_service_data: dict):
        """专门的色温同步函数，支持多种色温参数格式"""
        try:
            # 方法1：使用color_temp参数
            temp_data = base_service_data.copy()
            temp_data["color_temp"] = color_temp
            await self.hass.services.async_call("light", "turn_on", temp_data)
            _LOGGER.info(f"色温同步成功 (color_temp): {target_entity_id} = {color_temp}")
            return True
        except Exception as temp_err:
            _LOGGER.warning(f"色温同步失败 (color_temp): {target_entity_id} - {temp_err}")
            
            # 方法2：尝试使用kelvin参数
            try:
                kelvin_value = int(1000000 / color_temp)
                kelvin_data = base_service_data.copy()
                kelvin_data["kelvin"] = kelvin_value
                await self.hass.services.async_call("light", "turn_on", kelvin_data)
                _LOGGER.info(f"色温同步成功 (kelvin): {target_entity_id} = {kelvin_value}K")
                return True
            except Exception as kelvin_err:
                _LOGGER.warning(f"色温同步失败 (kelvin): {target_entity_id} - {kelvin_err}")
                
                # 方法3：尝试使用color_temp_kelvin参数
                try:
                    kelvin_data = base_service_data.copy()
                    kelvin_data["color_temp_kelvin"] = kelvin_value
                    await self.hass.services.async_call("light", "turn_on", kelvin_data)
                    _LOGGER.info(f"色温同步成功 (color_temp_kelvin): {target_entity_id} = {kelvin_value}K")
                    return True
                except Exception as kelvin_temp_err:
                    _LOGGER.error(f"所有色温同步方法均失败: {target_entity_id} - {kelvin_temp_err}")
                    return False
    
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
        _LOGGER.info(f"[LISTENER] ===== 实体1监听器被触发 ===== {self.entity1_id}")
        _LOGGER.info(f"[LISTENER] 事件类型: {event.event_type}")
        _LOGGER.info(f"[LISTENER] 事件数据: {event.data}")
        _LOGGER.info(f"[DEBUG] 实体1状态变化事件触发: {self.entity1_id}")
        
        if self._sync_in_progress:
            _LOGGER.debug(f"[DEBUG] 同步正在进行中，跳过: {self.entity1_id}")
            return
            
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            _LOGGER.info(f"[DEBUG] 事件数据: new_state={new_state.state if new_state else None}, old_state={old_state.state if old_state else None}")
            
            if not new_state or not old_state:
                _LOGGER.warning(f"[DEBUG] 状态变化事件数据不完整，跳过同步: new_state={new_state}, old_state={old_state}")
                return
            
            # 检查是否为步进设备
            is_progressive = self._is_progressive_device(new_state.entity_id)
            _LOGGER.info(f"[DEBUG] 步进设备检测: {is_progressive}")
            
            # 步进设备只在触发时立即同步，不进行实时同步
            if is_progressive and self._has_progressive_change(old_state, new_state):
                _LOGGER.info(f"[DEBUG] 检测到步进设备变化，启用立即同步模式: {self.entity1_id}")
                await self._handle_progressive_sync(self.entity1_id, self.entity2_id, new_state, old_state)
                return
            
            # 使用精确的变化检测
            is_significant = self._is_significant_change(new_state, old_state, force_sync=False)
            _LOGGER.info(f"[DEBUG] 状态变化检测结果: {is_significant}, {old_state.state}->{new_state.state}")
            
            if not is_significant:
                _LOGGER.info(f"[DEBUG] 状态未发生有意义变化，跳过同步: {self.entity1_id}")
                return
            
            # 检查是否为重复状态
            is_duplicate = self._is_duplicate_state(self.entity1_id, new_state)
            _LOGGER.info(f"[DEBUG] 重复状态检测结果: {is_duplicate}")
            
            if is_duplicate:
                _LOGGER.info(f"[DEBUG] 检测到重复状态，跳过同步: {self.entity1_id}")
                return
            
            # 清理状态缓存（带类型验证）
            if self._validate_async_method(self._clean_state_cache, "_clean_state_cache"):
                await self._clean_state_cache()
            else:
                _LOGGER.error("跳过状态缓存清理，方法类型验证失败")
            
            # 智能同步判断和冷却时间检查
            sync_key = f"{self.entity1_id}->{self.entity2_id}"
            current_time = time.time()
            
            # 批量同步优化
            should_batch = self._should_batch_sync(self.entity1_id)
            _LOGGER.info(f"[DEBUG] 批量同步检测结果: {should_batch}")
            
            if should_batch:
                # 高频同步时增加冷却时间
                effective_cooldown = self._sync_cooldown * 1.5
                _LOGGER.info(f"[DEBUG] 检测到高频同步，启用批量优化: {sync_key}")
            else:
                effective_cooldown = self._sync_cooldown
            
            if sync_key in self._last_sync_times:
                time_since_last = current_time - self._last_sync_times[sync_key]
                _LOGGER.info(f"[DEBUG] 冷却时间检查: 距离上次={time_since_last:.2f}s, 阈值={effective_cooldown}s")
                if time_since_last < effective_cooldown:
                    _LOGGER.info(f"[DEBUG] 冷却时间未到，跳过同步: {time_since_last:.2f}s < {effective_cooldown}s")
                    return
            else:
                _LOGGER.info(f"[DEBUG] 首次同步，无冷却时间限制")
            
            # 记录同步时间
            self._last_sync_times[sync_key] = current_time
            
            _LOGGER.info(f"[DEBUG] 开始同步: {self.entity1_id} -> {self.entity2_id}")
            _LOGGER.debug(f"实体1状态变化: {self.entity1_id} -> {new_state.state}")
            await self._sync_to_entity(new_state, self.entity2_id)
        except Exception as err:
            _LOGGER.error(f"处理实体1状态变化事件时发生错误: {err}", exc_info=True)
    
    async def _handle_entity2_change(self, event: Event):
        """处理实体2的状态变化"""
        _LOGGER.info(f"[LISTENER] ===== 实体2监听器被触发 ===== {self.entity2_id}")
        _LOGGER.info(f"[LISTENER] 事件类型: {event.event_type}")
        _LOGGER.info(f"[LISTENER] 事件数据: {event.data}")
        _LOGGER.info(f"[DEBUG] 实体2状态变化事件触发: {self.entity2_id}")
        
        if self._sync_in_progress:
            _LOGGER.debug(f"[DEBUG] 同步正在进行中，跳过: {self.entity2_id}")
            return
            
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            
            _LOGGER.info(f"[DEBUG] 事件数据: new_state={new_state.state if new_state else None}, old_state={old_state.state if old_state else None}")
            
            if not new_state or not old_state:
                _LOGGER.warning(f"[DEBUG] 状态变化事件数据不完整，跳过同步: new_state={new_state}, old_state={old_state}")
                return
            
            # 检查是否为步进设备
            is_progressive = self._is_progressive_device(new_state.entity_id)
            _LOGGER.info(f"[DEBUG] 步进设备检测: {is_progressive}")
            
            # 步进设备只在触发时立即同步，不进行实时同步
            if is_progressive and self._has_progressive_change(old_state, new_state):
                _LOGGER.info(f"[DEBUG] 检测到步进设备变化，启用立即同步模式: {self.entity2_id}")
                await self._handle_progressive_sync(self.entity2_id, self.entity1_id, new_state, old_state)
                return
            
            # 使用精确的变化检测
            is_significant = self._is_significant_change(new_state, old_state, force_sync=False)
            _LOGGER.info(f"[DEBUG] 状态变化检测结果: {is_significant}, {old_state.state}->{new_state.state}")
            
            if not is_significant:
                _LOGGER.info(f"[DEBUG] 状态未发生有意义变化，跳过同步: {self.entity2_id}")
                return
            
            # 检查是否为重复状态
            is_duplicate = self._is_duplicate_state(self.entity2_id, new_state)
            _LOGGER.info(f"[DEBUG] 重复状态检测结果: {is_duplicate}")
            
            if is_duplicate:
                _LOGGER.info(f"[DEBUG] 检测到重复状态，跳过同步: {self.entity2_id}")
                return
            
            # 清理状态缓存（带类型验证）
            if self._validate_async_method(self._clean_state_cache, "_clean_state_cache"):
                await self._clean_state_cache()
            else:
                _LOGGER.error("跳过状态缓存清理，方法类型验证失败")
            
            # 智能同步判断和冷却时间检查
            sync_key = f"{self.entity2_id}->{self.entity1_id}"
            current_time = time.time()
            
            # 批量同步优化
            should_batch = self._should_batch_sync(self.entity2_id)
            _LOGGER.info(f"[DEBUG] 批量同步检测结果: {should_batch}")
            
            if should_batch:
                # 高频同步时增加冷却时间
                effective_cooldown = self._sync_cooldown * 1.5
                _LOGGER.info(f"[DEBUG] 检测到高频同步，启用批量优化: {sync_key}")
            else:
                effective_cooldown = self._sync_cooldown
            
            if sync_key in self._last_sync_times:
                time_since_last = current_time - self._last_sync_times[sync_key]
                _LOGGER.info(f"[DEBUG] 冷却时间检查: 距离上次={time_since_last:.2f}s, 阈值={effective_cooldown}s")
                if time_since_last < effective_cooldown:
                    _LOGGER.info(f"[DEBUG] 冷却时间未到，跳过同步: {time_since_last:.2f}s < {effective_cooldown}s")
                    return
            else:
                _LOGGER.info(f"[DEBUG] 首次同步，无冷却时间限制")
            
            # 记录同步时间
            self._last_sync_times[sync_key] = current_time
            
            _LOGGER.info(f"[DEBUG] 开始同步: {self.entity2_id} -> {self.entity1_id}")
            _LOGGER.debug(f"实体2状态变化: {self.entity2_id} -> {new_state.state}")
            await self._sync_to_entity(new_state, self.entity1_id)
        except Exception as err:
            _LOGGER.error(f"处理实体2状态变化事件时发生错误: {err}", exc_info=True)
    
    async def _immediate_sync(self, source_state: State, target_entity_id: str):
        """立即同步方法 - 专门用于步进设备，一次性同步所有属性，无延迟"""
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
            
            _LOGGER.debug(f"开始立即同步: {source_state.entity_id}({source_domain}) -> {target_entity_id}({target_domain})")
            
            service_data = {"entity_id": target_entity_id}
            
            if source_domain == "light":
                if source_state.state == "on":
                    # 立即同步灯光属性，使用智能颜色属性选择避免冲突
                    validated_attrs = self._validate_light_attributes(source_state.attributes)
                    if validated_attrs:
                        # 添加亮度属性
                        if "brightness" in validated_attrs:
                            service_data["brightness"] = validated_attrs["brightness"]
                        
                        # 智能颜色属性选择：优先级 hs_color > rgb_color > xy_color > color_temp
                        # 只选择一个颜色属性，避免冲突
                        if "hs_color" in validated_attrs:
                            service_data["hs_color"] = validated_attrs["hs_color"]
                        elif "rgb_color" in validated_attrs:
                            service_data["rgb_color"] = validated_attrs["rgb_color"]
                        elif "xy_color" in validated_attrs:
                            service_data["xy_color"] = validated_attrs["xy_color"]
                        elif "color_temp" in validated_attrs:
                            service_data["color_temp"] = validated_attrs["color_temp"]
                    
                    await self.hass.services.async_call("light", "turn_on", service_data)
                    _LOGGER.debug(f"灯光立即同步成功: {target_entity_id} = {service_data}")
                else:
                    await self.hass.services.async_call("light", "turn_off", service_data)
                    _LOGGER.debug(f"灯光关闭立即同步成功: {target_entity_id}")
            elif source_domain == "switch":
                service = "turn_on" if source_state.state == "on" else "turn_off"
                await self.hass.services.async_call("switch", service, service_data)
            elif source_domain == "cover":
                if source_state.state == "open":
                    await self.hass.services.async_call("cover", "open_cover", service_data)
                elif source_state.state == "closed":
                    await self.hass.services.async_call("cover", "close_cover", service_data)
                elif "position" in source_state.attributes:
                    service_data["position"] = source_state.attributes["position"]
                    await self.hass.services.async_call("cover", "set_cover_position", service_data)
            elif source_domain == "fan":
                if source_state.state == "on":
                    attrs = {k: v for k, v in source_state.attributes.items() 
                            if k in ["speed", "percentage", "preset_mode", "oscillating"]}
                    service_data.update(attrs)
                    await self.hass.services.async_call("fan", "turn_on", service_data)
                else:
                    await self.hass.services.async_call("fan", "turn_off", service_data)
            else:
                # 对于其他类型，使用基础同步
                is_on = source_state.state in ["on", "open", "playing", "cleaning", "heating", "cooling", "auto", "heat", "cool"]
                if target_domain in ["light", "switch", "fan", "humidifier", "input_boolean"]:
                    service = "turn_on" if is_on else "turn_off"
                    await self.hass.services.async_call(target_domain, service, service_data)
                    
            _LOGGER.info(f"立即同步完成: {source_state.entity_id} -> {target_entity_id}")
                
        except ServiceNotFound as err:
            _LOGGER.error(f"立即同步失败，服务不存在: {err}")
        except HomeAssistantError as err:
            _LOGGER.error(f"立即同步失败，Home Assistant错误: {err}")
        except Exception as err:
            _LOGGER.error(f"立即同步过程中发生未知错误: {err}", exc_info=True)
    
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
        
        # 注册调试服务
        if not hass.services.has_service(DOMAIN, "debug_sync_entity1_to_entity2"):
            async def handle_debug_sync_1_to_2(call):
                """处理调试同步服务：实体1到实体2"""
                try:
                    entity1 = call.data.get("entity1")
                    entity2 = call.data.get("entity2")
                    force = call.data.get("force", False)
                    
                    # 查找对应的协调器
                    target_coordinator = None
                    for coord in hass.data[DOMAIN].values():
                        if hasattr(coord, 'entity1_id') and hasattr(coord, 'entity2_id'):
                            if coord.entity1_id == entity1 and coord.entity2_id == entity2:
                                target_coordinator = coord
                                break
                    
                    if target_coordinator:
                        result = await target_coordinator.manual_sync_entity1_to_entity2(force)
                        _LOGGER.info(f"调试同步结果: {result}")
                    else:
                        _LOGGER.error(f"调试同步失败: 未找到对应的同步配置")
                except Exception as err:
                    _LOGGER.error(f"调试同步失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "debug_sync_entity1_to_entity2", handle_debug_sync_1_to_2)
            _LOGGER.info("已注册调试同步服务（实体1到实体2）")
        
        if not hass.services.has_service(DOMAIN, "debug_sync_entity2_to_entity1"):
            async def handle_debug_sync_2_to_1(call):
                """处理调试同步服务：实体2到实体1"""
                try:
                    entity1 = call.data.get("entity1")
                    entity2 = call.data.get("entity2")
                    force = call.data.get("force", False)
                    
                    # 查找对应的协调器
                    target_coordinator = None
                    for coord in hass.data[DOMAIN].values():
                        if hasattr(coord, 'entity1_id') and hasattr(coord, 'entity2_id'):
                            if coord.entity1_id == entity1 and coord.entity2_id == entity2:
                                target_coordinator = coord
                                break
                    
                    if target_coordinator:
                        result = await target_coordinator.manual_sync_entity2_to_entity1(force)
                        _LOGGER.info(f"调试同步结果: {result}")
                    else:
                        _LOGGER.error(f"调试同步失败: 未找到对应的同步配置")
                except Exception as err:
                    _LOGGER.error(f"调试同步失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "debug_sync_entity2_to_entity1", handle_debug_sync_2_to_1)
            _LOGGER.info("已注册调试同步服务（实体2到实体1）")
        
        if not hass.services.has_service(DOMAIN, "get_sync_status"):
            async def handle_get_sync_status(call):
                """处理获取同步状态服务"""
                try:
                    entity1 = call.data.get("entity1")
                    entity2 = call.data.get("entity2")
                    
                    # 查找对应的协调器
                    target_coordinator = None
                    for coord in hass.data[DOMAIN].values():
                        if hasattr(coord, 'entity1_id') and hasattr(coord, 'entity2_id'):
                            if coord.entity1_id == entity1 and coord.entity2_id == entity2:
                                target_coordinator = coord
                                break
                    
                    if target_coordinator:
                        status = await target_coordinator.get_sync_status()
                        _LOGGER.info(f"同步状态查询完成")
                    else:
                        _LOGGER.error(f"获取同步状态失败: 未找到对应的同步配置")
                except Exception as err:
                    _LOGGER.error(f"获取同步状态失败: {err}", exc_info=True)
            
            hass.services.async_register(DOMAIN, "get_sync_status", handle_get_sync_status)
            _LOGGER.info("已注册获取同步状态服务")
        
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
            hass.services.async_remove(DOMAIN, "debug_sync_entity1_to_entity2")
            hass.services.async_remove(DOMAIN, "debug_sync_entity2_to_entity1")
            hass.services.async_remove(DOMAIN, "get_sync_status")
            _LOGGER.info("已移除双向同步服务和调试服务")
        
        return True
        
    except Exception as err:
        _LOGGER.error(f"卸载集成失败: {err}", exc_info=True)
        return False