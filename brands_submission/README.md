# Home Assistant SYMI 双向同步集成 - Brands 提交指南

## 📁 文件清单

已为 Home Assistant brands 仓库准备了以下4个标准图标文件：

```
brands_submission/custom_integrations/ha_two_way_sync/
├── icon.png      (256x256px, 5.8KB) - 标准图标
├── icon@2x.png   (512x512px, 11.7KB) - 高分辨率图标  
├── logo.png      (256x256px, 5.8KB) - 标准logo
└── logo@2x.png   (512x512px, 11.7KB) - 高分辨率logo
```

## ✅ 图标规格验证

- ✅ **格式**: PNG 格式，透明背景
- ✅ **尺寸**: 
  - icon.png: 256x256px
  - icon@2x.png: 512x512px
  - logo.png: 256x256px
  - logo@2x.png: 512x512px
- ✅ **质量**: 高质量双三次插值缩放
- ✅ **文件大小**: 合理范围内（5-12KB）

## 🚀 提交到 Home Assistant Brands 仓库步骤

### 1. Fork 官方仓库
访问 [home-assistant/brands](https://github.com/home-assistant/brands) 并点击 "Fork" 按钮

### 2. 克隆你的 Fork
```bash
git clone https://github.com/YOUR_USERNAME/brands.git
cd brands
```

### 3. 创建分支
```bash
git checkout -b add-ha-two-way-sync-brand
```

### 4. 添加品牌文件
创建目录并复制图标文件：
```bash
mkdir -p custom_integrations/ha_two_way_sync
```

将 `brands_submission/custom_integrations/ha_two_way_sync/` 目录下的所有4个PNG文件复制到：
`brands/custom_integrations/ha_two_way_sync/`

### 5. 提交更改
```bash
git add custom_integrations/ha_two_way_sync/
git commit -m "Add SYMI ha_two_way_sync custom integration brand assets"
git push origin add-ha-two-way-sync-brand
```

### 6. 创建 Pull Request
1. 访问你的 Fork 仓库页面
2. 点击 "Compare & pull request"
3. 填写 PR 标题和描述：

**标题**: `Add SYMI ha_two_way_sync custom integration brand assets`

**描述模板**:
```markdown
## 描述
为 SYMI 双向同步集成 (ha_two_way_sync) 添加品牌资源。

## 集成信息
- **Domain**: ha_two_way_sync
- **名称**: SYMI 双向同步
- **类型**: 自定义集成
- **仓库**: https://github.com/wgqtx/ha-two-way-sync

## 品牌资源
- ✅ icon.png (256x256px)
- ✅ icon@2x.png (512x512px) 
- ✅ logo.png (256x256px)
- ✅ logo@2x.png (512x512px)

所有图标均为PNG格式，透明背景，基于官方SYMI品牌logo制作。

## 检查清单
- [x] 图标符合 Home Assistant 品牌指南
- [x] 文件命名正确
- [x] 图标尺寸正确
- [x] PNG格式，透明背景
- [x] 集成domain与目录名一致
```

## 📋 重要注意事项

1. **Domain 一致性**: 确保 `manifest.json` 中的 `domain` 字段为 `ha_two_way_sync`
2. **文件路径**: 品牌文件必须放在 `custom_integrations/ha_two_way_sync/` 目录下
3. **审核时间**: PR 审核可能需要几天到几周时间
4. **合并后生效**: 一旦 PR 被合并，HACS 中的 Logo 将在下次缓存更新后显示

## 🔗 相关链接

- [Home Assistant Brands 仓库](https://github.com/home-assistant/brands)
- [品牌指南](https://developers.home-assistant.io/docs/creating_integration_brand_guidelines/)
- [SYMI 集成仓库](https://github.com/wgqtx/ha-two-way-sync)

## 📞 支持

如果在提交过程中遇到问题，可以：
1. 查看 Home Assistant 开发者文档
2. 在集成仓库中创建 Issue
3. 参考其他自定义集成的 brands PR 示例

---

**状态**: ✅ 品牌资源已准备完成，可以提交到 Home Assistant Brands 仓库