# UI 图像资源命名规范

适用于新加入的 UI 源图像素材，包括公共资源和各模块资源。命名服务于人工查找、结构文件引用和后续 AssetBundle 打包；现有脚本会检查路径歧义，但**尚未自动校验本规范的缩写格式**。已有素材不因本规范自动重命名。

## 当前 `hund/market` 项目

`hund/source/design/market.png` 是效果图，`hund/source/sprites/` 是切图根目录。目前切图按 `Backgrounds/`、`Buttons/`、`Cells/`、`Decorations/`、`Icons/` 和 `Sprites/` 分类；例如 `Buttons/btn_buy_normal.png`、`Cells/cell_tradable_selected.png`。这些是**现有文件及引用**，可以继续用于当前页面。根目录中的 `Preview.png`、`Reconstruction.png` 和报告文件是产出/检查资料，不是 UI 源切图。

下文的 `Common/` 与 `Pages/<module>/` 是新增页面时建议采用的归属布局，**不是当前 `hund` 项目已经完成的迁移**。为 `market` 新增资源时，可以先沿用当前目录并写明完整相对路径；若决定迁移到新布局，应一次核对所有受影响页面的 `assetDirs`、`commonAssetDirs`、`ui_structure.json` 与 Unity 引用，然后重新执行 `prepare → check → 复核 → finalize`。不要仅为了统一名字批量改动现有切图。

## 归属与文件名

一个游戏使用独立的 `assetRoot`。该游戏内的图像文件名采用：

```text
<scope>_<type>_<meaning>[_<state>][_<variant>].<ext>
```

- 全部使用小写 ASCII 字母、数字和下划线；扩展名使用小写 `.png`、`.jpg` 或 `.jpeg`。不用空格、中文、连字符、临时序号、`final`、`new`、`v2` 等制作过程标记。
- `<scope>` 是 `cmn`（公共）或模块固定缩写。每个游戏在 `ui_workspace.json` 旁的项目文档中维护一份模块缩写表；模块缩写使用三个小写字母，在该游戏内唯一，确定后保持稳定。例如 `mkt` 表示 market、`eqp` 表示 equipment。不要为同一模块混用缩写。
- `<type>` 取下表中的统一缩写；`<meaning>` 用简短、稳定的英文词描述图像所表达的对象或用途，例如 `coin`、`buy`、`inventory`。词之间用下划线分隔。
- 只有确实存在多种状态时才写 `<state>`；默认状态省略。`<variant>` 仅用于尺寸、颜色或其他确有必要区分的版本，并使用有含义的词，如 `large`、`red`，不用数字顺序代替含义。
- 同一游戏的所有 UI 源图像**文件名不区分大小写后必须唯一**，即使它们位于不同目录。新增文件前检查同名；更改文件名时同步更新 `ui_structure.json` 中的资源路径及相关 Unity 引用。

| 类型 | 缩写 | 状态 | 缩写 |
| --- | --- | --- | --- |
| 图标 | `ico` | 悬停 | `hov` |
| 按钮 | `btn` | 按下 | `prs` |
| 背景 | `bg` | 禁用 | `dis` |
| 面板 | `pnl` | 选中 | `sel` |
| 边框 | `frm` | 默认（仅多状态时） | `nrm` |
| 单元格 | `cel` |  |  |
| 装饰 | `dec` |  |  |
| 资源胶囊/条 | `pil` |  |  |

例如现有 `btn_buy_normal.png` 与 `btn_buy_disabled.png`，迁移后可分别命名为 `mkt_btn_buy_nrm.png` 与 `mkt_btn_buy_dis.png`；只有一个状态时省略状态段。新增类型或状态时先更新此表，再使用新缩写；不要为同一含义另起缩写。

## 公共资源与模块资源

公共资源放在该游戏的 `Common/`，模块专用资源放在 `Pages/<module>/`。**默认一个模块只用一个素材目录**，图标、按钮、背景等直接放在一起，由文件名的 `<type>` 区分；`Common/` 也采用相同方式。素材量大到难以浏览时，可再按类型建立子目录，文件名规则保持不变。判断是否公共资源：修改这一张图时，所有使用它的模块是否都应一起变化。只有确认共用同一份素材时才放入 `Common/`；外观相近但需要独立修改的资源留在各模块。

```text
sprites/
  Common/cmn_ico_coin.png
  Common/cmn_btn_close.png
  Pages/market/mkt_bg_market.png
  Pages/market/mkt_btn_buy_dis.png
  Pages/equipment/eqp_pnl_inventory.png
```

`ui_workspace.json` 的 `commonAssetDirs` 和 `assetDirs` 选择这些目录。`ui_structure.json` 引用时写相对于 `assetRoot` 的路径，例如 `Common/cmn_ico_coin.png`；当前 `hund` 项目则写 `Buttons/btn_buy_normal.png` 这样的实际路径。目录表达归属，文件名中的 scope 则保证素材被汇总、复制或按文件名检索时仍可辨认。当前工作流虽支持唯一 basename 的简写，规范仍要求结构文件写完整相对路径。

## AssetBundle 边界

AssetBundle 的名称和源图像文件名分别管理。建议在包名中加入游戏命名空间及归属，例如 `ui/hund/common`、`ui/hund/market`；不同游戏可以使用相同的源图像文件名。加载时使用完整资源路径或明确配置的 address，不依赖裸文件名。

公共素材由一个公共包明确收纳，模块包引用它。**文件名唯一只能避免名称歧义，不能阻止同一依赖被复制进多个包。** 打包前另行检查包归属和重复依赖。Unity 导出器自动生成的 `image_<hash>`、`sprite_<hash>` 等派生文件使用其自身的稳定命名机制，不按此源素材规则手动改名。
