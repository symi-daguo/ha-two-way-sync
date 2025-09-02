# Home Assistant SYMI双向同步集成

![SYMI Logo](https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/logo.png)

## 简介

Home Assistant SYMI双向同步集成是一个功能强大的自定义集成，专为实现Home Assistant中两个实体之间的双向状态同步而设计。无论是灯光、开关、窗帘还是其他智能设备，都能实现完美的状态同步。

## 核心特性

- **智能双向同步**: 支持多种设备类型的双向状态同步
- **防循环机制**: 内置智能防循环算法，确保系统稳定
- **易于配置**: 通过Home Assistant UI界面轻松配置
- **广泛兼容**: 支持灯光、开关、窗帘、风扇、空调等多种设备
- **企业级稳定性**: 经过严格测试，确保长期稳定运行

## 支持的设备类型

| 设备类型 | 同步功能 | 说明 |
|---------|----------|------|
| 灯光 (light) | 完美同步 | 状态、亮度、颜色等所有属性 |
| 开关 (switch) | 完美同步 | 开关状态同步 |
| 窗帘 (cover) | 完美同步 | 开关状态和位置同步 |
| 风扇 (fan) | 完美同步 | 状态、速度等属性同步 |
| 空调 (climate) | 完美同步 | 温度、模式等属性同步 |
| 其他设备 | 基础同步 | 开关状态同步 |

## 安装要求

- Home Assistant 2024.1.0 或更高版本
- Python 3.12 或更高版本
- HACS（推荐用于自动更新）

## 关于SYMI

SYMI是专注于智能家居解决方案的技术品牌，致力于为用户提供稳定、易用的智能家居集成产品。

## 技术支持

- GitHub Issues: [提交问题](https://github.com/symi-daguo/ha-two-way-sync/issues)
- 邮箱支持: 303316404@qq.com

---

**版本**: 2.0.7  
**兼容性**: Home Assistant 2024.1.0+  
**许可证**: MIT License