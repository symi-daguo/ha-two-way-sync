# HACS收录完整设置指南

本指南将帮助您完成Home Assistant集成的HACS收录申请的所有步骤。

## 当前状态

✅ **GitHub Release v2.0.3**: 已创建  
✅ **仓库描述和Topics**: 已设置  
🟡 **Brands仓库PR**: [#7810](https://github.com/home-assistant/brands/pull/7810) - 等待审核中  
❌ **HACS收录申请**: [#4061](https://github.com/hacs/default/pull/4061) - 已关闭，需重新提交  

### HACS生效时间说明

HACS收录申请的审核和生效时间通常为：
- **初次审核**: 1-2周
- **修改后重审**: 3-7天
- **生效时间**: 审核通过后立即生效

**注意**: Brands仓库的PR需要先被合并，HACS收录申请才能成功。

## 前置要求

1. **GitHub Personal Access Token**
   - 访问 [GitHub Settings > Tokens](https://github.com/settings/tokens)
   - 创建新的Personal Access Token (Classic)
   - 需要以下权限：
     - `repo` (完整仓库访问权限)
     - `workflow` (工作流权限)
     - `write:packages` (包写入权限)

2. **必要文件检查**
   确保以下文件存在且正确：
   - `custom_components/ha_two_way_sync/manifest.json`
   - `hacs.json`
   - `logo.png` (256x256像素，PNG格式)
   - `icon.png` (256x256像素，PNG格式)
   - `README.md`

3. **HACS收录要求**
   - 仓库必须是公开的
   - 必须有至少一个GitHub Release
   - 必须有适当的仓库描述和topics
   - 代码质量符合Home Assistant标准
   - Brands仓库的logo文件已被接受

## 详细操作流程

### 第一步：准备GitHub仓库

1. **创建GitHub Release**
```powershell
# 设置GitHub Token
$env:GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"

# 创建v2.0.3 release
$releaseData = @{
    tag_name = "v2.0.3"
    target_commitish = "main"
    name = "v2.0.3"
    body = "Release for HACS submission"
    draft = $false
    prerelease = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/ha-two-way-sync/releases" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $releaseData -ContentType 'application/json'
```

2. **设置仓库描述和Topics**
```powershell
# 更新仓库信息
$repoData = @{
    description = "Home Assistant custom integration for two-way synchronization"
    topics = @("home-assistant", "hacs", "custom-integration", "synchronization")
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/ha-two-way-sync" -Method PATCH -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $repoData -ContentType 'application/json'
```

### 第二步：提交Logo到Brands仓库

1. **Fork home-assistant/brands仓库**
```powershell
# Fork brands仓库
Invoke-RestMethod -Uri "https://api.github.com/repos/home-assistant/brands/forks" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' }
```

2. **创建新分支并上传logo文件**
```powershell
# 获取主分支SHA
$masterRef = Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/brands/git/refs/heads/master" -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN" }

# 创建新分支
$branchData = @{
    ref = "refs/heads/add-ha-two-way-sync-logos"
    sha = $masterRef.object.sha
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/brands/git/refs" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $branchData -ContentType 'application/json'

# 上传logo.png和icon.png文件
# (需要将文件转换为base64格式)
```

3. **创建Pull Request**
```powershell
# 创建PR到home-assistant/brands
$prData = @{
    title = "Add brand images for ha_two_way_sync custom integration"
    head = "symi-daguo:add-ha-two-way-sync-logos"
    base = "master"
    body = "Adding logo and icon files for ha_two_way_sync custom integration for Home Assistant."
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/home-assistant/brands/pulls" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $prData -ContentType 'application/json'
```

### 第三步：提交HACS收录申请

1. **Fork hacs/default仓库**
```powershell
# Fork HACS default仓库
Invoke-RestMethod -Uri "https://api.github.com/repos/hacs/default/forks" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' }
```

2. **更新integration文件**
```powershell
# 获取当前integration文件内容
$integrationFile = Invoke-RestMethod -Uri "https://api.github.com/repos/hacs/default/contents/integration" -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN" }

# 解码内容并添加新集成
$content = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($integrationFile.content))
$newContent = $content + "symi-daguo/ha-two-way-sync`n"
$encodedContent = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($newContent))

# 提交更新
$updateData = @{
    message = "Add symi-daguo/ha-two-way-sync integration"
    content = $encodedContent
    sha = $integrationFile.sha
    branch = "add-ha-two-way-sync"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/default/contents/integration" -Method PUT -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $updateData -ContentType 'application/json'
```

3. **创建HACS收录申请PR**
```powershell
# 创建PR到hacs/default
$hacsData = @{
    title = "Add symi-daguo/ha-two-way-sync integration"
    head = "symi-daguo:add-ha-two-way-sync"
    base = "master"
    body = @"
## Integration Information

**Repository**: https://github.com/symi-daguo/ha-two-way-sync
**Domain**: ha_two_way_sync
**Type**: Integration

## Description

Home Assistant custom integration for two-way synchronization between different systems.

## HACS Requirements Checklist

- [x] Repository is public
- [x] Has at least one release
- [x] Repository has description and topics
- [x] Code follows Home Assistant standards
- [x] Brands repository PR submitted

## Related Links

- Brands PR: https://github.com/home-assistant/brands/pull/7810
- Documentation: https://github.com/symi-daguo/ha-two-way-sync/blob/main/README.md
"@
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.github.com/repos/hacs/default/pulls" -Method POST -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' } -Body $hacsData -ContentType 'application/json'
```

## 验证操作结果

### 第四步：验证所有操作

1. **检查GitHub Release和仓库信息**
```powershell
# 检查GitHub Release
$releases = Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/ha-two-way-sync/releases" -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' }
Write-Host "Latest Release: $($releases[0].tag_name) - $($releases[0].name)"

# 检查仓库信息
$repo = Invoke-RestMethod -Uri "https://api.github.com/repos/symi-daguo/ha-two-way-sync" -Headers @{ 'Authorization' = "token $env:GITHUB_TOKEN"; 'Accept' = 'application/vnd.github.v3+json' }
Write-Host "Repository Description: $($repo.description)"
Write-Host "Topics: $($repo.topics -join ', ')"
```

2. **检查PR状态**
```powershell
# 检查Brands PR状态
$brandsPR = Invoke-RestMethod -Uri "https://api.github.com/repos/home-assistant/brands/pulls/7810" -Headers @{ 'User-Agent' = 'PowerShell/7.0' }
Write-Host "Brands PR #7810 状态: $($brandsPR.state)"
Write-Host "合并状态: $($brandsPR.merged)"

# 检查HACS PR状态（如果重新提交）
# $hacsPR = Invoke-RestMethod -Uri "https://api.github.com/repos/hacs/default/pulls/YOUR_NEW_PR_NUMBER" -Headers @{ 'User-Agent' = 'PowerShell/7.0' }
# Write-Host "HACS PR 状态: $($hacsPR.state)"
```

3. **使用curl验证（替代方案）**
```bash
# 检查releases
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/symi-daguo/ha-two-way-sync/releases

# 检查仓库信息
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/symi-daguo/ha-two-way-sync

# 检查PR状态
curl -H "User-Agent: curl/7.0" \
     https://api.github.com/repos/home-assistant/brands/pulls/7810
```

## 脚本说明

### `complete_hacs_setup.ps1`
主控脚本，执行所有操作并提供详细的进度反馈。

**参数：**
- `-GitHubToken`: GitHub Personal Access Token（必需）
- `-SkipBrands`: 跳过brands仓库操作
- `-SkipHacsSubmission`: 跳过HACS收录申请
- `-DryRun`: 干运行模式，不执行实际操作

### `github_api_setup.ps1`
处理GitHub仓库的基本设置：
- 创建v2.0.3 release
- 添加仓库描述
- 设置topics
- 验证操作结果

### `brands_repo_setup.ps1`
处理Home Assistant brands仓库：
- Fork home-assistant/brands仓库
- 上传logo和icon文件
- 创建Pull Request

### `hacs_submission.ps1`
处理HACS收录申请：
- Fork hacs/default仓库
- 更新integrations.json文件
- 创建收录申请Pull Request

## 常见问题

### Q: GitHub API操作失败怎么办？
A: 
1. **检查Token权限**: 确保GitHub Token有以下权限：
   - `repo` (完整仓库访问权限)
   - `workflow` (工作流权限)
   - `write:packages` (包写入权限)
2. **网络连接**: 确认网络连接正常，可以访问GitHub API
3. **错误分析**: 查看具体错误信息，常见错误：
   - `401 Unauthorized`: Token无效或权限不足
   - `404 Not Found`: 仓库不存在或无访问权限
   - `422 Unprocessable Entity`: 请求数据格式错误

### Q: 如何检查操作是否成功？
A: 
1. **GitHub仓库检查**:
   - 访问 https://github.com/symi-daguo/ha-two-way-sync/releases
   - 确认v2.0.3 release存在
   - 检查仓库描述和topics是否正确设置
2. **PR状态检查**:
   - Brands PR: https://github.com/home-assistant/brands/pull/7810
   - 使用上述验证脚本检查状态

### Q: Brands仓库的PR被拒绝怎么办？
A: 
1. **Logo规范检查**:
   - 确保logo.png和icon.png都是256x256像素
   - 文件格式必须是PNG
   - 背景应该是透明的
   - 设计应该简洁明了
2. **文件路径**: 确认文件上传到正确路径：
   - `custom_integrations/ha_two_way_sync/icon.png`
   - `custom_integrations/ha_two_way_sync/logo.png`
3. **根据反馈修改**: 仔细阅读维护者的评论并进行相应修改

### Q: HACS收录申请被拒绝怎么办？
A: 
1. **检查HACS要求**:
   - 仓库必须是公开的
   - 必须有至少一个GitHub Release
   - 代码质量符合Home Assistant标准
   - 必须有适当的文档
2. **常见拒绝原因**:
   - Brands仓库的PR尚未合并
   - 代码质量不符合标准
   - 缺少必要的配置文件
   - 文档不完整
3. **重新提交**: 修改问题后可以重新提交申请

### Q: 为什么HACS PR #4061被关闭了？
A: 
1. **可能原因**:
   - 自动化检查失败
   - Brands仓库PR尚未合并
   - 集成不符合HACS标准
   - 重复提交
2. **解决方案**:
   - 等待Brands PR合并后重新提交
   - 检查并修复代码质量问题
   - 确保所有必需文件都存在且正确

### Q: 多久能在HACS中看到我的集成？
A: 
1. **审核时间**:
   - Brands仓库PR: 1-4周
   - HACS收录申请: 1-2周
2. **生效时间**: 审核通过后立即生效
3. **加速方法**:
   - 确保所有要求都满足
   - 及时回应维护者的反馈
   - 保持代码质量高标准

## 后续步骤

1. **等待审核**
   - Brands仓库的PR通常需要几天到几周
   - HACS收录申请也需要类似的时间

2. **监控进度**
   - 关注相关PR的状态和评论
   - 及时回应维护者的问题和建议

3. **发布后维护**
   - 定期更新集成
   - 处理用户反馈和bug报告
   - 保持与Home Assistant版本的兼容性

## 支持

如果遇到问题，可以：
1. 查看HACS官方文档：https://hacs.xyz/
2. 参考Home Assistant开发者文档：https://developers.home-assistant.io/
3. 在相关GitHub仓库中提交Issue

---

**注意：** 请妥善保管您的GitHub Personal Access Token，不要在公开场所分享。