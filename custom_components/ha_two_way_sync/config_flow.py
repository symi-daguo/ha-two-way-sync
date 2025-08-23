"""Home Assistant 双向同步集成配置流程"""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_two_way_sync"


class TwoWaySyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """双向同步配置流程"""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """处理用户配置步骤"""
        errors = {}
        
        if user_input is not None:
            # 验证配置
            entity1 = user_input.get("entity1")
            entity2 = user_input.get("entity2")
            
            if entity1 == entity2:
                errors["base"] = "same_entity"
            elif not entity1 or not entity2:
                errors["base"] = "missing_entity"
            else:
                # 检查实体是否存在
                if not self.hass.states.get(entity1):
                    errors["entity1"] = "entity_not_found"
                if not self.hass.states.get(entity2):
                    errors["entity2"] = "entity_not_found"
                
                if not errors:
                    # 创建条目标题
                    title = f"{entity1} <-> {entity2}"
                    
                    # 允许多个配置条目，不检查重复配置
                    # 用户可能需要为不同的设备对创建多个同步配置
                    
                    return self.async_create_entry(
                        title=title,
                        data={
                            "entity1": entity1,
                            "entity2": entity2,
                            "enabled": user_input.get("enabled", True),
                            "sync_mode": user_input.get("sync_mode", "perfect"),
                            "progressive_sync_mode": user_input.get("progressive_sync_mode", "smart"),
                            "action_completion_timeout": user_input.get("action_completion_timeout", 3.0),
                        }
                    )
        
        # 构建配置表单
        data_schema = vol.Schema({
            vol.Required("entity1"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=[
                        "light", "switch", "cover", "fan", "climate", "lock", 
                        "binary_sensor", "sensor", "scene", "script", "automation",
                        "humidifier", "water_heater", "vacuum", "media_player",
                        "input_boolean", "input_select", "input_number", "input_text"
                    ]
                )
            ),
            vol.Required("entity2"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=[
                        "light", "switch", "cover", "fan", "climate", "lock", 
                        "binary_sensor", "sensor", "scene", "script", "automation",
                        "humidifier", "water_heater", "vacuum", "media_player",
                        "input_boolean", "input_select", "input_number", "input_text"
                    ]
                )
            ),
            vol.Optional("enabled", default=True): selector.BooleanSelector(),
            vol.Optional("sync_mode", default="perfect"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "perfect", "label": "完美同步（同步所有属性）"},
                        {"value": "basic", "label": "基础同步（仅开关状态）"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("progressive_sync_mode", default="smart"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "smart", "label": "智能模式（自动检测步进设备）"},
                        {"value": "realtime", "label": "实时模式（传统实时同步）"},
                        {"value": "master_slave", "label": "主从模式（强制主从同步）"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("action_completion_timeout", default=3.0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1.0,
                    max=10.0,
                    step=0.5,
                    unit_of_measurement="秒",
                    mode=selector.NumberSelectorMode.BOX
                )
            ),
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "entity1_description": "选择第一个要同步的实体",
                "entity2_description": "选择第二个要同步的实体",
            }
        )
    
    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """获取选项流程"""
        return TwoWaySyncOptionsFlow(config_entry)


class TwoWaySyncOptionsFlow(config_entries.OptionsFlow):
    """双向同步选项流程"""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流程"""
        super().__init__(config_entry)
    
    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """管理选项"""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        data_schema = vol.Schema({
            vol.Optional(
                "enabled",
                default=self.config_entry.options.get(
                    "enabled", self.config_entry.data.get("enabled", True)
                )
            ): selector.BooleanSelector(),
            vol.Optional(
                "sync_mode",
                default=self.config_entry.options.get(
                    "sync_mode", self.config_entry.data.get("sync_mode", "perfect")
                )
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "perfect", "label": "完美同步（同步所有属性）"},
                        {"value": "basic", "label": "基础同步（仅开关状态）"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(
                "progressive_sync_mode",
                default=self.config_entry.options.get(
                    "progressive_sync_mode", self.config_entry.data.get("progressive_sync_mode", "smart")
                )
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "smart", "label": "智能模式（自动检测步进设备）"},
                        {"value": "realtime", "label": "实时模式（传统实时同步）"},
                        {"value": "master_slave", "label": "主从模式（强制主从同步）"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(
                "action_completion_timeout",
                default=self.config_entry.options.get(
                    "action_completion_timeout", self.config_entry.data.get("action_completion_timeout", 3.0)
                )
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1.0,
                    max=10.0,
                    step=0.5,
                    unit_of_measurement="秒",
                    mode=selector.NumberSelectorMode.BOX
                )
            ),
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )