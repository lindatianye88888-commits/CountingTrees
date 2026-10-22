# CountingTrees（数树）

用于 Windows AutoCAD 的景观植物绘图插件，当前开发版本 **0.3.24**。支持乔木、灌木球、灌木与地被的布置、区域面积计算、植物填充、引线标注和关联苗木数量表，并提供本地 MCP 接口。

## 安装与使用

下载 [0.3.24 开发版安装包](releases/CountingTrees_数树_0.3.24.zip)，解压后，先保存图纸并关闭 AutoCAD／天正，再双击 `PlantCAD-0.3/安装操作面板.cmd`。安装脚本需要 Python 3；本项目开发环境使用 Python 3.12。

启动 CAD，输入 `COUNTINGTREES` 或 `数树` 打开植物工作台。也可以从本仓库的 `PlantCAD-0.3` 目录直接运行安装脚本。

[开始使用](开始使用.md) · [完整操作说明](PlantCAD-0.3/README.md) · [兼容性与测试矩阵](PlantCAD-0.3/docs/兼容性与测试矩阵.md)

## 兼容范围

目标为 **Windows 64 位＋完整 AutoCAD 2014—2024**，按 API 版本提供六组 DLL，由安装后的插件清单选择加载版本。天正需搭配其支持的 AutoCAD 版本。

AutoCAD 2014／TArch9 为本机开发环境；已有 268 项自动检查以及部分 2014 原生内核回归。2015—2024 已完成对应 SDK 编译及引用核对，**尚未完成对应 CAD、天正的实机交互和打印验收**。当前安装包为开发版。

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
