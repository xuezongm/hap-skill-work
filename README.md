# HAP Skill Work（明道云 AI 技能套件）

本仓库整合了面向明道云（HAP）低代码平台的全生命周期 AI Agent 技能（Skills），涵盖应用设计与搭建、存量应用演进与逆向重构、高难度测试用例生成以及技能规范治理。

---

## 📦 技能套件清单

| 技能名称 | 目录 | 定位与核心能力 |
| :--- | :--- | :--- |
| **hap-app-copilot** | [`hap-app-copilot/`](./hap-app-copilot) | **HAP 应用与数据全生命周期助手**：从 0 到 1 架构规划与搭建、存量应用渐进式修改/重构，以及日常业务数据查询统计、记录增删改、审批待办处理与流程触发。 |
| **hap-testcase-generator** | [`hap-testcase-generator/`](./hap-testcase-generator) | **场景化测试用例批量生成器**：基于真实业务口吻（存量刷数、离职交接、软删除、极简指令）批量生成高仿真、具有挑战性的修改与搭建用例集。 |
| **skill-maintainer** | [`skill-maintainer/`](./skill-maintainer) | **Skill 维护与内容治理规范**：审查和规范 Agent/Codex Skill 的文件分工、单一事实源、引用关系、加载层级及内容粒度。 |

---

## 🚀 快速上手与集成

### 1. 本地安装到 Agent / Codex / Claude Code
将对应的技能目录软链接或复制到全局技能配置目录（如 `~/.gemini/config/skills/` 或各 Agent 的技能根目录）：

```bash
# 示例：安装 hap-app-copilot 到全局技能库
ln -s "$(pwd)/hap-app-copilot" ~/.gemini/config/skills/hap-app-copilot
```

### 2. 依赖环境与 MCP
- **MCP 服务**：`hap_meihua_mcp` / `hap_personal_mcp` / `hap_sandbox_mcp`
- **运行环境**：Python 3.10+（部分预计算与校验辅助脚本使用标准库）

---

## 维护文档

- [Copilot 与 AgentService 的共享内容及同步规则](./skill-maintainer/references/hap-copilot-sync.md)：共享镜像清单、本地适配文件、权威位置、版本对照、同步命令及未覆盖范围。供仓库维护者使用，不属于 `hap-app-copilot` 的业务使用入口。
- [Copilot 发布包维护](./skill-maintainer/references/copilot-release.md)：依赖与许可证说明、发布清单检查、杂项排除及 ZIP 打包方式。

## 📄 License
MIT License
