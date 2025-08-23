# 双向同步测试指南

## 概述
本指南帮助您测试和调试 Home Assistant 双向同步集成，特别是针对灯光设备 `light.lemesh_cn_1000421585_wy0c09_s_2_2` 和 `light.lemesh_cn_1000421585_wy0c09_s_2` 的同步功能。

## 测试前准备

### 1. 重启 Home Assistant
更新代码后，需要重启 Home Assistant 以加载最新的集成代码。

### 2. 检查集成状态
在 Home Assistant 的「配置」->「集成」中确认双向同步集成已正确加载。

## 测试方法

### 方法1：查看日志

1. 打开 Home Assistant 日志（「配置」->「日志」）
2. 寻找包含以下关键词的日志条目：
   - `双向同步集成设置完成`
   - `事件监听器注册成功`
   - `监听器触发确认`
   - `状态变化检测`
   - `同步开始`

### 方法2：手动切换灯光状态

1. 在 Home Assistant 界面中手动开关任一灯光
2. 观察另一个灯光是否自动同步状态
3. 检查日志中是否有同步相关的调试信息

### 方法3：使用调试服务

#### 3.1 手动同步服务

在「开发者工具」->「服务」中调用以下服务：

**从实体1同步到实体2：**
```yaml
service: ha_two_way_sync.debug_sync_entity1_to_entity2
data:
  entity1: light.lemesh_cn_1000421585_wy0c09_s_2_2
  entity2: light.lemesh_cn_1000421585_wy0c09_s_2
  force: true
```

**从实体2同步到实体1：**
```yaml
service: ha_two_way_sync.debug_sync_entity2_to_entity1
data:
  entity1: light.lemesh_cn_1000421585_wy0c09_s_2_2
  entity2: light.lemesh_cn_1000421585_wy0c09_s_2
  force: true
```

#### 3.2 获取同步状态

```yaml
service: ha_two_way_sync.get_sync_status
data:
  entity1: light.lemesh_cn_1000421585_wy0c09_s_2_2
  entity2: light.lemesh_cn_1000421585_wy0c09_s_2
```

#### 3.3 原有服务

**手动同步：**
```yaml
service: ha_two_way_sync.manual_sync
data:
  entity1: light.lemesh_cn_1000421585_wy0c09_s_2_2
  entity2: light.lemesh_cn_1000421585_wy0c09_s_2
```

**切换同步状态：**
```yaml
service: ha_two_way_sync.toggle_sync
data:
  entity1: light.lemesh_cn_1000421585_wy0c09_s_2_2
  entity2: light.lemesh_cn_1000421585_wy0c09_s_2
```

## 调试信息说明

### 正常工作的日志示例

```
[INFO] 双向同步集成设置完成: light.lemesh_cn_1000421585_wy0c09_s_2_2 <-> light.lemesh_cn_1000421585_wy0c09_s_2
[INFO] 事件监听器注册成功，监听实体: light.lemesh_cn_1000421585_wy0c09_s_2_2
[INFO] 事件监听器注册成功，监听实体: light.lemesh_cn_1000421585_wy0c09_s_2
[INFO] 监听器触发确认 - 实体1事件处理器被调用
[DEBUG] 状态变化检测: 检测到有意义的状态变化
[INFO] 同步开始: light.lemesh_cn_1000421585_wy0c09_s_2_2 -> light.lemesh_cn_1000421585_wy0c09_s_2
```

### 常见问题排查

#### 1. 没有同步
- 检查是否有「监听器触发确认」日志
- 检查是否有「状态变化检测」相关日志
- 尝试使用 `force: true` 参数的调试服务

#### 2. 同步延迟
- 检查「冷却时间检查」日志
- 查看「批量同步检测」结果

#### 3. 同步错误
- 查看错误日志中的详细错误信息
- 检查实体是否存在且可访问

## 版本信息

当前版本：v1.0.11
更新内容：
- 增强调试日志输出
- 优化状态变化检测逻辑
- 添加手动触发同步的调试功能
- 验证事件监听器注册和触发状态

## 支持

如果遇到问题，请：
1. 收集完整的日志信息
2. 记录具体的操作步骤
3. 提供实体的状态信息
4. 在 GitHub 仓库中提交 Issue