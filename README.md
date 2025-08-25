# Home Assistant 双向同步集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/symi-daguo/ha-two-way-sync.svg)](https://github.com/symi-daguo/ha-two-way-sync/releases)
[![License](https://img.shields.io/github/license/symi-daguo/ha-two-way-sync.svg)](LICENSE)

一个简单易用的 Home Assistant 自定义集成，用于实现两个实体之间的双向状态同步。

## 🚨 v1.2.2 紧急修复（2025-01-25）

### 🔧 关键修复
- **🔧 缓存修复**: 强制更新版本号解决 Home Assistant 缓存导致的 asyncio 导入问题
- **🐛 调试增强**: 添加详细的调试信息帮助诊断 asyncio.Lock() 创建问题
- **✅ 导入优化**: 进一步确保 asyncio 模块导入的可靠性
- **📝 错误处理**: 在 SimpleSyncCoordinator 初始化时添加异常处理

### 📋 技术细节
- 强制更新版本号解决缓存问题
- 添加详细的调试日志
- 优化 asyncio 模块导入机制

## 🚨 v1.2.1 紧急修复（2025-01-25）

### 🔧 关键修复
- **🐛 修复导入错误**: 修复 `NameError: name 'asyncio' is not defined` 错误
- **📦 添加缺失导入**: 在 `__init__.py` 中添加 `import asyncio` 和 `Callable` 类型导入
- **✅ 确保兼容性**: 确保所有必要的模块都已正确导入
- **🚀 立即可用**: 修复后集成可以正常设置和运行

### 📋 技术细节
- 在文件顶部添加了 `import asyncio` 导入语句
- 添加了 `Callable` 类型导入以支持类型注解
- 通过语法检查验证修复有效性

## 🎉 v1.2.0 重大修复（2025-01-25）

### 🚨 关键问题修复
- **🔄 解决循环同步**: 彻底修复调光功能反复开关的严重问题
- **🔒 同步锁机制**: 实现强大的同步锁，防止循环同步导致的无限循环
- **⏱️ 优化防重复**: 将防重复间隔从50ms优化到2秒，有效阻止快速循环
- **📊 状态缓存**: 添加状态缓存机制，避免重复同步相同状态
- **🎯 方向锁定**: 实现同步方向锁定，防止双向同步冲突

### 🛠️ 技术改进
- 添加同步进行标志(_sync_in_progress)防止并发同步
- 实现状态等效性检测，忽略由同步引起的微小变化
- 优化状态变化检测逻辑，提高同步精确度
- 增强错误处理和详细日志记录
- 改进手动同步方法的安全性

### 📈 稳定性提升
- 完全消除调光反复开关问题
- 大幅提升同步系统稳定性
- 减少不必要的同步操作
- 提供更好的调试信息

## 📋 v1.1.0 更新记录（2025-01-25）

### ✨ 重要改进
- **🚀 解决回弹问题**: 彻底解决灯光调亮度、调色温时的回弹现象
- **⚡ 实时同步**: 重构同步逻辑，实现真正的实时同步，无延迟
- **🎯 立即响应**: 开关操作100%同步执行，步进操作（调光、调色温）立即同步
- **🔧 简化架构**: 移除复杂的状态检测和等待机制，提升同步响应速度
- **💡 智能防重复**: 采用50ms防重复机制，既防止回弹又保证实时性

### 🛠️ 技术优化
- 一次性同步所有属性，避免分步同步导致的状态不一致
- 智能颜色属性选择，避免颜色属性冲突
- 移除复杂的批量优化和冷却机制
- 简化事件处理逻辑，提升性能

### 📈 用户体验提升
- 灯光调节过程中的每个变化都能实时同步
- 快速连续操作不再被跳过
- 消除调光调色温时的"卡顿"感
- 更稳定的同步表现

## ✨ 功能特性

- 🔄 **双向同步**: 支持两个实体之间的实时双向状态同步
- 🎯 **智能同步**: 相同类型实体支持完美同步（状态+属性），不同类型实体支持基础同步（开关状态）
- 🛡️ **防循环**: 内置防循环同步机制，确保系统稳定
- 🔧 **易配置**: 通过 Home Assistant UI 界面轻松配置
- 📱 **广泛支持**: 支持灯光、开关、窗帘、风扇、空调、加湿器、热水器、扫地机、媒体播放器、场景、脚本等多种设备类型
- 🎛️ **服务支持**: 提供手动同步和切换同步状态的服务

## 📋 系统要求

- Home Assistant 2024.1.0 或更高版本
- Python 3.12 或更高版本（推荐）
- HACS（可选，用于自动更新）

## 🚀 安装方法

### 方法一：通过 HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中点击 "集成"
3. 点击右上角的三个点，选择 "自定义存储库"
4. 添加存储库 URL: `https://github.com/symi-daguo/ha-two-way-sync`
5. 类别选择 "集成"
6. 搜索并安装 "Home Assistant 双向同步集成"
7. 重启 Home Assistant

### 方法二：手动安装

1. 下载最新版本的代码
2. 解压后将整个 `custom_components/ha_two_way_sync` 文件夹复制到你的 Home Assistant 配置目录下的 `custom_components` 文件夹中
3. 确保目录结构如下：
   ```
   config/
   └── custom_components/
       └── ha_two_way_sync/
           ├── __init__.py
           ├── config_flow.py
           ├── manifest.json
           ├── services.yaml
           └── translations/
               ├── en.json
               └── zh.json
   ```
4. 重启 Home Assistant

## ⚙️ 配置说明

### 添加集成

1. 在 Home Assistant 的 "设置" > "设备与服务" 中点击 "添加集成"
2. 搜索并选择 "Home Assistant 双向同步集成"
3. 按照向导完成配置：
   - 选择要同步的第一个实体
   - 选择要同步的第二个实体
   - 完成配置

### 支持的设备类型

| 设备类型 | 域名 | 同步类型 | 说明 |
|---------|------|----------|------|
| 灯光 | `light` | 完美同步 | 同步状态、亮度、颜色等所有属性 |
| 开关 | `switch` | 完美同步 | 同步开关状态 |
| 窗帘 | `cover` | 完美同步 | 同步开关状态和位置 |
| 风扇 | `fan` | 完美同步 | 同步状态、速度等属性 |
| 空调 | `climate` | 完美同步 | 同步温度、模式等属性 |
| 加湿器 | `humidifier` | 完美同步 | 同步状态、湿度等属性 |
| 热水器 | `water_heater` | 完美同步 | 同步状态、温度等属性 |
| 扫地机 | `vacuum` | 完美同步 | 同步状态、模式等属性 |
| 媒体播放器 | `media_player` | 完美同步 | 同步播放状态、音量等属性 |
| 场景 | `scene` | 完美同步 | 触发场景 |
| 脚本 | `script` | 完美同步 | 执行脚本 |
| 自动化 | `automation` | 基础同步 | 开关状态同步 |
| 输入布尔 | `input_boolean` | 完美同步 | 同步开关状态 |
| 输入选择 | `input_select` | 完美同步 | 同步选项值 |
| 输入数字 | `input_number` | 完美同步 | 同步数值 |
| 输入文本 | `input_text` | 完美同步 | 同步文本内容 |
| 二进制传感器 | `binary_sensor` | 基础同步 | 只读，不支持同步 |
| 传感器 | `sensor` | 基础同步 | 只读，不支持同步 |
| 锁 | `lock` | 基础同步 | 开关状态同步 |

## 💡 使用示例

### 示例一：客厅主灯与辅助灯同步
- **实体1**: `light.living_room_main` (客厅主灯)
- **实体2**: `light.living_room_auxiliary` (客厅辅助灯)
- **效果**: 两个灯光的开关状态、亮度、颜色完全同步

### 示例二：卧室开关与床头灯同步
- **实体1**: `switch.bedroom_wall_switch` (墙壁开关)
- **实体2**: `light.bedside_lamp` (床头灯)
- **效果**: 墙壁开关控制床头灯，床头灯状态也会反映到开关上

### 示例三：窗帘与智能开关同步
- **实体1**: `cover.living_room_curtain` (客厅窗帘)
- **实体2**: `switch.curtain_control` (窗帘控制开关)
- **效果**: 开关控制窗帘开合，窗帘状态同步到开关

## 🛠️ 可用服务

集成提供以下服务供自动化使用：

### `ha_two_way_sync.manual_sync`
手动触发同步操作

```yaml
service: ha_two_way_sync.manual_sync
data:
  config_entry_id: "your_config_entry_id"
```

### `ha_two_way_sync.toggle_sync`
切换同步状态（启用/禁用）

```yaml
service: ha_two_way_sync.toggle_sync
data:
  config_entry_id: "your_config_entry_id"
```

## 🔧 故障排除

### 常见问题

1. **同步不工作**
   - 检查实体ID是否正确
   - 确认两个实体都存在且可用
   - 查看 Home Assistant 日志中的错误信息
   - 重启集成或 Home Assistant

2. **启用调试日志**
   ```yaml
   # configuration.yaml
   logger:
     default: warning
     logs:
       custom_components.ha_two_way_sync: debug
   ```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 这个仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

- **GitHub Issues**: [提交问题](https://github.com/symi-daguo/ha-two-way-sync/issues)
- **邮箱**: 303316404@qq.com

---

**版本**: 1.2.0  
**更新时间**: 2025年1月  
**兼容性**: Home Assistant 2024.1.0+  
**测试版本**: Home Assistant 2024.12.x