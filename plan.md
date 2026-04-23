# ETF双框架分析工具 — 构建计划

## 项目概述
基于两份研究报告（缠论ETF量化操作策略 + 丁昶投资思想与ETF量化分析框架），构建一个可部署的Web分析工具。用户输入ETF代码后，工具以缠论角度给出趋势位置判断，并以丁昶分析框架进行评判。

## Stage 1 — 方法论提取与系统设计
- **缠论核心**：分型→笔→线段→中枢→走势类型→背驰判断→三类买卖点识别→多周期联立(日线/30min/5min)→共振评分
- **丁昶框架**：五维评估模型（股息质量30%、估值安全25%、盈利质地20%、资金驱动15%、宏观适配10%），去除银行股偏爱，泛化为通用ETF评估
- **系统架构**：Python FastAPI后端 + React前端，Ubuntu可部署

## Stage 2 — 后端开发 (vibecoding-general-swarm)
- FastAPI服务
- 数据获取：akshare免费接口
- 缠论引擎：集成CZSC库（高性能缠论计算）
- 丁昶评分：五维评分引擎
- 报告生成：综合分析报告

## Stage 3 — 前端开发 (vibecoding-webapp-swarm)
- React + TypeScript + Tailwind CSS
- ETF输入界面
- 缠论分析展示（分型、笔、中枢可视化，趋势位置，买卖点标注）
- 丁昶五维雷达图评分
- 综合分析报告展示

## Stage 4 — 集成与部署
- Docker容器化
- 部署验证

## 技术栈
- 后端：Python 3.10+, FastAPI, CZSC, akshare, numpy, pandas, ta-lib
- 前端：React 18, TypeScript, Tailwind CSS, Recharts, shadcn/ui
- 部署：Docker + Docker Compose
