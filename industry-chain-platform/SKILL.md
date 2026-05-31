---
name: industry-chain-platform
description: "产业链分析可视化平台——已集成到日晷Sundial。398节点全产业超级图谱，10大分组。节点名=同花顺板块名 或 百川盈孚原材料品种名。数据唯一真相源：macro-industry.json。"
version: 3.2.0
author: 新闻星期五
---

# 产业链分析平台（日晷集成版）

已完全内嵌到日晷 Sundial（端口 8100），不再独立运行。原 `/root/projects/industry-chain/` 已删除。

**核心规则：只有同花顺有独立概念/行业板块的产业环节才能成为节点。节点名 = THS 板块名。**

## 项目位置

**静态数据文件（macro-industry.json）在 `data/industry_data/`，不在 src 下。**

```
sundial/
├── main.py                    # /api/page/industry-chain, /api/industry/{id}
├── data/industry_data/        # JSON 数据（已迁移至此）
│   ├── index.json            # 行业注册（仅 macro-industry）
│   └── macro-industry.json   # 全产业图谱（398节点+480边）
├── industry_analyses/        # 深度分析 Markdown（当前空）
└── dashboard/
    ├── static/pages/industry-chain.html   # 页面模板
    ├── static/js/app.js                   # renderIndustryChain() + D3
    └── static/css/app.css                 # 产业链样式（浅色主题）
```

**迁移已完成**（2026-05-31）：`src/sundial/industry_data/` → `data/industry_data/`，`_INDUSTRY_DATA` 路径已更新为 `../../data/industry_data`。

## API 接口（日晷 :8100）

| 路由 | 说明 |
|------|------|
| `GET /api/page/industry-chain` | index.json |
| `GET /api/industry/macro-industry` | 完整图谱数据（132节点+235边） |
| `GET /api/industry/{id}/analysis/{file}` | 深度分析 Markdown→HTML |
| `GET /#industry-chain` | 日晷前端 tab（进来直接进图，无列表页） |

## 10 大分组

| 分组 | 颜色 | 节点数 | 覆盖范围 |
|------|------|:---:|------|
| ⛽能源电力 | `#f0883e` | 11 | 石油加工贸易、天然气、煤炭开采加工、页岩气、核电、电力、绿色电力、风电、智能电网、储能、特高压 |
| 🏭化工材料 | `#bc8cff` | 8 | 煤化工概念、氟化工概念、磷化工、有机硅概念、硅能源、化肥、碳纤维、工业母机 |
| 🔩金属矿产 | `#9ca3af` | 6 | 钢铁、金属铜、金属镍、稀土永磁、盐湖提锂、锂电池概念 |
| 🌾农业食品 | `#3fb950` | 5 | 粮食概念、养殖业、猪肉、白酒、食品加工制造 |
| 🚗汽车交通 | `#58a6ff` | 8 | 汽车整车、新能源汽车、汽车零部件、汽车芯片、充电桩、无人驾驶、物流、港口航运 |
| 💻半导体 | `#06b6d4` | 10 | 芯片概念、第三代半导体、光刻胶、光刻机、PCB概念、先进封装、共封装光学(CPO)、存储芯片、5G、消费电子 |
| 🧠AI智能 | `#a855f7` | 7 | 算力租赁、数据中心(AIDC)、人工智能、液冷服务器、人形机器人、机器人概念、减速器 |
| ☀️新兴能源 | `#eab308` | 5 | 光伏概念、钙钛矿电池、可控核聚变、氢能源、固态电池 |
| 🛩️低空航天 | `#ec4899` | 8 | 低空经济、飞行汽车(eVTOL)、无人机、商业航天、大飞机、军工、军工电子、卫星导航 |
| 🧵纺织 | `#f472b6` | 1 | 纺织 |
| 🧱建材 | `#d97706` | 1 | 建材 |
| 🧪橡塑 | `#84cc16` | 1 | 橡塑 |
| 🛒塑料制品 | `#22d3ee` | 1 | 塑料制品 |
| ⛏️原材料 | `#78716c` | 60 | 原油、液化天然气、焦炭、炼焦煤、液化气、燃料油、石脑油、无烟煤、石油焦、二甲醚、电解铜、电解铝、镍、钴、铅、锌、锡、白银、金属硅、碳酸锂、镨钕氧化物、氧化镝、萤石、铁矿石、螺纹钢、热轧卷板、不锈钢、硅铁、锰硅、甲醇、尿素、纯碱、乙二醇、磷酸、硫酸、纯苯、苯乙烯、PX、醋酸、氯化钾、磷酸一铵、磷酸二铵、EVA、PP、LLDPE、PVC、天然橡胶、丙烯腈、PTA、皮棉、涤纶短纤、沥青、玉米、豆粕、白糖、生猪、棕榈油、大豆、鸡蛋、菜籽油 |

