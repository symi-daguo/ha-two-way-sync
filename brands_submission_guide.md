# Home Assistant Brands 提交指南

## 品牌logo显示问题解决方案

### 问题
集成添加时没有品牌logo显示

### 解决方案
需要向 Home Assistant 的 brands 仓库提交品牌信息

## 提交步骤

### 1. 准备文件
需要准备以下文件结构：
```
brands/
└── custom_integrations/
    └── ha_two_way_sync/
        ├── icon.png (256x256)
        └── icon@2x.png (512x512)
```

### 2. 图标要求
- **icon.png**: 256x256像素，PNG格式
- **icon@2x.png**: 512x512像素，PNG格式（高分辨率版本）
- 背景透明
- 设计简洁清晰

### 3. 提交流程
1. Fork https://github.com/home-assistant/brands
2. 在 `custom_integrations/` 目录下创建 `ha_two_way_sync` 文件夹
3. 添加图标文件
4. 提交 Pull Request

### 4. PR 描述模板
```
Add brand for ha_two_way_sync custom integration

This PR adds brand assets for the "Home Assistant SYMI双向同步" custom integration.

Integration details:
- Domain: ha_two_way_sync
- Name: Home Assistant SYMI双向同步
- Repository: https://github.com/symi-daguo/ha-two-way-sync
- Type: Custom Integration
- Function: Two-way entity synchronization

The integration provides two-way synchronization between Home Assistant entities.
```

## 当前状态
- ✅ 集成内已包含 icon.png
- ⏳ 需要提交到 brands 仓库
- ⏳ 等待 brands PR 合并

## 临时解决方案
在 brands 提交被接受之前，logo 可能不会显示，但这不影响集成的功能。

## 注意事项
- brands 提交通常需要几天到几周时间审核
- 提交后需要等待下一个 HA 版本发布才能看到效果
- 可以先发布集成，后续再提交 brands
