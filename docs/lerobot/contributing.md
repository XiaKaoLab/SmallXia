# 来源

https://hugging-face.cn/docs/lerobot/contributing

# 如何贡献 🤗 LeRobot

我们欢迎每个人参与贡献，并重视每一个人所做的贡献。代码并不是帮助社区的唯一方式。回答问题、帮助他人、积极沟通以及改进文档都具有极高的价值。

无论您选择以何种方式贡献，请务必遵守我们的 [行为准则](https://github.com/huggingface/lerobot/blob/main/CODE_OF_CONDUCT.md) 和 [AI 政策](https://github.com/huggingface/lerobot/blob/main/AI_POLICY.md)。

## 贡献方式

您可以通过多种方式进行贡献：

* **修复问题：** 解决 Bug 或改进现有代码。
* **新功能：** 开发新功能。
* **扩展：** 实现新的模型/策略、机器人或仿真环境，并将数据集上传到 Hugging Face Hub。
* **文档：** 改进示例、指南和 docstrings（文档字符串）。
* **反馈：** 提交关于 Bug 或期望新功能的 Ticket。

如果您不确定从哪里开始，请加入我们的 [Discord 频道](https://discord.gg/q8Dzzpym3f)。

## 开发环境搭建

要贡献代码，您需要搭建一个开发环境。

### 1. Fork 并 Clone

在 GitHub 上 Fork 该仓库，然后 Clone 您的 Fork 分支

```
git clone https://github.com/<your-handle>/lerobot.git
cd lerobot
git remote add upstream https://github.com/huggingface/lerobot.git
```

### 2. 环境安装

请参考我们的 [安装指南](installation.md) 来进行环境搭建和从源码安装。

## 运行测试与质量检查

### 代码风格 (Pre-commit)

安装 `pre-commit` 钩子，以便在提交代码前自动运行检查

```
pre-commit install
```

若要手动对所有文件运行检查：

```
pre-commit run --all-files
```

### 运行测试

我们使用 `pytest`。首先，请确保通过安装 **git-lfs** 来获取测试资源

```
git lfs install
git lfs pull
```

运行全套测试（这可能需要安装额外的依赖）

```
pytest -sv ./tests
```

或者在开发过程中运行特定的测试文件

```
pytest -sv tests/test_specific_feature.py
```

## 提交 Issue 和 Pull Request

请使用模板填写必要字段并提供示例。

* **Issues：** 请遵循 [Ticket 模板](https://github.com/huggingface/lerobot/blob/main/.github/ISSUE_TEMPLATE/bug-report.yml)。
* **Pull Requests：** 基于 `upstream/main` 进行 rebase，使用具有描述性的分支名（不要在 `main` 上工作），在本地运行 `pre-commit` 和测试，并遵循 [PR 模板](https://github.com/huggingface/lerobot/blob/main/.github/PULL_REQUEST_TEMPLATE.md)。

随后，LeRobot 团队的一名成员将审核您的贡献。

感谢您为 LeRobot 做出贡献！

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/contributing.md)