## 节点规则（铁律）

1. **节点名必须是同花顺板块名** — 同花顺有的概念/行业板块才能建节点。没有独立板块的产业环节（如"丝杠""电子布""工业硅"）不能独立成节点。
2. **节点 ID 直接使用 THS 板块名** — 如 `"光刻胶"`（概念）、`"汽车整车"`（行业），保留原名后缀如 `"(CPO)"`。
3. **每个节点天然有成分股** — 从 `data/cache/raw_sectors.json` 倒排索引取。不人工填 leader。

## 关键跨组链路

- 煤炭开采加工→电力/钢铁/煤化工概念（传统能源枢纽）
- 硅能源→光伏概念/有机硅概念（硅基材料双路径）
- 锂电池概念→新能源汽车/储能（锂下游双应用）
- 芯片概念→光刻胶/光刻机/先进封装/存储芯片（半导体子环节）
- 人工智能→算力租赁/数据中心/人形机器人/机器人概念（AI 赋能）
- 数据中心(AIDC)→电力（AI 巨量电力消耗）
- 钢铁→汽车零部件/机器人概念、金属铜→电力/PCB概念（金属跨行业供应）
- 光伏概念→绿色电力、储能→智能电网（新能源接入）

## 待办：原材料价格接入

原材料节点已作为 `⛏️原材料` 分组落地到图谱中。数据源已切换为百川盈孚（见 `commodity-data-source` skill）。

| 顺序 | 数据源 | 覆盖品种 | 方式 |
|:---:|--------|---------|------|
| 1 | mootdx 期货行情 | 原油/焦炭/焦煤/液化气/铜/铝/镍/白银/硅/碳酸锂/铁矿石/螺纹钢/热卷/不锈钢/硅铁/锰硅/甲醇/尿素/纯碱/乙二醇/橡胶/玉米/豆粕/白糖/生猪/棕榈油 | 已有 mootdx，直接接 |
| 2 | 百川盈孚 | 非期货品种（硫酸/液碱/盐酸/废钢/石墨电极/次氯酸钠等 200+ 垂直行业） | Playwright + cookie 登录 |

## 数据现状

- **图谱骨架**：398 节点、480 边、0 孤立节点。数据唯一真相源：`macro-industry.json`。
- **节点来源**：产业板块来自同花顺概念/行业板块；原材料节点来自百川盈孚产业链（见 `commodity-data-source` skill）。禁止引用外部绝对路径，全部数据在项目内部。
- **数据铁律**：禁止 mock。数据源失败返回空，不降级填充。
- **图谱文件路径**：`data/industry_data/macro-industry.json`（根目录 data/，不是 src/sundial/data/）
- **旧路径**（过渡期）：`src/sundial/industry_data/macro-industry.json`
- **日晷端口**：8100（`uvicorn sundial.main:app --host 0.0.0.0 --port 8100`）
- **浏览器强刷**：app.js 带 `?v=N` 缓存 busting 参数。调查渲染异常时先确认浏览器没有缓存旧版（Mac: Cmd+Shift+R，PC: Ctrl+Shift+R）。检查方法：在浏览器 Console 执行 `fetch('/api/industry/macro-industry').then(r=>r.json()).then(d=>console.log(d.nodes.find(n=>n.id.includes('汞'))))` 验证 API 数据是否含目标节点。
- **市值数据**：mootdx `finance()` 不支持批量（只接受单个 string），无法一次拉全市场。找龙头仍需人工维护或接受逐只查询的成本。

