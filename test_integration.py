#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Home Assistant SYMI双向同步集成的基本功能
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# 添加自定义组件路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

def test_manifest_json():
    """测试 manifest.json 文件"""
    print("🔍 测试 manifest.json 文件...")
    
    manifest_path = Path("custom_components/ha_two_way_sync/manifest.json")
    if not manifest_path.exists():
        print("❌ manifest.json 文件不存在")
        return False
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        required_fields = ['domain', 'name', 'version', 'documentation_url', 'codeowners']
        for field in required_fields:
            if field not in manifest:
                print(f"❌ manifest.json 缺少必需字段: {field}")
                return False
        
        print(f"✅ manifest.json 验证通过")
        print(f"   - 域名: {manifest['domain']}")
        print(f"   - 版本: {manifest['version']}")
        print(f"   - 名称: {manifest['name']}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ manifest.json 格式错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 读取 manifest.json 失败: {e}")
        return False

def test_init_file():
    """测试 __init__.py 文件"""
    print("\n🔍 测试 __init__.py 文件...")
    
    init_path = Path("custom_components/ha_two_way_sync/__init__.py")
    if not init_path.exists():
        print("❌ __init__.py 文件不存在")
        return False
    
    try:
        # 尝试导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("ha_two_way_sync", init_path)
        if spec is None:
            print("❌ 无法创建模块规范")
            return False
        
        module = importlib.util.module_from_spec(spec)
        
        # 检查必需的函数
        with open(init_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_functions = ['async_setup_entry', 'async_unload_entry']
        for func in required_functions:
            if func not in content:
                print(f"❌ __init__.py 缺少必需函数: {func}")
                return False
        
        print("✅ __init__.py 验证通过")
        print("   - 包含必需的设置和卸载函数")
        return True
        
    except Exception as e:
        print(f"❌ 验证 __init__.py 失败: {e}")
        return False

def test_config_flow():
    """测试 config_flow.py 文件"""
    print("\n🔍 测试 config_flow.py 文件...")
    
    config_flow_path = Path("custom_components/ha_two_way_sync/config_flow.py")
    if not config_flow_path.exists():
        print("❌ config_flow.py 文件不存在")
        return False
    
    try:
        with open(config_flow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查必需的类和方法
        required_items = ['ConfigFlow', 'async_step_user']
        for item in required_items:
            if item not in content:
                print(f"❌ config_flow.py 缺少必需项: {item}")
                return False
        
        print("✅ config_flow.py 验证通过")
        print("   - 包含配置流类和用户步骤")
        return True
        
    except Exception as e:
        print(f"❌ 验证 config_flow.py 失败: {e}")
        return False

def test_translations():
    """测试翻译文件"""
    print("\n🔍 测试翻译文件...")
    
    translations_dir = Path("custom_components/ha_two_way_sync/translations")
    if not translations_dir.exists():
        print("❌ translations 目录不存在")
        return False
    
    # 检查中文和英文翻译文件
    required_files = ['zh.json', 'en.json']
    for lang_file in required_files:
        lang_path = translations_dir / lang_file
        if not lang_path.exists():
            print(f"❌ 翻译文件不存在: {lang_file}")
            return False
        
        try:
            with open(lang_path, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"✅ {lang_file} 验证通过")
        except json.JSONDecodeError as e:
            print(f"❌ {lang_file} 格式错误: {e}")
            return False
    
    return True

def test_version_consistency():
    """测试版本一致性"""
    print("\n🔍 测试版本一致性...")
    
    # 检查 manifest.json 版本
    manifest_path = Path("custom_components/ha_two_way_sync/manifest.json")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    manifest_version = manifest['version']
    
    # 检查 README.md 版本
    readme_path = Path("README.md")
    with open(readme_path, 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    # 检查 info.md 版本
    info_path = Path("info.md")
    with open(info_path, 'r', encoding='utf-8') as f:
        info_content = f.read()
    
    expected_version = "2.1.2"
    
    if manifest_version != expected_version:
        print(f"❌ manifest.json 版本不匹配: {manifest_version} != {expected_version}")
        return False
    
    if f"V{expected_version}" not in readme_content:
        print(f"❌ README.md 版本不匹配")
        return False
    
    if f"当前版本：{expected_version}" not in info_content:
        print(f"❌ info.md 版本不匹配")
        return False
    
    print(f"✅ 版本一致性验证通过: {expected_version}")
    return True

def main():
    """主测试函数"""
    print("🚀 开始测试 Home Assistant SYMI双向同步集成 v2.1.2")
    print("=" * 60)
    
    tests = [
        test_manifest_json,
        test_init_file,
        test_config_flow,
        test_translations,
        test_version_consistency
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！集成已准备就绪。")
        return True
    else:
        print("⚠️  部分测试失败，请检查上述错误。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)