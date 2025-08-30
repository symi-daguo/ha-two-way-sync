# HACS 安装指南

![SYMI Logo](SYMI-logo.png)

## 通过 HACS 安装 Home Assistant SYMI双向同步集成

### 前提条件

1. 确保已安装 [HACS (Home Assistant Community Store)](https://hacs.xyz/)
2. Home Assistant 版本 2024.1.0 或更高

### 安装步骤

#### 方法一：自定义仓库安装（推荐）

1. **打开 HACS**
   - 在 Home Assistant 侧边栏中点击 "HACS"

2. **添加自定义仓库**
   - 点击右上角的三个点菜单
   - 选择 "自定义存储库"
   - 在 "存储库" 字段中输入：`https://github.com/symi-daguo/ha-two-way-sync`
   - 在 "类别" 下拉菜单中选择 "集成"
   - 点击 "添加"

3. **安装集成**
   - 在 HACS 的 "集成" 页面中搜索 "SYMI双向同步"
   - 点击集成卡片
   - 点击 "下载" 按钮
   - 等待下载完成

4. **重启 Home Assistant**
   - 转到 "设置" > "系统" > "重启"
   - 等待重启完成

5. **配置集成**
   - 转到 "设置" > "设备与服务"
   - 点击 "添加集成"
   - 搜索 "Home Assistant SYMI双向同步"
   - 按照配置向导完成设置

### 验证安装

安装成功后，您应该能够：

1. 在 "设备与服务" 页面看到 "Home Assistant SYMI双向同步" 集成
2. 看到 SYMI 品牌 logo 显示在集成卡片上
3. 能够配置两个实体之间的双向同步

### 更新集成

HACS 会自动检查更新。当有新版本可用时：

1. 在 HACS 的 "集成" 页面中找到 "SYMI双向同步"
2. 如果有更新，会显示 "更新" 按钮
3. 点击 "更新" 并重启 Home Assistant

### 故障排除

#### 找不到集成
- 确保已正确添加自定义仓库
- 检查仓库 URL 是否正确
- 尝试刷新 HACS 页面

#### 安装失败
- 检查 Home Assistant 版本是否满足要求（2024.1.0+）
- 查看 Home Assistant 日志中的错误信息
- 确保网络连接正常

#### Logo 不显示
- 重启 Home Assistant
- 清除浏览器缓存
- 检查 brands 目录是否正确安装

### 技术支持

如果遇到问题，请：

1. 查看 [GitHub Issues](https://github.com/symi-daguo/ha-two-way-sync/issues)
2. 提交新的 Issue 并提供详细的错误信息
3. 联系邮箱：303316404@qq.com

### 卸载集成

如需卸载：

1. 在 "设备与服务" 中删除所有 SYMI双向同步 配置
2. 在 HACS 中卸载集成
3. 重启 Home Assistant

---

**版本**: v2.0.1  
**更新日期**: 2025年1月  
**兼容性**: Home Assistant 2024.1.0+