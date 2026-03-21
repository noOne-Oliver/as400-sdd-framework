# 快速开始 (5 分钟)

## 1. 前置条件
- Python 3.10+

## 2. 安装依赖
```bash
./scripts/setup.sh
```

## 3. 运行 Demo
```bash
./scripts/demo.sh
```

## 4. 运行真实需求
```bash
./scripts/run_pipeline.sh examples/order_processing/requirement.txt
```

## 5. 常见问题
**Q: 如何切换到真实 LLM？**
修改 `config/pipeline.yaml` 中 provider 为 `ollama` 并设置 model。

**Q: 输出在哪里？**
输出默认生成在 requirement 文件同目录下（analysis/sdd/tests/code）。
