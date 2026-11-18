# 山荆蜂业 · 蜂场越冬弱群巡检

面向山荆蜂业9名蜂师、80箱定地蜂群，把巡箱异常提示、饲喂/换王执行、返回复查和主管关闭串成保群工作流。

现在蜂师用纸本记抬箱体重，王况写在箱盖，晚上再人工翻找异常：低体重变化难察觉、无王误当缺饲、喂料后没有复查。上游是现场 `shanjing_winter_20261117.csv` 巡检读数，本应用接管筛查与处置，下游主管据复查决定越冬状态，观察员查看箱况。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
# 启动自动seed；也可重复执行，保留人工修改
 docker compose exec -T backend python -m scripts.seed_demo
# 收尾删除本项目演示数据
 docker compose down -v --remove-orphans
```

前端 [localhost:18226](http://localhost:18226)，[后端API19226/docs](http://localhost:19226/docs)，PostgreSQL映射17726。

|角色/账号|权限|典型动作|
|---|---|---|
|admin / admin@shanjing.test|全部；维护箱况、最终关闭仅主管|核实蜂王、体重与蜂量后关闭处置|
|beekeeper / beekeeper@shanjing.test|巡检、筛查、计划、执行、复查，无最终关闭|登记换王执行，回来查看是否接受新王|
|viewer / viewer@shanjing.test|六页、全部领域记录与审计只读|查看越冬状态与处置依据|

密码均 `Hive2026!`，JWT有效8小时。数据库/签名默认配置用于本地演示。

## 多模块业务

- **蜂场箱位**：Hive含唯一code、site、queen_present、colony_frames、care_state。001–040东坡，041–080林缘。80格矩阵为编号箱位示意，不是地理坐标。主管编辑箱况；处置中禁止直接改王况/框数。
- **巡箱手记**：Visit保留体重、箱温、活动、余饲、巡检见王与框数。新的巡检同步当前Hive王况/框数。已有处置时不能另记巡检替换原始输入；记录不提供PUT覆盖。
- **弱群筛查**：每箱仅筛最新Visit，使用无标签IsolationForest异常分值；所有原始数值留在数据库。异常低分只提示核查，未见王无论是否异常都进入关注。
- **处置复查簿**：CareAction关联Visit，饲喂或换王。饲喂量0–3kg，饲喂须>0，换王饲喂量记0。planned→executed→rechecked→closed；执行与复查是独立动作。换王执行必须确认新王实际入箱，立即更新Hive.queen_present；复查如果仍无王会真实把Hive置false，主管拒绝关闭，需重新复查。

无王巡检误做饲喂后，复查将CareAction/Visit/Hive分别转needs_requeen，主管不能仅靠饲喂关闭；可据同一Visit新增换王处置，保留原饲喂记录，不覆盖历史。最终关闭须见王、体重不低于巡检、蜂量≥5框；关闭后CareAction=closed、Visit=closed、Hive=winter_ready，旧巡检变stale。已关闭处置不能改执行或复查。

## 无监督算法口径

`backend/fixtures/winter_reference.json`含100条无标签参考巡检，特征weight_kg、temperature、activity、feed_left。`IsolationForest(n_estimators=150,contamination=.15,random_state=42)`；score_samples越低越偏离参考，模型offset_是异常阈值，score<threshold标异常，decision_margin=score−threshold。固定参考中15/100低于阈值是设定比例，不是分类准确率。模型未使用王况/框数，未见王另由业务规则强制关注。

数据可复现：Python random.Random(42)，i=0…99。i在[30,46,61,74,88]时四特征分别uniform(15.5,19)、uniform(25,29)、uniform(4,14)、uniform(.1,.5)；其余uniform(25,34)、uniform(32,35)、uniform(38,86)、uniform(1.5,3.8)。体重/箱温/余饲保留2位，活动1位。参考SHA写入每次Visit.model_evidence。读数为模拟范围数据，不接真实蜂箱传感器。

Redis队列交Python worker真算，结果写Visit并在共享artifacts卷留JSON；任务结果Redis缓存24小时。UI不声称患病概率、准确率或临床结论。异常筛查不能代替蜂师检查。

## 一天剧本

1. 08:30 蜂师登录查H-018常规群与H-031未见王弱群；两场80箱。
2. 09:00 把 `shanjing_winter_20261117.csv` 的抬箱、活动、余饲与王况记入手记。
3. 09:30 筛查每箱最新巡检，查看100条参考分布与异常阈值。
4. 10:00 对H-031试建3.5kg饲喂，被拒绝；误做2kg饲喂也不能直接关闭。
5. 11:00 饲喂执行后复查仍未见王，转须换王；建立换王计划。
6. 13:00 确认新蜂王实际入箱，Hive王况更新；首次复查仍无王时主管拒绝关闭。
7. 15:00 复查24kg、见王、6框，主管关闭；H-031越冬复查通过。
8. 16:00 H-018有王群完成1.5kg饲喂，复查24.5kg/7框后关闭，观察员查审计。

Seed按email、Hive.code、Visit.code及饲料批号自然键只补缺少记录，不覆盖人工修改；3账号、80箱、100巡检和3个饲料批次。

## 工程、目录与开发

Python3.12 / FastAPI / SQLAlchemy / PostgreSQL16 / Redis7 / scikit-learn1.6 / Nginx1.27；前端原生ES modules / HTML / CSS，无框架。

backend/src/models.py定义Hive/Visit/CareAction与账号审计；schemas.py校验输入；yard_service.py处理箱况/巡检/筛查入队；care_service.py负责执行/复查/关闭与跨实体规则；screen_model.py无监督模型；worker.py消费筛查队列与心跳；app.py接口、JWT依赖、timings/recover两中间件；scripts/seed_demo.py幂等seed。

frontend/src/pages/yard.js箱位、visits.js巡箱、screening.js分值与阈值、care.js处置复查；notebook.js是领域状态与最新巡检选择；api.js请求；utils.js转义/数值/上海时间/错误反馈；components/notes.js共享巡检证据、异常依据、标题和状态。巡检证据在箱位与处置页复用，异常依据在筛查与处置关联显示。

共享角色、CareKind、CareState、VisitState枚举分别在backend/src/constants.py、frontend/src/constants.js；role与账号一致。审计记录真实操作账号、动作、时间，UI按Asia/Shanghai显示。

本地后端：创建Python3.12 venv，安装backend/requirements.txt，设置DATABASE_URL指向localhost17726、REDIS_URL指向本地Redis；backend目录运行`uvicorn src.app:app --reload`与`python -m src.worker`。worker默认/artifacts需要写权限，推荐Compose；前端Nginx代理/api/，修改后compose build frontend。

环境变量COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、JWT_SECRET、SEED_DEMO、NETWORK_SUBNET。默认显式子网10.221.27.0/24规避本机地址池耗尽。恰好五服务，全部真实health；worker用20秒心跳门限，backend查DB/Redis，Nginx127.0.0.1。db_data/redis_data/artifacts三命名卷。首次metadata建表，无生产在线迁移；测试/截图在源码外test-artifacts/gb-1027。

## License

MIT，见LICENSE。


## 饲料追溯与蜂王引入观察扩展

**饲料批次领用**：FeedLot记录唯一批号、到货/可用重量、有效期及active/quarantine状态；FeedIssue用唯一care_id关联饲喂计划、来源批次、领用重量和领退人。领料量从CareAction.feed_kg自动取值，不允许另填。事务锁计划与批次，拒过期、隔离、缺料及重复领用。饲喂执行前须已领料，执行时再次核批次有效状态，成功后issue变used。尚未执行的计划可附依据取消，原批加回同量、issue变returned，重复退料拒绝；已执行不回库。

**蜂王引入观察**：QueenObservation唯一关联换王care_id，并记录唯一蜂王号、与执行日一致的引入日期、接受/见卵布尔值、观察手记和主管确认人。仅已执行换王可登记，观察阶段可补记；新王接受且见卵后才允许主管确认。确认后冻结。换王关闭在原见王、体重不降、蜂量≥5框之外，追加“新王接受+见卵+主管确认”条件，历史已关闭数据保留。

接口：`GET/POST /feed-lots`、`PUT /feed-lots/{id}/state`（主管隔离/解除）、`GET/POST /feed-issues`、`POST /care/{id}/cancel`、`GET/POST /queen-observations`、`PUT /queen-observations/{id}`、`POST /queen-observations/{id}/confirm`（仅主管）。蜂师可入库、领退和登记观察；观察员只读。前端新页为`pages/feed.js`与`pages/queens.js`；后端新增`resource_models.py/resource_schemas.py/resource_routes.py/feed_service.py/queen_service.py`，原care_service接执行与关闭守卫。

Seed增加FD-202611-A可用30kg、FD-HOLD隔离8kg、FD-EXPIRED已过期5kg，后两批用来演示拒领；不制造未经执行的蜂王观察。领料与观察须实际经过原处置流程。三个新表由metadata补建，无旧表列变更；已有已关闭处置不追溯篡改，后续新执行/关闭应用新条件。

续篇剧本：入库20kg→为1.5kg饲喂计划领用→库存18.5kg→处置簿登记执行，领料凭据变已使用；另一换王计划实际入箱→观察接受与见卵→主管确认→返回处置簿登记24kg/见王/6框→主管关闭。取消未执行计划时原批库存恢复。真实证据位于`test-artifacts/gb-1027/expansion/`。

范围：已实现小型批次库存和领退追溯；未实现采购订单、多仓调拨、蜂王采购或病害诊断。饲料有效期、3kg单次上限及5框门限为模拟业务规则。


## V3 转场、保温和春检

原六页完整保留，新增蜂场转场检疫、保温物料安装、春检复苏损耗三页，共九业务页。

1. ApiaryMove绑定蜂箱，winter_ready且有王、至少5框、无planned/executed/rechecked活跃处置才可申请；同箱一个在途。主管检疫签发→蜂师实际转场，未来日期不可提前完成，原址变化拒绝覆盖；在途档案冻结，可取消。完成只更新蜂箱当前site，保存原址、冬前框数、王况和巡检ID/体重快照，不改历史Visit。被换王接手的needs_requeen旧单为历史处置，非活跃计划。
2. InsulationLot有库存及active/quarantine状态，InsulationInstall关联蜂箱和批次，按Hive→Install→Lot顺序锁定；安装整笔扣件，同箱一个installed/accepted。未通风拒验收，可在installed补记通风，再由主管验收；验收后通风冻结。拆除按实际可复用数0至原件数一次返库，损坏不返，重复拆返拒绝。
3. SpringReview蜂箱唯一，须winter_ready且有accepted保温。保存冬前体重（优先最后已关闭CareAction复查体重）、框数、王况、站点和保温ID快照；春检实际王况/框数同步当前箱。无王、框数<5或死亡率>20%为rescue，其他pending；救护须原巡检页新建真实读数、IsolationForest筛查、同箱新CareAction及原领料/换王观察/复查闭环，主管才可审签。旧单、他箱单、未关闭单拒绝，已通过不可重复。审签后当前箱spring_ready，冬前快照不改。

GET /moves /insulation-lots /insulation-installs /spring-reviews供三角色；POST /moves、complete/cancel、POST /insulation-lots、POST /insulation-installs、PUT ventilation、POST remove及POST /spring-reviews允许蜂师/主管；move approve、insulation accept、spring pass及物料隔离仅主管，viewer全部只读。各新增模型均有外键；物料数量与春检值域由数据库和Pydantic校验。

Seed只在缺失时增加IN-2026-WINTER 120件，不改人工库存/安装/春检；历史winter_ready无需补装以维持历史状态，新的春检动作才要求保温。真实证据在test-artifacts/gb-1027/v3/。本地检疫留痕不替代行政检疫证；每箱每季一条春检，本演示固定2026越冬季，无跨季归档。
