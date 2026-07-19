# payclip — 薪资管理工具

> 面向 10–20 人小微企业 / 财税工作室的**多租户 SaaS 薪资管理一体化系统**
> 覆盖「客户 → 业务 → 账单 → 收款 → 核对 → 提成 → 薪资」全链路，PC + H5 双端协同。

---

## ✨ 项目简介

payclip 解决小微企业三类核心痛点：

| 痛点 | 解决方案 |
|------|---------|
| 多成分薪资（底薪 + 服务/销售/一次性提成 + 欠费扣款 + 补回）手工算易错 | 提成计算引擎自动算三种提成 + 欠费/补回 + 底薪 → 应发薪资 |
| 收款登记、核对、内账校验分散 | 收款全生命周期管理（填报 → 核对 → 校验锁定 → 计算） |
| 客户/供应商/业务数据无统一台账 | 统一客户/供应商/业务台账 + 经营报表 + Excel 导出 |

**产品形态：**
- **PC Web**：Vue3 + Element Plus（主管/财务/老板用），开发端口 `5173`
- **H5 移动端**：Vue3 + Vant（员工填报收款、查薪资，微信内可分享），开发端口 `5174`
- **后端**：FastAPI + MySQL 8.0（多租户共享表 + `tenant_id` 隔离），端口 `8000`

---

## 🧱 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | FastAPI 0.110 | 异步高性能，自动 OpenAPI 文档 |
| ORM / 迁移 | SQLAlchemy 2.0 + Alembic | 参数化查询，防 SQL 注入 |
| 数据库 | MySQL 8.0 | utf8mb4，支持 JSON / CTE / 窗口函数 |
| 认证 | JWT (python-jose) + bcrypt | 无状态认证，密码哈希存储 |
| 定时任务 | APScheduler | 每月 1 日自动生成账单 |
| 文件处理 | openpyxl + pandas | Excel 导入/导出 |
| PC 前端 | Vue 3 + Element Plus + Vite + Pinia + ECharts | PC 优先 |
| 移动端 | Vue 3 + Vant + Vite + Pinia | 375px 起 H5 适配 |
| 部署 | Uvicorn + Nginx / Docker Compose | ASGI + 反向代理 |

> 所有界面强制中文（含日期选择器等组件）。

---

## 🏗 系统架构

```mermaid
flowchart LR
    subgraph Client["客户端"]
        PC["PC Web<br/>Vue3 + Element Plus"]
        H5["H5 移动端<br/>Vue3 + Vant"]
    end

    subgraph Gateway["网关层"]
        NGX["Nginx<br/>静态托管 + 反向代理"]
    end

    subgraph Backend["后端服务"]
        API["FastAPI<br/>REST API + JWT 鉴权"]
        SCHED["APScheduler<br/>月度账单生成"]
        ENGINE["提成计算引擎<br/>服务/销售/一次性 + 欠费/补回"]
    end

    subgraph Storage["存储层"]
        DB[("MySQL 8.0<br/>共享表 + tenant_id")]
        FS["uploads/<br/>收款截图"]
    end

    PC --> NGX
    H5 --> NGX
    NGX --> API
    API --> ENGINE
    SCHED --> API
    API --> DB
    API --> FS
```

### 多租户隔离机制

```mermaid
flowchart TD
    REQ["请求到达"] --> AUTH["JWT 解析<br/>提取 tenant_id / role"]
    AUTH --> CHECK{"role == super_admin?"}
    CHECK -- "是" --> ALL["tenant_id = NULL<br/>可跨租户查询"]
    CHECK -- "否" --> FILTER["所有业务查询<br/>自动 filter(tenant_id=current)"]
    ALL --> BIZ["执行业务逻辑"]
    FILTER --> BIZ
    BIZ --> RESP["返回结果"]
```

---

## 📁 项目结构

