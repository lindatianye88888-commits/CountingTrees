# CountingTrees（数树）

本仓库提供以下两个软件版本及其配套源码、文档和安装包：

| 版本 | 源码目录 | 安装包 |
| --- | --- | --- |
| 0.3.23：AutoCAD 2014 x64／天正 TArch9 | [PlantCAD-0.3.23-CAD2014-TArch9](PlantCAD-0.3.23-CAD2014-TArch9/) | [0.3.23 安装包](releases/CountingTrees_数树_0.3.23_CAD2014_TArch9.zip) |
| 0.3.28：AutoCAD 2014—2024 分版兼容开发版 | [PlantCAD-0.3](PlantCAD-0.3/) | [0.3.28 安装包](releases/CountingTrees_数树_0.3.28.zip) |

0.3.23 根据原回滚快照整理，运行文件已逐项匹配原清单校验值，具体来源见[保留说明](PlantCAD-0.3.23-CAD2014-TArch9/保留说明.md)。两个版本分别通过 260 项、309 项无需 CAD 的自动检查。

用于 Windows AutoCAD 的景观植物绘图插件，当前开发版本 **0.3.28**。支持乔木、灌木球、灌木与地被的布置、区域面积计算、植物填充、引线标注和关联苗木数量表，并提供本地 MCP 接口。

**署名：梅梅的AI景观实验室**  
Gmail：[lindatianye88888@gmail.com](mailto:lindatianye88888@gmail.com) · QQ 邮箱：[375803231@qq.com](mailto:375803231@qq.com)

软件工作台底部显示署名，点击“关于/联系”可查看两个邮箱；植物小圆标右键菜单也有联系方式入口。

0.3.28 修复灌木标注不跟随单位、比例和字高的问题，短横线自动延长。309项自动检查、209项2014内核出图与保存重开检查通过，桌面鼠标验收及2015—2024宿主验收仍待完成。

当前已知问题：自动补线可能把相邻边线之间的细小缝隙额外识别为区域，小面积保留两位小数后显示为“0.00 平方米”。这类额外区域的筛选仍待修复，不代表旁边主要种植区域的面积为零。

0.3.27 的“项目植物 → 更新已有植物”支持混选图块、植物文字和灌木标注，补入项目规格并立即刷新数树关联表。普通文字仅收录名称，数量/面积以关联图形为准；未关联的名称显示“待关联”。

0.3.26 修复植物规格窗口初始化异常后无法取消的问题；按 Esc 或关闭窗口不会保存未确认的规格。

## 安装与使用

下载 [0.3.28 开发版安装包](releases/CountingTrees_数树_0.3.28.zip)，解压后，先保存图纸并关闭 AutoCAD／天正，再双击 `PlantCAD-0.3/安装操作面板.cmd`。安装脚本需要 Python 3；本项目开发环境使用 Python 3.12。

启动 CAD，输入 `COUNTINGTREES` 或 `数树` 打开植物工作台。也可以从本仓库的 `PlantCAD-0.3` 目录直接运行安装脚本。

[开始使用](开始使用.md) · [完整操作说明](PlantCAD-0.3/README.md) · [兼容性与测试矩阵](PlantCAD-0.3/docs/兼容性与测试矩阵.md)

## 兼容范围

目标为 **Windows 64 位＋完整 AutoCAD 2014—2024**，按 API 版本提供六组 DLL，由安装后的插件清单选择加载版本。天正需搭配其支持的 AutoCAD 版本。

AutoCAD 2014／TArch9 为本机开发环境；0.3.28 已通过 309 项自动检查和 209 项 AutoCAD 2014 内核出图及保存重开检查，桌面鼠标验收仍待完成。2015—2024 已完成对应 SDK 编译及引用核对，**尚未完成对应 CAD、天正的实机交互和打印验收**。当前安装包为开发版。

## 源码与构建

| 路径 | 内容 |
| --- | --- |
| `PlantCAD-0.3/developer/src` | UTF-8 AutoLISP、DCL 和植物目录源文件 |
| `PlantCAD-0.3/bridge/src` | C# CAD 桥接、工作台、几何及出图逻辑 |
| `PlantCAD-0.3/developer/tests` | 植物规则和流程测试、原生 CAD 验证驱动 |
| `PlantCAD-0.3/bridge/tests` | MCP 协议和读取器测试 |
| `PlantCAD-0.3/docs` | 操作、开发及验证说明 |
| `releases` | 可安装开发包和 SHA-256 校验文件 |

根目录运行无需 CAD 的自动检查：

```powershell
python -B -m unittest discover -s PlantCAD-0.3/developer/tests
python -B -m unittest discover -s PlantCAD-0.3/bridge/tests
```

完整构建在 Windows 上进行，需要 .NET Framework 编译器和相应 Autodesk 托管 API 引用。2014 引用取自本机合法安装，可用 `PLANTCAD_CAD_DIR` 指定目录；其余版本引用可通过 `PlantCAD-0.3/bridge/fetch_sdk_references.py` 获取。准备好引用后运行：

```powershell
python -B PlantCAD-0.3/bridge/fetch_sdk_references.py
python -B PlantCAD-0.3/developer/build.py
```

`PlantCAD-0.3` 根目录的 LISP／DCL／TSV 是生成的 GBK／CRLF 运行文件；修改其 `developer/src` 中的 UTF-8 源码后重新构建。保留 PlantCAD 技术目录、历史命令和图纸字典名称，以兼容已有图纸与连接配置。

本仓库及公开安装包不包含案例原图、案例测试基线、公众号素材、第三方程序或 SDK DLL、本机连接配置、缓存和运行队列。需要原始案例的 CAD 验证脚本须使用自己的图纸与本地测试记录；完整发布验收仍需对应宿主环境。

本地 MCP 配置可运行 `python -B PlantCAD-0.3/bridge/configure_clients.py` 生成；该命令默认只生成配置片段，不修改现有客户端设置。
