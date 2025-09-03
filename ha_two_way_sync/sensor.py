"""Home Assistant 双向同步集成传感器组件 v2.1.3

提供同步状态监控和管理界面支持。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME

from . import DOMAIN, _sync_coordinators

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器实体"""
    coordinator = _sync_coordinators.get(config_entry.entry_id)
    if coordinator:
        # 为每个同步配置创建状态传感器
        sensors = [
            TwoWaySyncStatusSensor(coordinator, config_entry),
            TwoWaySyncStatsSensor(coordinator, config_entry),
        ]
        async_add_entities(sensors)
        _LOGGER.debug(f"已添加传感器实体: {config_entry.title}")

class TwoWaySyncStatusSensor(SensorEntity):
    """双向同步状态传感器"""
    
    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """初始化状态传感器"""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"双向同步状态 {config_entry.title}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_status"
        self._attr_device_class = None
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
    def native_value(self) -> str:
        """返回传感器状态"""
        if not self._coordinator:
            return "未知"
            
        if self._coordinator.enabled:
            return "运行中"
        else:
            return "已停用"
            
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外状态属性"""
        if not self._coordinator:
            return {}
            
        status = self._coordinator.get_sync_status()
        return {
            "entity1_id": status["entity1"]["id"],
            "entity1_state": status["entity1"]["state"],
            "entity2_id": status["entity2"]["id"],
            "entity2_state": status["entity2"]["state"],
            "last_sync_time": status["last_sync_time"],
            "enabled": status["enabled"],
            "config_entry_id": self._config_entry.entry_id,
        }
        
class TwoWaySyncStatsSensor(SensorEntity):
    """双向同步统计传感器"""
    
    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """初始化统计传感器"""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"双向同步统计 {config_entry.title}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_stats"
        self._attr_device_class = None
        self._attr_icon = "mdi:chart-line"
        self._attr_native_unit_of_measurement = "次"
        
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
    def native_value(self) -> int:
        """返回总同步次数"""
        if not self._coordinator:
            return 0
            
        return self._coordinator._sync_stats.get("total_syncs", 0)
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回详细统计信息"""
        if not self._coordinator:
            return {}
            
        stats = self._coordinator._sync_stats
        success_rate = 0
        if stats["total_syncs"] > 0:
            success_rate = (stats["successful_syncs"] / stats["total_syncs"]) * 100
            
        return {
            "total_syncs": stats["total_syncs"],
            "successful_syncs": stats["successful_syncs"],
            "failed_syncs": stats["failed_syncs"],
            "success_rate": round(success_rate, 1),
            "avg_sync_time": round(stats["avg_sync_time"], 3),
            "last_sync_duration": round(stats["last_sync_duration"], 3),
            "config_entry_id": self._config_entry.entry_id,
        }