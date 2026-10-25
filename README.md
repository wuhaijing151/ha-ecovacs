# ha-ecovacs · 科沃斯未知机型补丁

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

让 Home Assistant 官方 **Ecovacs（科沃斯）** 集成能够使用 `deebot_client` 尚未收录的新机型，
例如 **DEEBOT T30 MAX 自动上下水套装**（机型代号 `wc8lnp`）。

> 本集成**不修改**任何已安装文件（官方集成、`deebot_client`、容器内文件都不动），
> 只在内存里为你的机型注册一个"能力别名"，重启即失效，卸载后不留痕迹。

---

## 一、问题现象

官方 `ecovacs` 集成通过 `deebot_client` 的**机型能力表**来识别扫地机：每个机型对应
`deebot_client/hardware/<机型代号>.py` 这个模块。如果你的机型还没有被上游收录，日志里会出现：

```
WARNING deebot_client.api_client: Device class "wc8lnp" not recognized. Please add support for it: {...}
WARNING homeassistant.components.ecovacs.controller: Device "DEEBOT T30 MAX自动上下水套装" not supported.
```

结果是：**所有实体都不可用**（`vacuum.xxx` 显示 unavailable，或者是一堆 `unknown` 幽灵实体），
而在上游补充机型之前，官方集成无法使用。上游是"人工提交机型"的模式，新机型往往要等很久。

## 二、工作原理

集成在 Home Assistant 启动完成后自动执行四步：

1. **找出未支持的机型代号**：读取正在运行的科沃斯集成里被标记为 `not_supported` 的设备，
   再向云端拉取账号下全部设备，凡是 `deebot_client` 没有对应模块的机型都列出来。
2. **找最接近的"已支持机型"**：拉取科沃斯产品库（`get_product_iot_map()`）并逐个打分：
   | 判据 | 分值 |
   | --- | --- |
   | 产品名 `name` 完全相同 | 1000 |
   | `UILogicId` 完全相同（上游判据） | 900 |
   | 同机型族（`t30max_cn_h_t30h5` → `t30`） | 400 |
   | `model` 完全相同 | 300 |
   | `smartType` 相同 | 100 |

   只有**已支持**且得分 ≥ 400 的候选才会被采用，绝不会跨机型族乱配对。
3. **注册能力别名**：在内存中注册 `deebot_client.hardware.<你的机型>`，复用该已支持机型的
   `get_device_info()`。`StaticDeviceInfo` 只包含"数据类型 + 设备能力"两项，因此别名是完整的，
   不依赖模块名。
4. **重新加载科沃斯集成**：实体立刻恢复正常（状态、电量、地图、基站、耗材寿命等）。

日志示例：

```
WARNING custom_components.ecovacs_model_patch: Device class wc8lnp is unknown to deebot_client and is now handled like n9f2g8
WARNING custom_components.ecovacs_model_patch: Reloaded Ecovacs config entry 01JGP4Q9KVWNFSE9ZJGNHH51DQ
WARNING custom_components.ecovacs_model_patch: Runtime patch active: wc8lnp -> n9f2g8
```

## 三、安装

### 方式 1：HACS（推荐）

1. HACS → 集成 → 右上角 `⋮` → **自定义仓库**；
2. 仓库地址填 `https://gitee.com/wuhaijing151/ha-ecovacs`，类别选 **Integration（集成）**；
3. 搜索 `Ecovacs Unsupported Model Patch` 安装；
4. **重启 Home Assistant**。

### 方式 2：手动

把仓库里的 `custom_components/ecovacs_model_patch` 整个目录复制到 Home Assistant 的
`config/custom_components/` 下，然后重启。

## 四、配置

`configuration.yaml` 里加一行即可（自动侦测，无需填写机型代号）：

```yaml
ecovacs_model_patch:
```

可选项：

```yaml
ecovacs_model_patch:
  enabled: true
  watch:                      # 手动指定要打补丁的机型代号（一般不需要）
    - wc8lnp
  hardware_override:          # 自动匹配不满意时，手动指定复用的已支持机型
    wc8lnp: n9f2g8
```

保存后重启 Home Assistant。首次启动会向云端查询一次（约几秒），结果会缓存到
`config/ecovacs_model_patch_cache.json`，之后启动不再请求云端。

### 服务

| 服务 | 说明 |
| --- | --- |
| `ecovacs_model_patch.refresh` | 重新侦测 + 重新加载科沃斯集成；参数 `rediscover: true` 表示忽略缓存重新查询云端 |

### 诊断文件

| 文件 | 内容 |
| --- | --- |
| `config/ecovacs_model_patch_cache.json` | `未支持机型 -> 复用的已支持机型` 的缓存（可手改，改完调用一次 `refresh`） |
| `config/ecovacs_model_patch_report.json` | 最近一次侦测的完整过程：机型信息、候选列表、得分、最终选择 |

## 五、常见问题

**Q：日志里说"没有找到足够相似的已支持机型"？**
会同时在"设置 → 系统 → 修复"里生成一条通知，并在 `report.json` 里列出全部候选与得分。
你可以照着报告里的候选，用 `hardware_override` 手动指定一个最接近的机型（例如同系列、同基站的型号）。

**Q：为什么有些实体还是没有 / 显示不可用？**
复用的是**其它机型**的能力表，能力不会 100% 一致。比如某些清扫参数、音量、网络信息可能缺失。
建议优先选同机型族的型号。所有**默认关闭**的实体可以在"设置 → 设备与服务 → 实体"里手动启用。

**Q：上游已经支持我的机型了怎么办？**
直接卸载本集成即可。集成内置了自我保护：一旦发现 `deebot_client` 已经自带该机型的模块，
就**不会**打补丁（避免覆盖官方实现）。

**Q：升级 Home Assistant 或 deebot_client 之后出问题？**
删除 `config/ecovacs_model_patch_cache.json` 后重启，让它重新侦测；或调用
`ecovacs_model_patch.refresh` 并带 `rediscover: true`。

**Q：会修改我的 HA 文件吗？**
不会。补丁只存在于 Python 进程的内存里（`sys.modules`），除了上面两个诊断 json 文件外不写任何东西。
卸载/重启后自动消失。

**Q：支持多个未收录机型吗？**
支持，会自动侦测并逐个处理；也可以全部写进 `watch` 列表。

## 六、已验证机型

| 实际机型 | 机型代号 | 复用机型 | 结果 |
| --- | --- | --- | --- |
| DEEBOT T30 MAX 自动上下水套装 | `wc8lnp` | `n9f2g8`（DEEBOT T30 PRO PLUS） | 状态 / 电量 / 地图 / 集尘基站 / 抹布与滤芯寿命 均正常 |

> 欢迎在 Issues 里贴出你的 `ecovacs_model_patch_report.json`（可删除敏感字段），
> 一起完善这份兼容列表。

## 七、免责声明

控制指令按照**复用机型**的能力表下发，与真机可能存在差异，请谨慎使用耗材复位、集尘、
重新定位等操作。本集成与科沃斯（Ecovacs）、Home Assistant 官方均无关联。

## 八、目录结构

```
custom_components/ecovacs_model_patch/
├── __init__.py        # 启动编排、服务、修复通知、诊断输出
├── cloud.py           # 复用官方集成已认证的 deebot_client 客户端
├── const.py           # 常量
├── discovery.py       # 产品库拉取 + 相似度打分
├── patch.py           # 内存机型别名（sys.modules 注入）
├── manifest.json
├── services.yaml
├── strings.json
└── translations/      # en / zh-Hans
```

## 九、License

[MIT](LICENSE) © 2026 吴海晶