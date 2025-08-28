<div align="center">

  <img src="docs/assets/images/RepoMaster.png" alt="RepoMaster Logo" width="600"/>
  

# RepoMaster: 基于GitHub仓库的自主任务解决框架

  <p style="margin: 10px 0;">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" />
    <img src="https://img.shields.io/badge/License-MIT-green.svg" />
    <img src="https://img.shields.io/badge/arXiv-2505.21577-red.svg" />
  </p>

  <p style="font-size: 15px; color: gray; margin-top: 4px;">
    🌐 <a href="README.md">English</a> | <a href="README_CN.md">中文</a>
  </p>

</div>

## 🚀 概述

RepoMaster 是一个革命性的自主代理框架，专门设计用于探索、理解和利用 GitHub 仓库来解决复杂的现实世界任务。与传统的从零开始生成代码的方法不同，RepoMaster 将 GitHub 上的开源仓库视为可组合的工具模块，通过智能搜索、层次化分析和自主探索来自动化地利用这些资源。

<img src="docs/assets/images/performance_01.jpg" alt="RepoMaster 效果图" style="background-color: #ffffff; display: block; margin: 0 auto;" />

---

## 🚀 快速开始

### 🛠️ 安装

**前置要求**：
```bash
python --version  # 需要Python 3.11+
```

**安装依赖**：
```bash
git clone https://github.com/QuantaAlpha/RepoMaster.git
cd RepoMaster
pip install -r requirements.txt
```

**配置API密钥**：
创建 `configs/.env` 文件：
```bash
# 设置默认API提供商 (openai, claude, deepseek, azure_openai)
# 如果未设置，将按优先级顺序使用第一个可用的提供商
DEFAULT_API_PROVIDER=openai
# OpenAI配置
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=openai_model

# Claude配置  
ANTHROPIC_API_KEY=your_claude_key
ANTHROPIC_MODEL=claude_model

# DeepSeek配置
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek_model

# Google Gemini配置
GEMINI_API_KEY=
GEMINI_MODEL=gemini_model

# 网络搜索API (深度搜索功能必需)
Serper_API_KEY=your_serper_key          # 用于Google搜索结果
JINA_API_KEY=your_jina_key              # 用于网页内容提取
```

### 🚀 运行RepoMaster

**前端模式（Web界面）**：
```bash
python launcher.py --mode frontend
# 访问：http://localhost:8501
```

**后端模式（推荐）**：
```bash
python launcher.py --mode backend --backend-mode unified
```

**Shell脚本快捷方式**：
```bash
bash run.sh frontend      # 前端模式
bash run.sh backend unified  # 后端统一模式
```

> 📘 **详细配置和高级选项，请参阅我们的[用户指南](docs/user-guide.md).**

## 🎯 快速演示

想象一下，您只需用自然语言描述一个任务，RepoMaster就能自动为您完成后续的一切：从找到最合适的GitHub仓库，到理解其复杂的代码结构，再到最终执行并完成任务！无论是简单的数据提取还是复杂的AI模型应用，RepoMaster都能胜任。

**示例任务**：
- **简单任务**："帮我从这个网页上抓取所有的产品名称和价格。"
- **复杂任务**："将这张人物照片转换成梵高油画风格。"

### 🎨 神经风格迁移演示

<table>
<tr>
<td align="center"><b>原始图像</b></td>
<td align="center"><b>风格参考</b></td>
<td align="center"><b>迁移结果</b></td>
</tr>
<tr>
<td><img src="docs/assets/images/origin.jpg" width="200px" /></td>
<td><img src="docs/assets/images/style.jpg" width="200px" /></td>
<td><img src="docs/assets/images/transfer.jpg" width="200px" /></td>
</tr>
</table>

**自动化工作流程**：
1. 🔍 **智能搜索**：在GitHub上搜索风格迁移相关仓库
2. 🏗️ **结构分析**：分析代码结构和处理流程
3. 🔧 **自主执行**：配置环境并处理图像
4. ✅ **任务完成**：生成结果，无需人工干预

### 🎬 完整执行演示 | [📺 YouTube演示](https://www.youtube.com/watch?v=Kva2wVhBkDU)

<div align="center">

https://github.com/user-attachments/assets/a21b2f2e-a31c-4afd-953d-d143beef781a

*RepoMaster自主执行神经风格迁移任务的完整过程*

</div>

---

## 🤝 贡献

我们欢迎社区贡献！请参阅我们的[贡献指南](CONTRIBUTING.md)。

### 开发环境设置
```bash
git clone https://github.com/your-org/RepoMaster.git
cd RepoMaster
pip install -e ".[dev]"
pre-commit install
```

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 📞 支持

- 📧 **邮箱**：quantaalpha.ai@gmail.com
- 🐛 **问题反馈**：[GitHub Issues](https://github.com/QuantaAlpha/RepoMaster/issues)
- 💬 **讨论**：[GitHub Discussions](https://github.com/QuantaAlpha/RepoMaster/discussions)
- 📖 **文档**：[完整文档](docs/)

---

## 🙏 致谢

感谢以下项目和社区的启发和支持：
- [AutoGen](https://github.com/microsoft/autogen) - 多代理框架
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) - 软件工程代理
- [SWE-Agent](https://github.com/princeton-nlp/SWE-agent) - GitHub问题解决代理
- [MLE-Bench](https://github.com/openai/mle-bench) - 机器学习工程基准

---

## 🌐 关于 QuantaAlpha

- QuantaAlpha 成立于 **2025 年 4 月**，由来自 **清华、北大、中科院、CMU、港科大** 等高校的教授、博士后、博士与硕士组成。  

🌟 我们的使命是探索智能的 **“量子”**，引领智能体研究的 **“阿尔法”** 前沿 —— 从 **CodeAgent** 到 **自进化智能**，再到 **金融与跨领域专用智能体**，致力于重塑人工智能的边界。 

✨ 在 **2025 年**，我们将在以下方向持续产出高质量研究成果：  
- CodeAgent：真实世界任务的端到端自主执行  
- DeepResearch：深度推理与信息检索增强  
- Agentic Reasoning / Agentic RL：智能体推理与强化学习  
- 自进化与协同学习：多智能体的自我进化与协作  

📢 欢迎对我们方向感兴趣的同学加入！  

🔗 团队主页：[QuantaAlpha](https://quantaalpha.github.io/)

---

## 📖 Citation

如果你觉得RepoMaster对你的研究有帮助，请引用我们的工作：

```bibtex
@article{wang2025repomaster,
  title={RepoMaster: Autonomous Exploration and Understanding of GitHub Repositories for Complex Task Solving},
  author={Wang, Huacan and Ni, Ziyi and Zhang, Shuo and Lu, Shuo and Hu, Sen and He, Ziyang and Chen, Jiaye and Lin, Yifu and Chen, Ronghao and Li, Xin and Jiang, Daxin and Du, Yuntao and Lyu, Pin},
  journal={arXiv preprint arXiv:2505.21577},
  year={2025},
  doi={10.48550/arXiv.2505.21577},
  url={https://arxiv.org/abs/2505.21577}
}
```

---

<div align="center">

**⭐ 如果 RepoMaster 对您有帮助，请给我们一个星标！**

Made with ❤️ by the QuantaAlpha Team

</div> 
