# Home Assistant SYMI双向同步集成 - 技术架构文档

## 项目概述

本项目是一个 Home Assistant 自定义集成，用于实现两个实体之间的双向状态同步。支持多种设备类型，包括灯光、开关、窗帘、风扇等。

## 技术栈

- **语言**: Python 3.12+
- **框架**: Home Assistant Integration Framework
- **配置**: YAML + JSON
- **包管理**: Home Assistant Component System
- **版本控制**: Git
- **发布平台**: GitHub Releases + HACS

## 项目结构

```
ha-two-way-sync/
├── .github/
│   └── workflows/          # GitHub Actions 工作流
├── brands_submission/       # Home Assistant Brands 提交文件
│   ├── README.md
│   └── custom_integrations/
│       └── ha_two_way_sync/
│           ├── icon.png     # 集成图标 (256x256)
│           └── icon@2x.png  # 高分辨率图标 (512x512)
├── custom_components/       # 主要集成代码
│   └── ha_two_way_sync/
│       ├── __init__.py      # 集成初始化
│       ├── config_flow.py   # 配置流程
│       ├── manifest.json    # 集成清单
│       ├── services.yaml    # 服务定义
│       ├── strings.json     # 字符串资源
│       └── translations/    # 多语言支持
│           ├── en.json
│           └── zh.json
├── hacs.json               # HACS 配置文件
├── README.md               # 项目说明文档
├── ARCHITECTURE.md         # 技术架构文档
├── LICENSE                 # 开源许可证
├── info.md                 # 集成信息
└── *.png                   # 项目图标文件
```

## 核心组件

### 1. 集成初始化 (`__init__.py`)
- 负责集成的启动和关闭
- 管理实体状态监听
- 实现双向同步逻辑
- 防循环同步机制

### 2. 配置流程 (`config_flow.py`)
- 用户界面配置向导
- 实体选择和验证
- 配置数据存储

### 3. 服务定义 (`services.yaml`)
- `manual_sync`: 手动同步服务
- `toggle_sync`: 切换同步状态服务

### 4. 清单文件 (`manifest.json`)
- 集成元数据定义
- 依赖关系声明
- 版本信息管理

## 同步机制

### 双向同步算法
1. **状态监听**: 监听两个实体的状态变化
2. **变化检测**: 检测状态或属性的变化
3. **防循环**: 使用时间戳和状态标记防止循环同步
4. **属性映射**: 根据实体类型映射相应的属性
5. **状态应用**: 将变化应用到目标实体

### 支持的同步类型
- **完美同步**: 同类型实体，同步所有状态和属性
- **基础同步**: 不同类型实体，仅同步开关状态

## HACS 集成

### 配置文件 (`hacs.json`)
```json
{
  "name": "Home Assistant SYMI双向同步集成",
  "render_readme": true,
  "country": ["CN"],
  "homeassistant": "2024.1.0",
  "zip_release": true,
  "filename": "symi.zip",
  "hide_default_branch": true
}
```

### 关键配置说明
- `zip_release`: 启用 ZIP 发布模式
- `filename`: 指定下载的 ZIP 文件名
- `homeassistant`: 最低支持的 HA 版本

## 发布流程

### 版本发布步骤
1. **更新版本号**: 修改 `manifest.json` 中的版本
2. **更新文档**: 更新 README.md 和相关文档
3. **创建 ZIP 包**: 打包 `custom_components/ha_two_way_sync` 目录
4. **Git 提交**: 提交所有更改到 Git
5. **创建 Release**: 在 GitHub 创建新的 Release
6. **上传文件**: 上传 ZIP 文件到 Release

### GitHub Release 要求
- Release 标签格式: `v{version}` (如 `v2.1.0`)
- ZIP 文件名: `symi.zip`
- 包含完整的集成代码

## 版本历史

### v2.1.1 (2025年9月3日)
**功能特性**:
- 完善的双向同步功能
- 增强的看门狗机制
- 优化的状态检查
- 稳定的自动恢复功能

**技术特性**:
- 支持多种设备类型同步
- 防循环同步机制
- 完整的配置流程
- 多语言支持

### v2.0.8 (2025年9月2日)
- 完善双向同步功能
- 增强看门狗机制
- 优化状态检查
- 稳定自动恢复功能

## 故障排除

### 常见问题

**问题**: 同步不工作
**解决方案**:
1. 检查实体是否存在且可用
2. 确认实体类型支持同步
3. 查看 Home Assistant 日志获取详细错误信息

**问题**: 配置失败
**解决方案**:
1. 确保选择的实体有效
2. 检查实体权限设置
3. 重启 Home Assistant 后重试

## 开发指南

### 本地开发环境
1. 克隆仓库到 Home Assistant 配置目录
2. 重启 Home Assistant
3. 在集成页面添加集成进行测试

### 调试配置
```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.ha_two_way_sync: debug
```

### 代码规范
- 遵循 Home Assistant 开发规范
- 使用 Python 类型提示
- 添加适当的错误处理
- 编写单元测试

## 依赖关系

### 运行时依赖
- Home Assistant Core >= 2024.1.0
- Python >= 3.12

### 开发依赖
- Home Assistant 开发环境
- Git
- 文本编辑器或 IDE

## 安全考虑

- 不存储敏感信息
- 验证用户输入
- 适当的错误处理
- 遵循 Home Assistant 安全最佳实践

## 性能优化

- 异步操作避免阻塞
- 合理的状态更新频率
- 内存使用优化
- 防循环同步机制

## 未来规划

- 支持更多设备类型
- 增强配置选项
- 改进用户界面
- 添加更多同步模式
- 性能监控和统计

---

**文档版本**: v2.1.1  
**最后更新**: 2025年9月3日  
**维护者**: symi-daguo