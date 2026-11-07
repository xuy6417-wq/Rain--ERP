Rain ERP

面向跨境电商团队的多店铺 ERP 管理系统，覆盖商品管理、供应商管理、采购管理、仓储库存及订单履约等核心业务。

项目介绍

Rain ERP 是一套专为跨境电商业务设计的管理系统，参考成熟跨境电商 ERP 的业务流程，帮助团队统一管理商品、供应链、采购和库存。

当前版本

Version：v0.5.1

当前版本重点完成采购管理、采购入库和库存流水功能。

已实现功能

1. 商品管理

* 商品 SPU / SKU 基础管理
* SKU 信息维护

2. 供应商管理

* 供应商信息管理
* 供应商采购报价管理

3. 采购管理

* 创建采购订单
* 单张采购单支持多个 SKU
* 采购数量、采购单价及金额自动计算
* 采购单提交和取消
* 采购状态管理
* 采购订单查询和筛选

4. 采购入库

* 按采购订单收货
* 支持部分入库
* 支持分批入库
* 自动累计采购入库数量
* 防止超量入库

5. 库存管理

* 仓库管理
* SKU 库存管理
* 库存人工调整
* 库存流水记录
* 按仓库和 SKU 查询库存流水

技术架构

模块	技术
前端	Next.js 14
UI	React 18
开发语言	TypeScript
后端	FastAPI
ORM	SQLAlchemy 2
数据验证	Pydantic 2
数据库	PostgreSQL 16
缓存	Redis 7
部署	Railway

项目目录

rain-mvp-v2/
├── apps/
│   ├── api/
│   │   └── app/
│   │       └── main.py
│   └── web/
│       ├── app/
│       │   └── procurement/
│       │       └── page.tsx
│       └── package.json
├── README.md
└── ...

核心 API

采购管理

方法	接口	说明
POST	/api/v1/purchase-orders	创建采购单
GET	/api/v1/purchase-orders	采购单列表
GET	/api/v1/purchase-orders/{id}	采购单详情
POST	/api/v1/purchase-orders/{id}/submit	提交采购单
POST	/api/v1/purchase-orders/{id}/cancel	取消采购单

采购入库

方法	接口	说明
POST	/api/v1/goods-receipts	创建收货入库单
GET	/api/v1/goods-receipts	收货记录列表

库存管理

方法	接口	说明
GET	/api/v1/inventory/movements	查询库存流水
POST	/api/v1/inventory/adjustments	库存人工调整

本地开发

后端

进入后端目录：

cd apps/api

安装依赖：

pip install -r requirements.txt

启动服务：

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API 地址：

http://localhost:8000

接口文档：

http://localhost:8000/docs

前端

进入前端目录：

cd apps/web

安装依赖：

npm install

配置环境变量：

NEXT_PUBLIC_API_URL=http://localhost:8000

启动前端：

npm run dev

访问：

http://localhost:3000

后续开发规划

v0.6

* 销售订单管理
* 多平台订单接入
* 订单处理工作台

v0.7

* 智能采购建议
* 安全库存预警
* 库存调拨

v0.8

* 多仓库管理完善
* 物流管理
* 发货履约管理

v1.0

* 多店铺统一管理
* 财务及利润分析
* 跨境电商完整业务流程

项目说明

本项目仍在持续开发中，当前版本为早期 MVP。

生产环境部署、数据库配置及前端完整构建需要在实际部署环境中进一步验证。

⸻

Rain ERP — Make Cross-border E-commerce Easier.
