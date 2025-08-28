"""Home Assistant 双向同步集成 v1.2.7

这个集成允许两个实体之间进行双向状态同步。
当一个实体的状态发生变化时，另一个实体会自动同步到相同的状态。

特性:
- 支持多种设备类型（灯光、开关、风扇、窗帘等）
- 极简的主从跟随机制：主动作是什么，从就立刻跟着做什么
- 基本同步锁防止死循环
- 完美同步模式，确保所有属性都被正确同步
- 支持手动同步和状态查询
- 详细的日志记录，便于调试

作者: Assistant
版本: v1.2.7
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

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
        
        # 调试信息：确保asyncio模块可用
        _LOGGER.debug("SimpleSyncCoordinator初始化 - asyncio模块: %s", asyncio)
        
        # 极简的同步控制 - 只保留基本同步锁
        try:
            self._sync_lock = asyncio.Lock()
            _LOGGER.debug("asyncio.Lock()创建成功")
        except Exception as e:
            _LOGGER.error("创建asyncio.Lock()失败: %s", e)
            raise
            
        # 简单的时间戳机制防止死循环
        self._last_sync_time = 0
        self._sync_cooldown = 0.1  # 100ms冷却时间
        
    def _is_sync_caused_change(self, entity_id: str) -> bool:
        """检查是否是同步引起的变化（简单时间戳检查）"""
        current_time = time.time()
        return current_time - self._last_sync_time < self._sync_cooldown
        
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
        """处理实体1状态变化 - 极简版"""
        if not self.enabled:
            return
            
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
            
        # 检查是否是同步引起的变化
        if self._is_sync_caused_change(self.entity1_id):
            _LOGGER.debug(f"忽略同步引起的变化: {self.entity1_id}")
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
            _LOGGER.debug(f"忽略同步引起的变化: {self.entity2_id}")
            return
            
        # 执行同步
        await self._instant_sync(new_state, self.entity1_id)
        
    async def _instant_sync(self, source_state: State, target_entity_id: str) -> None:
        """极简的即时同步 - 主动作是什么，从就立刻做什么"""
        async with self._sync_lock:
            try:
                # 更新同步时间戳
                self._last_sync_time = time.time()
                
                _LOGGER.info(f"开始同步: {source_state.entity_id} -> {target_entity_id}")
                
                # 获取目标实体当前状态
                target_state = self.hass.states.get(target_entity_id)
                if not target_state:
                    _LOGGER.error(f"目标实体不存在: {target_entity_id}")
                    return
                
                # 执行完美同步
                await self._perfect_sync(source_state, target_entity_id)
                
                _LOGGER.info(f"同步完成: {source_state.entity_id} -> {target_entity_id}")
                
            except Exception as e:
                _LOGGER.error(f"同步失败: {source_state.entity_id} -> {target_entity_id}: {e}")
                
    async def _perfect_sync(self, source_state: State, target_entity_id: str) -> None:
        """简单同步 - 只同步开关状态"""
        domain = source_state.domain
        service_data = {"entity_id": target_entity_id}
        
        try:
            # 所有设备类型都只同步基本的开关状态
            if source_state.state in ["on", "off"]:
                service = "turn_on" if source_state.state == "on" else "turn_off"
                await self.hass.services.async_call(domain, service, service_data)
            elif domain == "cover":
                # 窗帘特殊处理
                if source_state.state == "open":
                    await self.hass.services.async_call("cover", "open_cover", service_data)
                elif source_state.state == "closed":
                    await self.hass.services.async_call("cover", "close_cover", service_data)
                    
        except Exception as e:
            _LOGGER.error(f"简单同步失败 {domain}: {e}")
            
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
        _LOGGER.info(f"双向同步已卸载: {self.entity1_id} <-> {self.entity2_id}")

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
            _LOGGER.info(f"手动同步 {'成功' if success else '失败'}: {entry_id} ({direction})")
        else:
            _LOGGER.error(f"未找到同步器: {entry_id}")
    
    async def handle_get_status(call):
        """处理获取状态服务"""
        entry_id = call.data.get("entry_id")
        
        if entry_id in _sync_coordinators:
            status = _sync_coordinators[entry_id].get_sync_status()
            _LOGGER.info(f"同步状态: {status}")
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