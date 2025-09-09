# Home Assistant SYMI双向同步集成

<div align="center">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/symi-daguo/ha-two-way-sync.svg)](https://github.com/symi-daguo/ha-two-way-sync/releases)
[![License](https://img.shields.io/github/license/symi-daguo/ha-two-way-sync.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1.0+-blue.svg)](https://www.home-assistant.io/)

</div>

一个简单易用的 Home Assistant 自定义集成，用于实现两个实体之间的双向状态同步。

## 🎉 V2.1.5 正式版发布（2025年9月9日）

### 🔧 重大修复
- **彻底解决"实体不存在"问题**: 修复启动时序问题，支持延迟启动和自动重试
- **增强防死循环机制**: 添加同步源跟踪，防止反向触发
- **改进错误恢复**: 自动处理网络中断、设备重启、OTA更新等突发事件
- **优化性能和稳定性**: 减少不必要检查，改进资源管理

### ✨ 核心功能
- **完善的双向同步**: 开关、调光、窗帘双向同步功能全面稳定
- **智能实体检查**: 定期检查实体可用性，自动恢复同步
- **集成重新加载支持**: 新增reload服务，无需重启HA即可重新加载集成
- **增强错误恢复机制**: 自动重连、异常处理，确保系统高可用性
- **健康监控**: 实体状态检查和健康监控，定期检查实体可用性
- **稳定的自动恢复**: 后台自动恢复功能，处理各种突发情况
- **防死循环机制**: 增强的防循环同步机制，确保系统稳定运行
- **详细日志记录**: 优化的调试信息和性能监控，便于问题诊断

## ✨ 功能特性

- 🔄 **双向同步**: 支持两个实体之间的实时双向状态同步
- 🎯 **智能同步**: 相同类型实体支持完美同步（状态+属性），不同类型实体支持基础同步（开关状态）
- 🛡️ **防循环**: 内置防循环同步机制，确保系统稳定
- 🔧 **易配置**: 通过 Home Assistant UI 界面轻松配置
- 📱 **广泛支持**: 支持灯光、开关、窗帘、风扇、空调、加湿器、热水器、扫地机、媒体播放器、场景、脚本等多种设备类型
- 🎛️ **服务支持**: 提供手动同步、切换同步状态和重新加载集成的服务
- 🔄 **重新加载**: 支持集成重新加载，无需重启HA即可恢复集成功能
- 🛠️ **错误恢复**: 自动处理网络中断、设备重启、OTA更新等突发事件

## 📋 系统要求

- Home Assistant 2024.1.0 或更高版本
- Python 3.12 或更高版本（推荐）
- HACS（可选，用于自动更新）

## 🚀 安装方法

### 方法一：通过 HACS 安装

**当前状态**: HACS 收录申请正在处理中，暂时需要通过自定义存储库安装

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中点击 "集成"
3. 点击右上角的三个点，选择 "自定义存储库"
4. 添加存储库 URL: `https://github.com/symi-daguo/ha-two-way-sync`
5. 类别选择 "集成"
6. 搜索并安装 "Home Assistant 双向同步集成"
7. 重启 Home Assistant

> **未来**: 一旦 HACS 收录申请通过，您将可以直接在 HACS 默认存储库中搜索并安装此集成。

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

### `ha_two_way_sync.reload`
重新加载所有双向同步配置

```yaml
service: ha_two_way_sync.reload
```

## � 更新日志

### [2.1.5] - 2025-09-09
**重大修复**
- 🐛 **修复颜色属性冲突**: 解决"two or more values in the same group of exclusion 'Color descriptors'"错误
- 🎯 **优化同步逻辑**: 区分有步进过程的设备（调光、窗帘）和即时生效设备（开关）
- 🔄 **改进属性检测**: 增强对亮度、颜色、位置等关键属性变化的检测
- 🛡️ **防冲突机制**: 按优先级设置颜色属性（RGB > HS > 色温），避免同时设置多个颜色描述符

**同步策略优化**
- ⚡ **调光设备**: 检测亮度、颜色变化时立即同步目标状态，不等反馈
- 🪟 **窗帘设备**: 检测位置变化时立即同步目标位置，不等反馈
- 🔌 **开关设备**: 状态变化后实时同步，因为立即生效无等待过程
- 📊 **详细日志**: 添加颜色同步、位置同步的详细调试信息

### [2.1.4] - 2025-09-09
**重大修复**
- 🐛 彻底修复"实体不存在，无法设置同步"的关键问题
- 🔄 解决HA启动时实体尚未加载导致的同步设置失败
- 🛡️ 增强防循环同步机制，添加同步源跟踪
- 🔧 改进错误处理和自动恢复机制

**新增功能**
- ⏰ 延迟启动机制，给HA时间加载所有实体
- 🔍 实体检查重试，定期检查实体可用性并自动恢复同步
- 📊 健康检查，定期监控实体状态变化
- 🔄 智能重载，完善reload服务支持一键重载集成

**技术改进**
- 🛠️ 大幅提升集成稳定性，支持HA重启、断网等突发情况
- 📝 优化日志记录，减少错误日志，增加调试信息
- ⚡ 优化同步性能，减少不必要的检查
- 🧹 代码清理，删除不需要的文件，优化代码结构

### [2.1.3] - 2025-09-03
- 🐛 修复集成无法在Home Assistant中正常添加的关键问题
- 📁 补充缺失的services.yaml、strings.json和translations文件
- 🔧 修复manifest.json配置不完整导致的加载失败
- 🌐 恢复完整的中英文界面支持

## �🔧 故障排除

### 常见问题

1. **同步不工作**
   - 检查实体ID是否正确
   - 确认两个实体都存在且可用
   - 等待2-5分钟让集成自动检测实体
   - 使用reload服务重新加载集成
   - 查看 Home Assistant 日志中的错误信息

2. **实体不存在错误**
   - v2.1.4已修复此问题，更新后等待自动恢复
   - 如仍有问题，使用reload服务强制重新加载
   - 确认实体在HA中确实存在且可用

3. **启用调试日志**
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

## 📚 相关文档

- **[LICENSE](LICENSE)**: 项目许可证

## 🏷️ HACS 收录信息

本项目正在申请加入 HACS 默认存储库，相关进展：

- **Brands 仓库**: 已提交 SYMI 品牌图标 PR [#7818](https://github.com/home-assistant/brands/pull/7818)
- **HACS 默认仓库**: 等待 Brands PR 合并后重新提交收录申请
- **收录要求**: 已满足所有 HACS 收录要求（GitHub Release、仓库描述、Topics、品牌图标等）

---

**当前版本**: V2.1.4
**发布日期**: 2025年9月9日
**兼容性**: Home Assistant 2024.1.0+
**测试版本**: Home Assistant 2024.12.x
**HACS 状态**: 收录申请中