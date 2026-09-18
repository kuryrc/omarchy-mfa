# Omarchy MFA

[English](README.md)

由 **kuryrc** 制作的 Omarchy 原生 MFA 插件，参考 **Caleb Denio（cjdenio）及贡献者**
开发的 Raycast **Two-Factor Authentication Code Generator**。

参考来源：[Raycast 商店](https://www.raycast.com/cjdenio/two-factor-authentication-code-generator)、
[固定版本源码](https://github.com/raycast/extensions/tree/3c654737b0d566d3103fcdf72221a9f34664bdf2/extensions/two-factor-authentication-code-generator)。
界面使用 Omarchy 原生组件和主题；这是独立移植项目。

## 安装与打开

仓库发布后可运行：

```sh
omarchy plugin add https://github.com/kuryrc/omarchy-mfa.git --enable
omarchy-shell shell toggle kuryrc.mfa
```

本地开发时，将仓库 URL 替换为源码仓库的绝对路径。

在 `~/.config/hypr/bindings.lua` 的其他绑定导入之后添加以下内容。
它会替换相同按键的旧绑定；需要保留旧绑定时，请选其他按键。

```lua
hl.unbind("SUPER + SHIFT + L")
o.bind("SUPER + SHIFT + L", "MFA", "omarchy-shell shell toggle kuryrc.mfa")
```

执行 `hyprctl reload`，再通过 `hyprctl configerrors` 检查。

## 使用

首次打开，选择 **添加账户** 或 **通过 otpauth URL 添加**，手动填写服务提供方给出的密钥。
默认参数为 SHA1、6 位、30 秒，也支持 SHA256/SHA512、7/8 位和 1–2147483647 的整数秒周期。

- 输入文字搜索；方向键或 `Ctrl+p` / `Ctrl+n` 在账户、操作菜单、导入预览中上移 / 下移。
- `Enter` 执行默认操作，默认是复制；`Shift + Enter` 执行另一操作。
- `Ctrl + k` 打开操作菜单；`Ctrl + Shift + n` 手动添加；`Ctrl + U` 通过 URL 添加。
- `Ctrl + E` 重命名选中账户；`Esc` 返回上一页，在主页面时关闭。
- **操作 → 设置** 可切换默认复制/粘贴操作，以及英文或简体中文。自动模式跟随系统语言。

粘贴会先隐藏弹窗，再明确通知后端发送 Shift+Insert；目标程序需要支持该快捷键。
复制功能不依赖目标程序的粘贴快捷键。

Esc 和返回按钮按进入路径逐级返回：从操作菜单打开添加页，返回时回到操作菜单并保留
选中项；从主页面通过 Ctrl+Shift+n 直接打开添加页，则返回主页面。保存成功后回到主页面。

功能包含验证码倒计时、最近使用排序、重命名、删除、备份和恢复。
不提供直接读取 Vicinae 数据库的功能，也不包含二维码扫描、HOTP 或云同步。

## 备份与恢复

**备份账户** 确认后自动在 `~/Backups/omarchy-mfa/` 创建新的 `0600` 文本文件，
无需选择文件或目录。目录不存在时自动创建，权限为 `0700`。文件名带 UTC 时间戳，
保留已有备份，完成后显示完整路径。每行一个 `otpauth://totp/` URL，与原 Raycast
插件的备份格式兼容。文件包含明文密钥，导出前会要求确认。
该格式保存名称、密钥、算法、位数和周期，不保存最近使用时间和插件设置。

**恢复备份** 先展示预览：有效新条目默认选中，同名条目默认跳过；选择同名条目代表覆盖，
提交前还需确认。无效条目显示原因，不会被导入。每个名称只允许选一条。
所选批次通过一次钥匙环写入保存；预览后若账户已发生变化，需要重新预览。

## 依赖与数据位置

要求 Omarchy 的 Quickshell 插件宿主及原生 UI 组件。本机已验证版本为 **4.0.3**；
4.0.4 的标准包列表同样包含以下依赖，但尚未在该版本运行验证：

- `/usr/bin/python3`、`python-gobject`、`libsecret`。
- 提供默认钥匙环的 Secret Service，例如 GNOME Keyring。
- `wl-clipboard` 2.3+、用于粘贴的 `wtype`。
- Wayland 会话和当前用户私有的 `XDG_RUNTIME_DIR`。

无需 pip/npm、编译步骤或额外网络服务。插件安装器不会自动安装缺失依赖。
钥匙环不可用或已锁定时，会显示错误或提供解锁操作，不会自动回退到明文文件。

账户与设置保存在系统钥匙环的 `Omarchy MFA (kuryrc.mfa)` 条目中，应用属性为 `kuryrc.mfa`。
密钥不保存在代码仓库或 `shell.json` 中，也不会通过网络发送。
系统钥匙环不一定加密落盘：Omarchy 默认使用无密码钥匙环，实际保护取决于系统配置。
插件界面与其他插件共享 Omarchy shell 进程，不是安全沙箱。

复制时会标记为敏感内容。验证码到期后，只结束本插件仍持有的数据源，不清除其他程序
后来复制的内容。倒计时不依赖弹窗保持打开；剪贴板临时数据位于用户 runtime 目录。
Omarchy 的剪贴板历史会尊重敏感标记，其他剪贴板管理器可能忽略或另存副本。

## 更新、卸载与开发

技术栈固定为 **QML + Python**。格式规范、严格类型检查、开发命令与 CI 见
[CONTRIBUTING.md](CONTRIBUTING.md)，前后端字段和交互约定见
[协议文档](docs/protocol.md)。这些检查工具仅用于开发，不增加插件运行依赖。

```sh
omarchy plugin update kuryrc.mfa
omarchy plugin disable kuryrc.mfa
omarchy plugin remove kuryrc.mfa
```

卸载后请移除自定义快捷键。钥匙环账户会保留，重新安装后可继续使用。
如需彻底删除数据，在完成所需备份后，通过钥匙环管理器删除明确标为
`Omarchy MFA (kuryrc.mfa)` 的条目即可。

源码仓库和安装目录是两个独立 Git checkout。安装来源指向本地源码仓库时，先在源码
仓库提交，再运行插件更新命令。Omarchy 不允许插件内部包含软链接。

如果更新后仍显示旧界面，关闭弹窗，执行 `omarchy-restart-shell`，再重新打开。
本次在 Omarchy 4.0.3 会话中验证：重新扫描插件仍保留旧 QML 界面，重启 Shell 后才
加载新文件。状态栏会短暂重载，现有应用窗口会保留。

```sh
/usr/bin/python3 -B -m unittest discover -s tests -v
/usr/bin/python3 -B tests/check_ui_refresh.py
/usr/bin/python3 -B tests/check_backup_ui.py
/usr/bin/python3 -B tests/check_paste_ui.py
# 可选：在当前 Wayland 会话中打开独立测试弹窗。
/usr/bin/python3 -B tests/check_backup_ui.py --wayland
omarchy plugin validate .
/usr/bin/python3 -B scripts/check_qml_format.py
```

测试使用公开测试密钥、临时备份和离屏界面，不访问真实钥匙环或剪贴板。
界面回归检查覆盖刷新期间的列表高度、滚动位置与选中项，并发送真实 Qt 按键事件，
验证搜索框及后台刷新期间的 Ctrl+k 操作和普通文字输入，以及菜单的方向键和鼠标悬停
选择、主键盘回车、小键盘回车和空格激活。
同时验证 Ctrl+p/n 移动，以及鼠标停留在另一项时仍只有一个选中高亮。

备份界面测试验证无需选择路径即可确认并自动导出，用鼠标选择导出的文件进行恢复，
用按键取消及确认覆盖，并反复打开备份确认框和恢复选择器五次。使用真实后端和内存
测试账户，核对目录自动创建、目录和文件权限分别为 `0700`/`0600`、恢复后的各项 OTP
参数一致，以及取消操作没有写入文件。

恢复文件选择器使用 MFA 窗口内的 Qt Quick 界面，避开原生 GTK 选择器导致共享
Shell 崩溃的路径。Qt 6.11.2 的选择器对含 `#` 或百分号编码序列的目录可能显示错误内容；
此时请在「恢复备份」页面直接填写备份文件的完整路径。

在本机 Quickshell 0.3.1 / Omarchy 4.0.3 上，插件热更新还曾在 IPC 重新注册时崩溃。
本地开发更新时应先停止 Shell，再更新插件并重新启动 Shell。Shell 停止期间，更新命令
最后的重新扫描会报错，即使 Git 更新和校验已经成功；重启后需核对安装目录的版本。

## 署名与许可

作者：**kuryrc**。项目采用 [MIT 许可](LICENSE)，并保留
[Raycast](LICENSES/Raycast-MIT.txt) 和 [Omarchy](LICENSES/Omarchy-MIT.txt) 的上游许可声明。
与参考插件的明确差异包括：覆盖确认、无效条目报告、操作时重新计算验证码、系统钥匙环
存储，以及敏感剪贴板内容到期释放。