## 添加新 group 时的色值同步规则

百川行业链页面有 9 个产业频道（汽车/水处理/医药/光伏/电池/钢铁/造纸/轮胎/饲料），每个频道下的品种 group 值是百川分类（如"光伏行业相关产业链"），**不在预设 10 色图例组中**。

在 macro-industry.json 中新增 group 值时，必须同步更新两处，否则节点渲染为灰色：

1. **`app.js` 中的 `groups` 字典**：给新 group 分配一个 hex 颜色，否则 `getNodeColor` 走 fallback 返回 `#9ca3af`（灰色）
2. **`industry-chain.html` 中的图例 Legend**：在 sidebar 同步添加图例项，否则用户看不到该 group 的图例

**已知的未映射 group**（来自百川行业链 9 频道）：
- 光伏行业相关产业链 / 医药原辅料产业链 / 水处理原辅料产业链 / 汽车原料辅料产业链 / 电池原辅料产业链 / 造纸原辅料产业链 / 钢铁原辅料产业链 / 饲料添加剂产业链 / 🛞 轮胎

处理方式（二选一）：
- **方案 A**：给每个 group 分配独立颜色（增加图例复杂度）
- **方案 B**：将这些百川分组统一映射到已有分组（如 ⛏️原材料），在 summary 里注明百川分类来源

## 新增节点必须包含 `r` 字段（⚠️铁律）

节点半径 `r` 决定 D3 力导向图中的节点渲染尺寸。新增节点时不写 `r` 会导致 `forceSimulation` tick 时节点 `r=undefined`，渲染异常。

`r` 取值规则：
- 核心节点（如钢铁、汽车零部件、医药中间体）：r = 18-26
- 中等节点（如聚丙烯、电解铜）：r = 13-17
- 边缘/末端节点（如炼金）：r = 9-12

验证脚本：
```python
# 检查缺 r 字段的节点
import json
with open('macro-industry.json') as f:
    macro = json.load(f)
no_r = [n['id'] for n in macro['nodes'] if 'r' not in n]
print(f"缺r字段节点: {no_r}")
# 输出应为空
```
- **市值数据**：mootdx `finance()` 不支持批量（只接受单个 string），无法一次拉全市场。找龙头仍需人工维护或接受逐只查询的成本。

## 成分股数据源

数据链路：`q.10jqka.com.cn` 板块 AJAX → Cookie v_code → 成分股 HTML table → 倒排→正排。

详细参考：`a-stock-data-apis` skill 中「同花顺 AJAX 直抓」章节（Cookie v_code、每请求刷新、分页上限 100、批量策略）。

## 样式规则（铁律）

图谱容器必须在日晷设计系统中统一：
- 容器背景：`var(--surface)`，边框：`var(--border)`
- 文字：`var(--fg)` / `var(--muted)`
- 连线：`#d1d5db`（浅灰），高亮：`#f59e0b`（橙）
- 节点颜色保留分组色（9 组各有专属色），stroke 白色
- 图例/tooltip/面板统一用日晷 card 样式

**禁止保留暗色主题**（`#0d1117` 等），必须适配日晷浅色系。

## 节点 JSON 结构（API 响应 vs 图谱文件）

**图谱文件** `macro-industry.json` 节点结构：
```json
{
  "id": "电解铜",
  "group": "⛏️原材料",
  "r": 17,
  "summary": "...",
  "futures_code": "cu",
  "society_category": "有色",
  "leaders": [],
  "baiinfo_source": "baiinfo"       // 仅百川来源节点有
}
```

