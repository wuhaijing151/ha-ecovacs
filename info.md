# 科沃斯未知机型补丁

让 Home Assistant 官方 **Ecovacs** 集成支持 `deebot_client` 尚未收录的新机型
（例如 DEEBOT T30 MAX，机型代号 `wc8lnp`），不再出现"设备不受支持、实体全部不可用"。

- ✅ 自动侦测未支持机型，并匹配最接近的**已支持**机型
- ✅ 只在内存里打补丁，**不修改任何已安装文件**
- ✅ 上游支持你的机型后自动失效，可直接卸载
- ✅ 找不到相似机型时会在"修复"里提示，并输出完整诊断报告

## 快速开始

1. HACS → 集成 → `⋮` → 自定义仓库 → `https://gitee.com/wuhaijing151/ha-ecovacs`（类别：集成）
2. 安装并重启 Home Assistant
3. `configuration.yaml` 加一行：

```yaml
ecovacs_model_patch:
```

4. 再重启一次，日志出现 `Runtime patch active: wc8lnp -> n9f2g8` 即成功

完整说明见 [README.md](https://gitee.com/wuhaijing151/ha-ecovacs/blob/master/README.md)。