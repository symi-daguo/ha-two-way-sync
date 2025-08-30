# Home Assistant Brands 仓库 Logo 提交指南

## 概述

根据 Home Assistant 官方规范，自定义集成的 logo 和品牌图片需要提交到官方的 [home-assistant/brands](https://github.com/home-assistant/brands) 仓库，而不是在集成项目内部放置。

## 为什么需要提交到 Brands 仓库？

1. **统一管理**: Home Assistant 通过 brands 仓库统一管理所有集成的品牌图片
2. **避免混淆**: 防止自定义集成使用 Home Assistant 官方品牌图片
3. **标准化**: 确保所有集成遵循相同的品牌图片标准
4. **性能优化**: 集中管理减少重复资源，提升加载性能

## 提交流程

### 1. 准备 Logo 文件

创建以下规格的 logo 文件：
- **icon.png**: 256x256 像素，PNG 格式，用于小图标显示
- **logo.png**: 256x256 像素，PNG 格式，用于品牌展示
- **logo@2x.png**: 512x512 像素，PNG 格式，用于高分辨率显示（可选）

**设计要求**：
- 背景透明
- 简洁清晰的设计
- 在小尺寸下仍然清晰可辨
- 符合品牌识别规范

### 2. Fork Brands 仓库

1. 访问 [home-assistant/brands](https://github.com/home-assistant/brands)
2. 点击右上角的 "Fork" 按钮
3. 将仓库 fork 到你的 GitHub 账户

### 3. 克隆仓库到本地

```bash
git clone https://github.com/YOUR_USERNAME/brands.git
cd brands
```

### 4. 创建集成目录

在 `custom_integrations` 目录下创建以你的集成域名命名的文件夹：

```bash
mkdir -p custom_integrations/ha_two_way_sync
```

### 5. 添加 Logo 文件

将准备好的 logo 文件复制到集成目录：

```bash
cp /path/to/your/icon.png custom_integrations/ha_two_way_sync/
cp /path/to/your/logo.png custom_integrations/ha_two_way_sync/
```

目录结构应该如下：
```
custom_integrations/
└── ha_two_way_sync/
    ├── icon.png
    └── logo.png
```

### 6. 创建 Manifest 文件

在集成目录下创建 `manifest.json` 文件：

```json
{
  "domain": "ha_two_way_sync",
  "name": "Home Assistant SYMI双向同步",
  "integrations": ["ha_two_way_sync"]
}
```

### 7. 提交更改

```bash
git add custom_integrations/ha_two_way_sync/
git commit -m "Add SYMI ha_two_way_sync integration brand assets"
git push origin main
```

### 8. 创建 Pull Request

1. 访问你 fork 的仓库页面
2. 点击 "Compare & pull request" 按钮
3. 填写 PR 标题和描述：
   - **标题**: `Add SYMI ha_two_way_sync integration brand assets`
   - **描述**: 简要说明你的集成和提交的品牌资源

### 9. 等待审核

- Home Assistant 团队会审核你的 PR
- 可能会要求修改 logo 设计或文件格式
- 审核通过后，你的 logo 将被合并到官方仓库

## 审核标准

### Logo 设计要求
- 原创设计，不侵犯版权
- 清晰的品牌识别
- 适合在小尺寸下显示
- 背景透明
- 符合 Home Assistant 的设计风格

### 技术要求
- PNG 格式
- 正确的文件尺寸
- 优化的文件大小
- 正确的目录结构

## 使用 Logo

一旦你的 logo 被合并到 brands 仓库，Home Assistant 会自动使用这些图片：

1. **集成页面**: 在设备与服务页面显示你的集成 logo
2. **HACS**: HACS 会自动获取并显示你的集成 logo
3. **文档**: 官方文档可能会使用你的 logo

## 注意事项

1. **不要在集成项目中包含 brands 目录**
2. **不要在 manifest.json 中使用 `brand` 字段**（除非你的集成已在 brands 仓库中）
3. **确保 logo 设计符合你的品牌规范**
4. **保持 logo 文件尺寸合理**（通常小于 50KB）

## 替代方案

如果你的 PR 暂时未被合并，你可以：

1. **在 README 中展示 logo**: 在项目 README 中包含 logo 图片
2. **在 HACS 中使用默认图标**: HACS 会显示默认的集成图标
3. **等待官方审核**: 继续完善你的 logo 设计，等待审核通过

## 相关链接

- [Home Assistant Brands 仓库](https://github.com/home-assistant/brands)
- [Home Assistant 开发者文档](https://developers.home-assistant.io/)
- [品牌指南](https://developers.home-assistant.io/docs/creating_integration_brand)

---

**注意**: 本指南基于 Home Assistant 官方规范编写，具体要求可能会随时间变化，请以官方文档为准。