**API 响应** `/api/industry/macro-industry` 会额外附加：
```json
{
  "id": "电解铜",
  "group": "⛏️原材料",
  "r": 17,
  "summary": "...",
  "futures_code": "cu",
  "society_category": "有色",
  "leaders": [],
  "baiinfo_source": "baiinfo",
  "links": [],                      // 部分节点有此字段（来源数据自带的边），API 读取后过滤
  "source": "baiinfo",              // 同 baiinfo_source 别名
  "has_analysis": false             // API 自动注入，是否关联深度分析 Markdown
}
```

**新增节点时必须包含 `r` 字段**：核心节点 18-26，中等 13-17，边缘 9-12。新节点不写 `r` 会导致渲染异常（D3 tick 时节点 r=undefined）。

**百川盈孚来源判断**：节点有 `baiinfo_source` 字段 = 来自百川产业链数据。纯产业板块节点无此字段。

- `r`：核心节点 18-26，中等 13-17，边缘 9-12
- `futures_code`：期货合约代码（mootdx 接入用，仅原材料节点有；非期货品种为 null）
- `society_category`：生意社分类归属（能源/有色/钢铁/化工/橡塑/纺织/建材/农副），仅原材料节点有

## 边方向规则（铁律）

source→target = **供应链上游→下游方向**（原材料→加工→终端应用）。不是"需求拉动方向"，不是"技术溢出方向"。

正确示例：
- 电力→充电桩（电力是上游能源，充电桩耗电）
- 芯片概念→军工电子（芯片是上游元器件，军工是下游应用）
- 稀土永磁→人形机器人（稀土是原材料，机器人是成品）
- 智能电网→充电桩（电网是上游基础设施）

**常见方向错误**（审计时必须逐条验证）：
- 把需求拉动当成供应链方向（❌新能源汽车→充电桩 看起来"新能源车需要充电桩"但对供应链来说充电桩是基础设施→上车）
- 把应用端当成上游（❌军工电子→芯片概念 实际上芯片→军工电子）
- 电力节点永远是上游，不可能"某节点→电力"

## 页面交互行为

**节点悬停**：浮动 tooltip 显示节点名 + 分组 + summary

**节点点击**：三个效果同时触发：
1. tooltip 隐藏（避免与面板重叠）
2. 右侧面板弹出节点详情（id、分组、龙头公司、summary、涟漪影响的下游列表）
3. 图谱高亮分离三色：
   - 被点击节点：金色光晕（`.clicked`，stroke #f59e0b + glow）
   - 涟漪下游节点：青色高亮（`.ripple`，stroke #06b6d4）
   - 链路：直接出边橙色（`.highlight`），涟漪区域青色（`.ripple-link`）
   - 其余节点：变暗 8% 透明度

**搜索**：输入关键词后自动匹配节点 ID，匹配成功即应用与点击相同的三色高亮效果。未匹配到则只 dim 不匹配节点。

**点击空白/关闭按钮**：重置所有高亮、隐藏面板。

**节点漂移到屏幕外：**
- 原因：`forceCenter` 强度太弱（<0.1），节点数 >50 时大部分节点被推出 SVG 可视区
- 修复：`forceCenter(W/2, H/2).strength(0.2)` — 最小 0.2
- 同时必须设置 `alphaDecay(0.02)` 让模拟在合理时间内收敛

**null reference 报错：**
- 原因：含 `dateInput` 等元素的页面模板（如 daily-replay）在产业链 tab 页不存在，但 JS 中写死了对它们的引用
- 修复：所有 renderXxx 函数在访问 DOM 前加空值守卫：`if (!dateInput) return;`

**D3 节点用 `<g transform>` 而非 `<circle cx/cy>`：**
- 图谱渲染用 `node.attr('transform', d => 'translate(...)')` 定位节点组
- `<circle>` 元素不需要 cx/cy 属性，它们在组内默认位于 (0,0)
- 浏览器 console 检查时应该查 `<g>` 的 transform 属性，不是查 `<circle>` 的 cx

## 原材料节点审计铁律

