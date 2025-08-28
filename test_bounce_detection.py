#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试抖动检测功能
"""

import time
import logging
from unittest.mock import Mock

# 设置日志
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

class MockTwoWaySync:
    """模拟TwoWaySync类用于测试"""
    
    def __init__(self):
        self._state_history = {}
    
    def _record_state_change(self, entity_id, state_obj):
        """记录状态变化历史"""
        if entity_id not in self._state_history:
            self._state_history[entity_id] = []
        
        current_time = time.time()
        attributes = getattr(state_obj, 'attributes', {}) or {}
        
        self._state_history[entity_id].append([
            current_time,
            state_obj.state,
            attributes
        ])
        
        # 只保留最近10个记录
        if len(self._state_history[entity_id]) > 10:
            self._state_history[entity_id] = self._state_history[entity_id][-10:]
    
    def _is_bouncing_state(self, entity_id, state_obj=None):
        """检查是否处于抖动状态"""
        if entity_id not in self._state_history:
            return False
            
        history = self._state_history[entity_id]
        if len(history) < 6:  # 需要至少6个历史记录才判断抖动
            _LOGGER.debug(f"抖动检测 - {entity_id}: 历史记录不足 ({len(history)}/6)")
            return False
            
        current_time = time.time()
        recent_changes = [h for h in history if current_time - h[0] <= 5.0]  # 5秒内的变化
        
        if len(recent_changes) >= 6:
            # 提取状态值和关键属性
            states = [h[1] for h in recent_changes]
            attributes_list = [h[2] for h in recent_changes]
            
            # 检查状态值的变化
            unique_states = set(states)
            
            # 只有当状态值在至少2个不同值之间快速切换时才可能是抖动
            if len(unique_states) >= 2:
                # 检查是否是真正的来回切换模式（状态值必须不同）
                state_changes = 0
                for i in range(1, len(states)):
                    if states[i] != states[i-1]:
                        state_changes += 1
                        
                # 只有当状态值变化次数超过4次时才认为是抖动
                if state_changes >= 4:
                    # 进一步检查：如果是灯光实体，还要检查关键属性是否也在快速变化
                    if entity_id.startswith('light.'):
                        # 对于灯光，检查亮度、色温等关键属性的变化
                        brightness_changes = 0
                        color_temp_changes = 0
                        
                        for i in range(1, len(attributes_list)):
                            prev_attrs = attributes_list[i-1] or {}
                            curr_attrs = attributes_list[i] or {}
                            
                            # 检查亮度变化
                            prev_brightness = prev_attrs.get('brightness', 0)
                            curr_brightness = curr_attrs.get('brightness', 0)
                            if abs(prev_brightness - curr_brightness) > 10:  # 亮度变化超过10才算有意义变化
                                brightness_changes += 1
                                
                            # 检查色温变化
                            prev_color_temp = prev_attrs.get('color_temp', 0)
                            curr_color_temp = curr_attrs.get('color_temp', 0)
                            if abs(prev_color_temp - curr_color_temp) > 20:  # 色温变化超过20才算有意义变化
                                color_temp_changes += 1
                        
                        # 只有状态值和关键属性都在快速变化时才认为是真正的抖动
                        if brightness_changes >= 3 or color_temp_changes >= 3:
                            _LOGGER.warning(f"检测到真正的抖动状态: {entity_id}, 状态变化: {state_changes}, 亮度变化: {brightness_changes}, 色温变化: {color_temp_changes}")
                            _LOGGER.debug(f"抖动状态详情: {entity_id}, 最近状态: {states[-6:]}")
                            return True
                        else:
                            _LOGGER.debug(f"状态值变化但属性变化不大，不认为是抖动: {entity_id}, 状态变化: {state_changes}, 亮度变化: {brightness_changes}, 色温变化: {color_temp_changes}")
                            return False
                    else:
                        # 对于非灯光实体，只检查状态值变化
                        _LOGGER.warning(f"检测到抖动状态: {entity_id}, 状态变化: {state_changes}")
                        _LOGGER.debug(f"抖动状态详情: {entity_id}, 最近状态: {states[-6:]}")
                        return True
            else:
                # 状态值相同，不是抖动（比如亮度调节导致的多次'on'状态）
                _LOGGER.debug(f"状态值相同，不认为是抖动: {entity_id}, 状态: {unique_states}")
                return False
                
        return False

def create_mock_state(state, brightness=None, color_temp=None):
    """创建模拟状态对象"""
    mock_state = Mock()
    mock_state.state = state
    mock_state.attributes = {}
    
    if brightness is not None:
        mock_state.attributes['brightness'] = brightness
    if color_temp is not None:
        mock_state.attributes['color_temp'] = color_temp
        
    return mock_state

def test_normal_brightness_adjustment():
    """测试正常亮度调节不应被误判为抖动"""
    print("\n=== 测试正常亮度调节 ===")
    sync = MockTwoWaySync()
    entity_id = "light.test_light"
    
    # 模拟正常的亮度调节：状态都是'on'，但亮度在变化
    states_and_brightness = [
        ('on', 100),
        ('on', 120),
        ('on', 140),
        ('on', 160),
        ('on', 180),
        ('on', 200),
        ('on', 220)
    ]
    
    for state, brightness in states_and_brightness:
        mock_state = create_mock_state(state, brightness=brightness)
        sync._record_state_change(entity_id, mock_state)
        time.sleep(0.1)  # 短暂延迟
        
        is_bouncing = sync._is_bouncing_state(entity_id, mock_state)
        print(f"状态: {state}, 亮度: {brightness}, 抖动检测: {is_bouncing}")
    
    # 最终检查
    final_result = sync._is_bouncing_state(entity_id)
    print(f"最终抖动检测结果: {final_result}")
    assert not final_result, "正常亮度调节不应被误判为抖动"
    print("✓ 测试通过：正常亮度调节未被误判为抖动")

def test_real_bouncing_state():
    """测试真正的抖动状态应被正确检测"""
    print("\n=== 测试真正的抖动状态 ===")
    sync = MockTwoWaySync()
    entity_id = "light.test_light"
    
    # 模拟真正的抖动：状态在on/off之间快速切换，且亮度也在变化
    states_and_attrs = [
        ('on', 100, 3000),
        ('off', 0, 0),
        ('on', 120, 3200),
        ('off', 0, 0),
        ('on', 140, 3400),
        ('off', 0, 0),
        ('on', 160, 3600)
    ]
    
    for state, brightness, color_temp in states_and_attrs:
        mock_state = create_mock_state(state, brightness=brightness, color_temp=color_temp)
        sync._record_state_change(entity_id, mock_state)
        time.sleep(0.1)  # 短暂延迟
        
        is_bouncing = sync._is_bouncing_state(entity_id, mock_state)
        print(f"状态: {state}, 亮度: {brightness}, 色温: {color_temp}, 抖动检测: {is_bouncing}")
    
    # 最终检查
    final_result = sync._is_bouncing_state(entity_id)
    print(f"最终抖动检测结果: {final_result}")
    assert final_result, "真正的抖动状态应被正确检测"
    print("✓ 测试通过：真正的抖动状态被正确检测")

def test_color_temp_adjustment():
    """测试色温调节不应被误判为抖动"""
    print("\n=== 测试色温调节 ===")
    sync = MockTwoWaySync()
    entity_id = "light.test_light"
    
    # 模拟正常的色温调节：状态都是'on'，色温在变化但变化不大
    states_and_color_temp = [
        ('on', 3000),
        ('on', 3010),
        ('on', 3020),
        ('on', 3030),
        ('on', 3040),
        ('on', 3050),
        ('on', 3060)
    ]
    
    for state, color_temp in states_and_color_temp:
        mock_state = create_mock_state(state, brightness=200, color_temp=color_temp)
        sync._record_state_change(entity_id, mock_state)
        time.sleep(0.1)  # 短暂延迟
        
        is_bouncing = sync._is_bouncing_state(entity_id, mock_state)
        print(f"状态: {state}, 色温: {color_temp}, 抖动检测: {is_bouncing}")
    
    # 最终检查
    final_result = sync._is_bouncing_state(entity_id)
    print(f"最终抖动检测结果: {final_result}")
    assert not final_result, "正常色温调节不应被误判为抖动"
    print("✓ 测试通过：正常色温调节未被误判为抖动")

if __name__ == "__main__":
    print("开始测试抖动检测功能...")
    
    try:
        test_normal_brightness_adjustment()
        test_real_bouncing_state()
        test_color_temp_adjustment()
        
        print("\n🎉 所有测试通过！抖动检测功能工作正常。")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except Exception as e:
        print(f"\n💥 测试出错: {e}")
        import traceback
        traceback.print_exc()