```
payclip/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口 + 路由（建表、超管初始化）
│   │   ├── config.py        # 配置（JWT、上传、数据库）
│   │   ├── database.py      # SQLAlchemy 引擎 / 会话
│   │   ├── core/            # 认证、权限装饰器
│   │   ├── models/          # ORM 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── routers/         # 路由模块
│   │   ├── services/        # 业务服务层
│   │   ├── dal/             # 数据访问层
│   │   └── utils/           # 工具函数
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # pytest 测试
│   └── requirements.txt
├── frontend/                # PC Web（Vue3 + Element Plus）
│   ├── src/
│   │   ├── api/             # axios 接口封装
│   │   ├── views/           # 页面
│   │   ├── components/      # 通用组件
│   │   ├── layout/          # 布局
│   │   ├── router/          # 路由
│   │   ├── stores/          # Pinia 状态
│   │   └── utils/
│   ├── dist/                # 构建产物
│   └── package.json
├── mobile/                  # H5 移动端（Vue3 + Vant）
│   ├── src/
│   │   ├── api/
│   │   ├── views/
│   │   ├── router/
│   │   ├── stores/
│   │   └── utils/
│   └── package.json
├── uploads/                 # 收款截图上传目录
├── 需求规格说明书.md
├── 整体设计文档.md
├── 数据库设计文档.md
├── 接口设计文档.md
├── 业务流程设计文档.md
├── 技术方案文档.md
├── 测试用例文档.md
└── 交付与本地运行说明.md
```

---

## 🔄 核心业务流程

```mermaid
flowchart TD
    subgraph INIT["初始化"]
        A1["录入客户 / 业务"] --> A2["系统按账期生成账单 Bill"]
        A2 --> A3{"有预付余额?"}
        A3 -- 有 --> A4["自动抵扣预付"]
        A3 -- 无 --> A5["等待收款"]
        A4 --> A5
    end

    subgraph PAY["收款阶段"]
        B1["员工填报收款<br/>关联客户+账单(可多账单)"] --> B2["上传截图凭证"]
        B2 --> B3["选核对人 / 标记公私用"]
        B3 --> B4["差额自动转入预付"]
        B4 --> B5["状态: pending"]
    end

    subgraph VERIFY["核对阶段"]
        C1["主管看待核对列表<br/>(只显示分配给自己)"] --> C2{"核对"}
        C2 -- 通过 --> C3["approved<br/>更新 Bill.paid_amount"]
        C2 -- 驳回 --> C4["填驳回原因<br/>员工改后重提"]
        C4 --> C1
    end

    subgraph CALC["计算阶段"]
        D1["财务点「校验并计算当月」"] --> D2["锁定当月收款"]
        D2 --> D3["提成引擎: 服务15% / 销售15% / 一次性20%<br/>+ 欠费扣5% + 补回"]
        D3 --> D4["按员工汇总 → MonthlySalary"]
        D4 --> D5["状态: locked"]
    end

    subgraph REPORT["报表阶段"]
        E1["个人核对表 (SELF)"] --> E2["管理者全部薪资 (ALL)"]
        E2 --> E3["经营报表: 区域 / 费用 / 趋势"]
        E3 --> E4["Excel 导出"]
    end

    INIT --> PAY --> VERIFY --> CALC --> REPORT
```

### 三种提成类型

| 类型 | 计算基数 | 比例 | 计提时点 | 欠费规则 | 12 月窗口 |
|------|---------|------|---------|---------|-----------|
| 服务提成 | 月费 | 15% | 服务当月 | 扣 5% | 无 |
| 销售提成 | 收款金额 | 15% | 收款当月 | 无 | 有（新客首月起的 12 个自然月） |
| 一次性业务提成 | 收入 − 成本（毛利） | 20% | 业务完成月 | 未收款扣 5% | 无 |

### 套餐与定价

| 套餐 | 价格 | 功能 | 期限 |
|------|------|------|------|
| 试用版 | ¥1 | 全功能 | 30 天 |
| 月付版 | ¥20/月 | 全功能 | 30 天（可续） |
| 年付版 | ¥199/年 | 全功能 | 365 天（可续） |

套餐状态机：`注册（凭注册码）→ active → expired_readonly（只读 30 天）→ soft_deleted（可恢复）`

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0

### 1. 准备数据库

```bash
mysql -e "CREATE DATABASE IF NOT EXISTS salary_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS 'salary'@'localhost' IDENTIFIED BY 'salary123';"
mysql -e "GRANT ALL PRIVILEGES ON salary_manager.* TO 'salary'@'localhost'; FLUSH PRIVILEGES;"
```

默认连接串：`mysql+pymysql://salary:salary123@localhost:3306/salary_manager`
可用环境变量 `DATABASE_URL` 覆盖。

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 启动时**自动建表**并创建默认超级管理员。
- 健康检查：`GET http://localhost:8000/api/health` → `{"status":"ok"}`
- API 文档：`http://localhost:8000/docs`

### 3. 启动 PC 前端

```bash
cd frontend
npm install
npm run dev
# 开发服务器：http://localhost:5173 （Vite 已代理 /api → localhost:8000）
```

或直接托管已构建产物：将 `frontend/dist/` 内容放到 Nginx 根目录即可。