**数据全量提取，不要预筛选：** 生意社页面有 5032 个品种（化工类 4774 个）。不要一开始就凭主观判断挑"大宗商品级"品种——必须先提取完整目录保存到 commodity_catalog.json，再由 subagent 逐条筛选。预筛选会导致大量遗漏（本次会话第一次筛选只出了 34 个，实际应为 60 个）。

**从 commodity_selection.json 出发建节点建边：** 每次修改原材料节点，必须从 commodity_selection.json 中的 targets 字段来确定边。禁止跳过中间文件直接改图谱。这保证了图谱中的原材料节点与生意社数据源之间的可追溯性。

**边方向易错点（审计专项）**：\n- `[x]→电力` 几乎永远是错的——电力是上游能源，只有 `电力→[x]` 才对\n- `[需求端]→[供应端]` 方向是需求拉动视角，在供应链图谱中应反转为 `[供应端]→[需求端]`\n- 原材料节点出边方向严格为 `原材料→板块`，不能出现 `板块→原材料`\n- 本次会话发现的错误示例：❌新能源汽车→充电桩 ✓充电桩→新能源汽车；❌军工电子→芯片概念 ✓芯片概念→军工电子；❌充电桩→电力 ✓电力→充电桩\n\n## 常见操作错误\n\n- **不要重复拉 THS API**：`data/cache/raw_sectors.json` 已经包含 465 个板块的倒排索引，grep 即可验证板块存在性。本次会话错误地调了 THS API 去拉板块列表，浪费了 token。\n- **原材料数据走管道**：生意社页面 → Playwright 浏览器过反爬 → commodity_catalog.json（全量）→ subagent 筛选 → commodity_selection.json（入选）→ subagent 建节点建边 → macro-industry.json。每次修改必须走完整管道。\n- **审查只能用 subagent**：所有图谱审查（节点/边/描述/完整性）必须通过 delegate_task 启动 subagent 执行，禁止自己直接审查。审查结果需逐条验证后才能接受。

**多轮审计流程：**
1. Subagent A 做数据提取/修改
2. Subagent B 审查 A 的结果，发现问题反馈给 A
3. 循环直到 Subagent B 无新问题
4. 最后一轮 Subagent 验证页面渲染 + API 响应

**审计项目：**

1. **边方向**：每条边的 source→target 是否符合"原材料→加工→终端"的供应链方向
2. **分组合理**：节点 group 是否符合其产业属性（如工业母机≠金属矿产，5G 放在💻半导体可接受因为芯片是核心上游）
3. **描述质量**：summary 需用大白话说清这个板块是**做什么的**（不是行业术语堆砌，不是投资建议），至少 30 字
4. **孤儿节点**：每个节点至少 2 条边，0 条边的节点直接删除
5. **重复边**：不允许 source+target 完全相同的重复
6. **断裂引用**：边引用的 source/target 必须存在于 nodes 中
7. **成分股数据不要重新拉 API**：图谱不需要每次从 THS API 重新拉板块——直接用本地 `data/cache/raw_sectors.json` 验证板块存在性即可。raw_sectors.json 是倒排索引，grep 确认板块名是否存在。

## 添加/修改节点

直接编辑 `industry_data/macro-industry.json`，无需重启日晷（每次请求实时读 JSON）。

**添加节点前先确认 THS 有对应板块**：grep raw_sectors.json 确认板块名存在即可，**不要调 THS API 重新拉**。

group 颜色在 `groups` 字典中定义。新增 group 时同步加颜色，并在 CSS legend 中保持同步。

完整筛选规则见 `references/ths-board-selection.md`。

## 迁移教训

- **迁移≠桥接**：数据文件复制到项目内部，路径用 `Path(__file__).parent`，不引用外部绝对路径
- **迁移后删除源**：原项目目录、端口、server.py 全部清理
- **样式必须统一**：集成到日晷后，所有 UI 组件必须用日晷设计系统变量，不保留原项目的独立主题
- **不要留列表页**：只有一个全产业图谱，不做行业选择或导航卡片
