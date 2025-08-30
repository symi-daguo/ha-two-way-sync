# Home Assistant Brands 仓库提交指南

## 概述

为了让您的 Home Assistant SYMI双向同步 集成在 Home Assistant 前端正确显示 logo 和图标，需要将标准化的图片文件提交到 Home Assistant 官方 brands 仓库。

## 已准备的文件

我们已经基于您的 `SYMI-logo.png` 创建了符合 Home Assistant 要求的标准文件：

- ✅ `icon.png` - 256x256像素，正方形图标
- ✅ `logo.png` - 256x256像素，品牌logo
- ✅ 格式：PNG，带透明通道，已优化压缩
- ✅ 文件大小：约9.7KB（符合web优化要求）

## 提交步骤

### 1. Fork Home Assistant Brands 仓库

访问 [https://github.com/home-assistant/brands](https://github.com/home-assistant/brands) 并点击 "Fork" 按钮创建您的分支。

### 2. 创建目录结构

在您的 fork 中，导航到 `custom_integrations` 文件夹，创建以下目录结构：

```
custom_integrations/
└── ha_two_way_sync/
    ├── icon.png
    └── logo.png
```

**重要**：目录名 `ha_two_way_sync` 必须与您的 `manifest.json` 中的 `domain` 字段完全匹配。

### 3. 上传文件

将本项目根目录下的以下文件上传到 `custom_integrations/ha_two_way_sync/` 目录：
- `icon.png`
- `logo.png`

### 4. 创建 Pull Request

1. 提交更改到您的 fork
2. 创建 Pull Request 到 `home-assistant/brands` 的 `main` 分支
3. 在 PR 描述中说明：
   ```
   Add brand images for ha_two_way_sync custom integration
   
   - Added icon.png (256x256px)
   - Added logo.png (256x256px)
   - Images are optimized PNG format with transparency
   - Integration domain: ha_two_way_sync
   ```

### 5. 等待审核

Home Assistant 维护者会审核您的 PR。一旦合并，您的 logo 将在以下 URL 可用：

- Icon: `https://brands.home-assistant.io/ha_two_way_sync/icon.png`
- Logo: `https://brands.home-assistant.io/ha_two_way_sync/logo.png`

## 验证

提交后，您可以通过以下方式验证：

1. **浏览器访问**：直接访问上述 URL 查看图片
2. **Home Assistant 前端**：在集成页面查看是否显示 logo
3. **HACS**：在 HACS 中搜索您的集成，查看是否显示图标

## 注意事项

- 📝 图片更改可能需要 24-48 小时才能在所有用户端生效（由于 CDN 缓存）
- 🔄 Home Assistant 会在每个主要版本发布时清除 Cloudflare 缓存
- ⚠️ 确保不要使用 Home Assistant 官方品牌图片，以免混淆用户
- 📏 严格遵循图片规格要求（PNG格式、正确尺寸、透明背景等）

## 相关链接

- [Home Assistant Brands 仓库](https://github.com/home-assistant/brands)
- [自定义集成 Logo 官方文档](https://developers.home-assistant.io/blog/2020/05/08/logos-custom-integrations/)
- [图片规格要求](https://github.com/home-assistant/brands#image-specification)

---

完成上述步骤后，您的 Home Assistant SYMI双向同步 集成将在所有支持的位置正确显示品牌 logo 和图标！