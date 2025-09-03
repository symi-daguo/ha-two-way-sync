"""Home Assistant 双向同步集成开关组件 v2.1.3

提供同步开关控制功能。
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN, _sync_coordinators

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置开关实体"""
    coordinator = _sync_coordinators.get(config_entry.entry_id)
    if coordinator:
        # 为每个同步配置创建控制开关
        switches = [
            TwoWaySyncSwitch(coordinator, config_entry),
        ]
        async_add_entities(switches)
        _LOGGER.debug(f"已添加开关实体: {config_entry.title}")

class TwoWaySyncSwitch(SwitchEntity):
    """双向同步控制开关"""
    
    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """初始化控制开关"""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"双向同步开关 {config_entry.title}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_switch"
        self._attr_icon = "mdi:sync"
        
    @property
    def device_info(self) -> DeviceInfo:
        """返回设备信息"""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=f"双向同步 {self._config_entry.title}",
            manufacturer="HA Two Way Sync",
            model="同步协调器",
            sw_version="2.1.3",
        )
        
    @property
    def is_on(self) -> bool:
        """返回开关状态"""
        if not self._coordinator:
            return False
        return self._coordinator.enabled
        
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """返回额外状态属性"""
        if not self._coordinator:
            return {}
            
        status = self._coordinator.get_sync_status()
        return {
            "entity1_id": status["entity1"]["id"],
            "entity1_state": status["entity1"]["state"],
            "entity2_id": status["entity2"]["id"],
            "entity2_state": status["entity2"]["state"],
            "config_entry_id": self._config_entry.entry_id,
        }
        
    async def async_turn_on(self, **kwargs: Any) -> None:
        """启用同步"""
        if self._coordinator:
            self._coordinator.enabled = True
            await self._coordinator.async_setup()
            self.async_write_ha_state()
            _LOGGER.info(f"已启用双向同步: {self._config_entry.title}")
            
    async def async_turn_off(self, **kwargs: Any) -> None:
        """禁用同步"""
        if self._coordinator:
            self._coordinator.enabled = False
            # 清理监听器但不完全卸载
            for unsubscribe in self._coordinator._unsubscribe_listeners:
                unsubscribe()
            self._coordinator._unsubscribe_listeners.clear()
            self.async_write_ha_state()
            _LOGGER.info(f"已禁用双向同步: {self._config_entry.title}")
            
    @property
    def available(self) -> bool:
        """返回实体可用性"""
        return self._coordinator is not None