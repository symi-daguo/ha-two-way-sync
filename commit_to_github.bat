@echo off
echo ========================================
echo Home Assistant 双向同步集成 v1.1.0
echo 自动提交到GitHub
echo ========================================

cd /d "c:\Users\wgqtx\trae\ha-two-way-sync"

echo.
echo [1/6] 检查Git状态...
git status

echo.
echo [2/6] 添加所有更改...
git add .

echo.
echo [3/6] 提交更改...
git commit -m "🎉 v1.1.0: 解决回弹问题，实现实时同步

✨ 重要改进:
- 彻底解决灯光调亮度、调色温回弹问题
- 实现真正的实时同步，无延迟
- 开关操作100%%同步执行，步进操作立即同步
- 使用最新稳定Python技术栈，消除所有警告

🔧 技术优化:
- 现代化类型注解，使用 | 语法替代 Union
- 简化同步逻辑，移除复杂的状态检测
- 一次性同步所有属性，避免分步同步
- 50ms防重复机制，既防回弹又保证实时性

💡 用户体验:
- 消除调光调色温过程中的'卡顿'感
- 快速连续操作不再被跳过
- 更稳定的同步表现
- 零警告的开发体验

📦 架构改进:
- 重构为简洁、现代的代码结构
- 完整类型注解，支持最新Python特性
- 优化错误处理和日志记录
- 移除未使用的导入和参数"

echo.
echo [4/6] 推送到远程仓库...
git push origin main

echo.
echo [5/6] 创建版本标签...
git tag v1.1.0
git push origin v1.1.0

echo.
echo [6/6] 提交完成！
echo ========================================
echo 版本 v1.1.0 已成功提交到 GitHub
echo 仓库地址: https://github.com/symi-daguo/ha-two-way-sync
echo 发布页面: https://github.com/symi-daguo/ha-two-way-sync/releases
echo ========================================

echo.
echo 请访问以下链接创建 GitHub Release:
echo https://github.com/symi-daguo/ha-two-way-sync/releases/new?tag=v1.1.0

pause