# 每日AI工程化资讯分析

## 功能
- 每天自动获取 AI 工程化相关热门资讯
- 分析前3条（如未分析过）
- 对接 AS400 SDD 框架，提供优化建议
- 生成日报供确认

## 目录结构
```
daily-news/
├── daily_news_task.py    # 主任务脚本
├── analyzed_articles.json # 已分析记录（避免重复）
├── report_YYYY-MM-DD.md   # 每日报告
└── README.md
```

## 使用方式

### 本地运行
```bash
python daily-news/daily_news_task.py
```

### GitHub Actions
- **自动触发**: 每天 9:00 (北京时间)
- **手动触发**: workflow_dispatch

## 报告内容
1. **资讯概要**: 标题、来源、链接
2. **核心理念**: 资讯中的关键概念
3. **相关代码**: AS400 SDD 框架中对应的代码文件
4. **优化建议**: 基于资讯提出的框架优化点
5. **待确认修改**: 用户确认后实施的优化项

## 数据源
当前使用模拟数据，可接入：
- Hacker News API
- RSS feeds
- 自定义 API

## 状态追踪
- `analyzed_articles.json`: 记录已分析的资讯 ID
- 相同资讯不会重复分析