### 4. 启动 H5 移动端

```bash
cd mobile
npm install
npm run dev
# 开发服务器：http://localhost:5174 （Vite 已代理 /api /uploads → localhost:8000）
```

移动端采用 **Vue3 + Vant 4.x** 构建，默认绑定 `0.0.0.0:5174`，支持手机在局域网内访问：
- 手机访问地址：`http://<电脑局域网IP>:5174`
- Vite 代理配置：`/api` 和 `/uploads` 请求自动转发至后端 `http://127.0.0.1:8000`
- 认证方式：JWT Token 存储在 `localStorage`，与 PC 端共用同一后端 API

**移动端功能模块：**
| 模块 | 说明 |
|------|------|
| 工作台 | 数据概览 |
| 收款填报 | 员工提交收款记录 |
| 收款核对 | 主管审核收款 |
| 我的薪资 | 查看个人薪资明细 |
| 客户列表 | 查看客户信息 |
| 账单列表 | 查看账单状态 |
| 我的 | 个人信息与设置 |
| 邀请员工 | 租户管理员邀请新员工 |

### 5. 默认账号

| 角色 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| 平台超管 | `admin` | `admin123` | 跨租户全权限，用于生成注册码、管理租户 |

> 普通租户管理员通过**注册码**注册，员工通过**邀请链接**自助加入。

---

## 🐳 Docker 部署

```bash
# 一键启动 MySQL + 后端 + Nginx
docker-compose up -d

# 初始化数据库迁移
docker-compose exec backend alembic upgrade head

# 创建超管（首次启动已自动创建，可跳过）
docker-compose exec backend python -m app.create_admin
```

---

## 🧪 测试

```bash
cd backend
pytest tests/ -v
```

覆盖：登录认证、端到端业务流（客户→业务→账单→收款→核对→提成→薪资）、欠费扣款与补回逻辑、SELF 数据范围权限隔离。

---

## 🔐 权限模型

**三级角色体系：**

| 角色 | tenant_id | 权限 |
|------|-----------|------|
| `super_admin` | NULL | 管理所有租户、生成注册码、手动开通付费、全局报表 |
| `tenant_admin` | NOT NULL | 本租户全功能 + 邀请员工 + 分配权限 |
| `employee` | NOT NULL | 按 `permissions` 数组限定 |

**功能权限点：** `payment:submit` / `payment:verify` / `salary:view` / `salary:manage` / `report:view` / `admin:config` / `tenant:admin`

**数据范围：** `SELF`（仅看自己 + 自己作为负责人的业务）/ `ALL`（看全部）

---

## 📚 设计文档索引

| 文档 | 内容 |
|------|------|
| [需求规格说明书.md](./需求规格说明书.md) | SRS v3，含多租户 SaaS 改造、套餐定价、注册码机制 |
| [整体设计文档.md](./整体设计文档.md) | 11 步设计流程，系统总体架构 |
| [数据库设计文档.md](./数据库设计文档.md) | 全表结构、索引、约束 |
| [接口设计文档.md](./接口设计文档.md) | REST API 接口契约 |
| [业务流程设计文档.md](./业务流程设计文档.md) | 端到端流程图、单据状态机 |
| [技术方案文档.md](./技术方案文档.md) | 缓存/定时任务/鉴权/日志/部署 |
| [测试用例文档.md](./测试用例文档.md) | 关键测试用例 |
| [交付与本地运行说明.md](./交付与本地运行说明.md) | 交付清单与运行指引 |

---

## 🗺 路线图

**Phase 1（MVP，当前版本）**
- ✅ 客户/供应商/业务管理（含 Excel 导入）
- ✅ 收款管理（逐笔填报 + 批量 CSV 导入 + 核对）
- ✅ 提成计算引擎（三种 + 欠费/补回，不含超额阶梯）
- ✅ 薪资核算（应发）+ 个人核对表
- ✅ 内账校验锁（最近月可撤销）
- ✅ 经营报表 + Excel 导出
- ✅ 多租户隔离 + 注册码 + 套餐状态机 + 三级角色
- ✅ PC 端汉化 + H5 移动端

**Phase 2（后续）**
- ⏳ 超额阶梯奖励计算（超额累进）
- ⏳ 年终奖 / 个税社保代扣
- ⏳ OCR（截图识别 + 流水截图导入）
- ⏳ 操作日志审计
- ⏳ PDF 导出
- ⏳ 微信小程序
- ⏳ 在线支付接入（微信支付 / 支付宝）

---

## 📄 License

内部项目，未开源。
