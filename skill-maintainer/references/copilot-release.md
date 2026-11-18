# Copilot 发布包维护

公开包以 `hap-app-copilot` 为根目录，包含运行规则、脚本、界面配置、README 和 LICENSE。维护脚本与同步资料留在本仓库的 `skill-maintainer`，不进入公开包。

## 依赖和许可证

运行依赖在 Copilot README 的“使用依赖”中统一说明。宿主工具适配由 HOST_ADAPTER 定义；构建子代理和工具数量门禁由入口与构建工作流定义。依赖变化时更新相应权威文件及 README 摘要。

公开包须包含 MIT 许可证全文 LICENSE，README 链接到该文件。来源说明保留，不将来源说明等同于同步功能入口。

## 检查与打包

从仓库根目录执行 [打包脚本](../scripts/package_copilot.py)：

```bash
# 只检查并输出实际发布清单
python3 skill-maintainer/scripts/package_copilot.py

# 生成新的 ZIP，输出位置必须在 Skill 目录之外
python3 skill-maintainer/scripts/package_copilot.py --output /absolute/path/to/hap-app-copilot.zip
```

其他安装位置使用 `--skill-dir` 指定 Skill 根目录。脚本校验必需文件、运行时映射及章节归属；生成后校验 ZIP 内容清单和完整性，拒绝覆盖已有同名包。

发布目录、扩展名和排除项以脚本清单为准。`.DS_Store`、AppleDouble 文件、Python 缓存、虚拟环境、IDE 配置和本地运行产物被排除；未声明文件或目录、发布内容中的软链接会报错，维护者确认用途后再调整。不要直接压缩整个仓库，也不要依赖 `.gitignore` 自动过滤 ZIP。

发布前另运行 Skill 结构检查和相关行为回归；打包成功不代表业务功能验收通过。[发布与按需加载回归](../tests/test_copilot_release.py)覆盖杂项排除、缺件和软链接拒绝、规则切片及公共约束保留。
