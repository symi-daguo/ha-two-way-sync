# Logo 配置说明

## 概述

本文档说明了 Home Assistant SYMI双向同步集成的 logo 配置和使用情况。

## Logo 文件位置

### 项目仓库中的 Logo 文件

- **位置**: 项目根目录
- **文件**:
  - `logo.png` - 主要品牌标识 (256x256 像素)
  - `icon.png` - 图标文件 (256x256 像素)

### Brands 仓库中的 Logo 文件

- **仓库**: https://github.com/symi-daguo/brands
- **位置**: `custom_integrations/ha_two_way_sync/`
- **文件**:
  - `logo.png` - 主要品牌标识 (256x256 像素)
  - `icon.png` - 图标文件 (256x256 像素)

## 配置文件说明

### 1. manifest.json

```json
{
  "domain": "ha_two_way_sync",
  "name": "Home Assistant SYMI双向同步",
  "brand": "ha_two_way_sync",
  ...
}
```

- `brand` 字段指定品牌标识符
- 对应 brands 仓库中的目录名

### 2. hacs.json

```json
{
  "brands": {
    "domain": "ha_two_way_sync",
    "logo": "https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/logo.png",
    "icon": "https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/icon.png"
  }
}
```

- `logo` 和 `icon` 字段指向项目仓库中的 logo 文件
- 使用 GitHub raw 链接确保可访问性

## Logo 使用场景

### 1. HACS 集成商店

- HACS 使用 `hacs.json` 中的 logo 路径显示集成图标
- 显示在集成列表和详情页面

### 2. Home Assistant 界面

- Home Assistant 使用 `manifest.json` 中的 brand 字段
- 查找对应的 brands 仓库中的 logo 文件
- 显示在集成配置界面

### 3. 文档和 README

- README.md 中使用项目仓库的 logo 链接
- 确保文档中的 logo 正常显示

## Logo 规范

### 文件格式
- **格式**: PNG
- **尺寸**: 256x256 像素
- **背景**: 透明或白色
- **质量**: 高质量，清晰可见

### 命名规范
- `logo.png` - 主要品牌标识
- `icon.png` - 简化图标版本

## 访问验证

### 项目仓库 Logo
- Logo: https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/logo.png
- Icon: https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/icon.png

### Brands 仓库 Logo
- Logo: https://raw.githubusercontent.com/symi-daguo/brands/master/custom_integrations/ha_two_way_sync/logo.png
- Icon: https://raw.githubusercontent.com/symi-daguo/brands/master/custom_integrations/ha_two_way_sync/icon.png

## 故障排除

### 常见问题

1. **Logo 不显示**
   - 检查文件路径是否正确
   - 验证文件是否存在于指定位置
   - 确认文件格式和尺寸符合规范

2. **HACS 中 Logo 不显示**
   - 检查 `hacs.json` 中的 logo 路径
   - 确认 GitHub raw 链接可访问
   - 清除 HACS 缓存并重新加载

3. **Home Assistant 中 Logo 不显示**
   - 检查 `manifest.json` 中的 brand 字段
   - 确认 brands 仓库中的文件存在
   - 重启 Home Assistant

### 调试步骤

1. 验证文件存在性
   ```bash
   curl -I https://raw.githubusercontent.com/symi-daguo/ha-two-way-sync/master/logo.png
   ```

2. 检查文件尺寸
   ```bash
   file logo.png
   ```

3. 验证配置文件
   - 检查 JSON 语法是否正确
   - 确认字段名和值是否匹配

## 更新流程

### 更新 Logo 文件

1. 替换项目根目录中的 `logo.png` 和 `icon.png`
2. 提交并推送到项目仓库
3. 更新 brands 仓库中的对应文件
4. 验证所有链接的可访问性

### 更新配置文件

1. 修改 `hacs.json` 或 `manifest.json`
2. 提交并推送更改
3. 重启相关服务验证效果

---

**最后更新**: 2025年1月21日  
**版本**: V2.0.3