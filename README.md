# Home Assistant SYMI双向同步集成

<div align="center">

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/release/symi-daguo/ha-two-way-sync.svg)](https://github.com/symi-daguo/ha-two-way-sync/releases)
[![License](https://img.shields.io/github/license/symi-daguo/ha-two-way-sync.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1.0+-blue.svg)](https://www.home-assistant.io/)

</div>

一个简单易用的 Home Assistant 自定义集成，用于实现两个实体之间的双向状态同步。

## 📢 HACS 收录状态

**当前状态**: 已提交 HACS 收录申请

- ✅ **GitHub Release v2.0.8**: 已创建
- ✅ **仓库描述和 Topics**: 已配置
- ✅ **Brands 仓库 Logo PR**: [#7818](https://github.com/home-assistant/brands/pull/7818) - 已提交
- 🔄 **HACS 收录申请**: 等待 Brands PR 合并后重新提交

> **注意**: HACS 收录申请正在处理中。在正式收录前，请使用手动安装方式或通过自定义存储库安装。

## 🎉 V2.0.8 正式版发布（2025-01-22）

### ✨ 核心功能
- **完善的双向同步**: 开关、调光、窗帘双向同步功能全面稳定
- **增强的看门狗机制**: 重启恢复机制，确保系统稳定性
- **优化的状态检查**: 实体状态检查和健康监控
- **稳定的自动恢复**: 后台自动恢复功能

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

## 📚 相关文档

- **[SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)**: HACS 收录详细设置指南
- **[LICENSE](LICENSE)**: 项目许可证

## 🏷️ HACS 收录信息

本项目正在申请加入 HACS 默认存储库，相关进展：

- **Brands 仓库**: 已提交 SYMI 品牌图标 PR [#7818](https://github.com/home-assistant/brands/pull/7818)
- **HACS 默认仓库**: 等待 Brands PR 合并后重新提交收录申请
- **收录要求**: 已满足所有 HACS 收录要求（GitHub Release、仓库描述、Topics、品牌图标等）

---

**当前版本**: V2.0.8  
**发布日期**: 2025年1月22日  
**兼容性**: Home Assistant 2024.1.0+  
**测试版本**: Home Assistant 2024.12.x  
**HACS 状态**: 收录申请中