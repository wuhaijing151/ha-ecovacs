# Changelog

## 1.0.2 (2026-10-25)

修正（已在真实环境验证）：

- **事件循环阻塞告警全部消除**。`deebot_client` 的机型查找要扫目录、导入模块
  （`os.listdir` / `import_module`），之前直接在事件循环里跑，HA 每次启动都会报
  `Detected blocking call to listdir … inside the event loop` 和
  `Detected blocking call to import_module …`。现在
  `patch.py` 新增 `async_supported_classes` / `async_module_available` /
  `async_install_alias` 三个执行器包装，`__init__.py`、`discovery.py`、`cloud.py`
  的 6 处调用点全部改走它们。
- 同步函数（`supported_classes` / `module_available` / `install_alias`）仍然保留，
  作为纯工具函数使用，行为不变。

已验证：HA Core 2026.10.0 重启后，`ecovacs_model_patch` 的 3 条阻塞调用告警全部消失，
别名补丁照常生效（`wc8lnp -> n9f2g8`），扫地机实体正常。

## 1.0.1 (2026-10-25)

修正（已在真实环境验证）：

- 配置支持裸键写法 `ecovacs_model_patch:`（此前只接受带子项的映射，裸键会报配置错误）
- 修正云端设备列表解析：`ApiClient.get_devices()` 返回的是 `Devices` 数据类
  （`mqtt` / `xmpp` / `not_supported`），不是设备数组
- 侦测逻辑兼容 `runtime_data` 为控制器或 `Devices` 两种形态
- 修复通知创建失败不再影响补丁主体

## 1.0.0 (2026-10-25)

首个版本。

- 自动侦测 `deebot_client` 未支持的机型代号（科沃斯集成运行时 + 云端设备列表两条路径）
- 基于科沃斯产品库的相似度打分匹配已支持机型
  （`name` / `UILogicId` / 机型族 / `model` / `smartType`）
- 在内存中注册机型能力别名，无需修改任何已安装文件
- 自动重新加载科沃斯集成条目，实体立即恢复
- 结果缓存（`ecovacs_model_patch_cache.json`）与诊断报告（`ecovacs_model_patch_report.json`）
- `ecovacs_model_patch.refresh` 服务，支持 `rediscover` 忽略缓存
- 匹配失败时生成"修复"通知
- 上游已支持该机型时自动跳过，避免覆盖官方实现

已验证：DEEBOT T30 MAX 自动上下水套装（`wc8lnp`）→ 复用 DEEBOT T30 PRO PLUS（`n9f2g8`）