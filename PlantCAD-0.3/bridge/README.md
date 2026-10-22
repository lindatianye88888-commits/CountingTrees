# CountingTrees（数树） 面板与 AI 接口

PlantCADBridge.dll 同时提供原生操作面板、图纸加载、鼠标图例预览和本地 AI 工具桥接。0.3.24按AutoCAD 2014—2024的6个API组提供x64 DLL。2014为本机验证环境；高版本及对应天正待实机验收。详见主说明中的兼容性矩阵。

正常使用先按主 README 安装，启动天正后输入 COUNTINGTREES 或 数树 打开面板。临时测试可 NETLOAD 加载本目录 DLL，再输入 PLANTCAD。

手动面板无需 AI 连接。要从 Codex 等桌面读取或调整植物，在面板点击“AI连接”，或运行 PLANTCADCONNECT。PLANTCADDISCONNECT 断开。

## 绑定与工具

当前接口为本地 stdio MCP，不调用模型 API。客户端账号由客户端管理。固定工具为 status、get_plants、catalogue、preview_adjust、apply_adjust、plot_settings，没有任意脚本或系统命令工具。

调整先读取真实对象，再预览；用户已授权执行该项调整时可执行有效计划。图纸/对象变化、重连或过期使旧计划失效。超时或部分失败后先回读图纸，不盲目重试。修改不自动保存，既有标注及受管理三表按范围同步。

切换到其他图纸会暂停绑定图纸的远程操作；在目标图点击 AI连接重新绑定。图纸关闭即断开。其他客户端配置见 clients，MCP 代码和参数约束见 mcp_server.py。

## 安装与队列

install_panel.py 将八个必要运行文件复制到用户级专属 .bundle，安装包的 queue-root.json 指回当前工作目录 bridge/runtime，以便复用已经配置的 MCP。移动源码目录后重新运行安装器。

安装器默认要求关闭 CAD；只有内部 --update-unloaded 模式会先逐一验证已安装运行文件没有占用，任何文件被占用都会在复制之前停止。不修改 CAD/TArch 的支持路径、菜单或安全策略。

runtime 和 host-output 含本机会话与测试数据，不进入分发 ZIP。

## 构建与验收

developer/build.py 运行规则/协议检查、编译 DLL 并转换配套 GBK 运行文件。build_bridge.py --test-reader 独立检查数据解码器。developer/verify_release.py 核验文件散列、纯规则模拟与 ZIP。85 项规则/协议检查已通过，完整最终宿主验收状态以 [验证说明](../docs/验证说明.md) 和当前散列匹配的记录为准。
