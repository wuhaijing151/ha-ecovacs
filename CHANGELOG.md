# Changelog

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