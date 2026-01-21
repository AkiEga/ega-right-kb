# KLE to KiCAD Plugin

KiCADのPCBエディタ用プラグインです。keyboard-layout-editor.com (KLE) のJSONファイルを読み込み、スイッチ(SW)とダイオード(D)のフットプリントを自動配置します。

## 機能

- KLE JSON形式のパース
- Cherry MX互換スイッチの自動配置
- ダイオードの自動配置（オフセット設定可能）
- 回転キーのサポート
- 様々なキーサイズ対応（1u, 1.5u, 2u, ISOエンターなど）
- GUIによる設定

## インストール方法

### 方法1: 手動インストール

1. `kle2kicad_plugin` フォルダを KiCAD のプラグインディレクトリにコピーします

**Windows:**
```
%APPDATA%\kicad\8.0\scripting\plugins\
```

**macOS:**
```
~/Library/Application Support/kicad/8.0/scripting/plugins/
```

**Linux:**
```
~/.local/share/kicad/8.0/scripting/plugins/
```

2. KiCADのPCBエディタを再起動します

3. メニューから `ツール` → `外部プラグイン` → `KLE to KiCAD Layout` を選択

### 方法2: シンボリックリンク（開発用）

開発時は、プラグインディレクトリにシンボリックリンクを作成すると便利です：

**Windows (管理者権限のコマンドプロンプト):**
```cmd
mklink /D "%APPDATA%\kicad\8.0\scripting\plugins\kle2kicad_plugin" "C:\work\keyboard\ega-right-kb\HW\KiCAD\kle2kicad_plugin"
```

## 使い方

### GUIから使用

1. KiCADでPCBファイルを開く
2. `ツール` → `外部プラグイン` → `KLE to KiCAD Layout` を選択
3. KLE JSONファイルを選択
4. 設定ダイアログでパラメータを調整
5. 「Apply Layout」をクリック

### スクリプトコンソールから使用

KiCADのスクリプトコンソール（`ツール` → `スクリプトコンソール`）で：

```python
from kle2kicad_plugin.kle2kicad_core import KLE2KiCADCore
import pcbnew

board = pcbnew.GetBoard()
settings = {
    'origin_x': 50,
    'origin_y': 50,
    'sw_width': 19.05,
    'sw_height': 19.05,
    'place_diodes': True,
    'diode_offset_x': 0,
    'diode_offset_y': 5.08,
    'diode_rotation': 90,
}

core = KLE2KiCADCore(board, "path/to/your/layout.json", settings)
result = core.execute()
pcbnew.Refresh()
print(result)
```

### コマンドラインから使用

```bash
python -m kle2kicad_plugin layout.json board.kicad_pcb --origin-x 50 --origin-y 50
```

オプション:
- `--origin-x`: 原点X座標 (mm)
- `--origin-y`: 原点Y座標 (mm)
- `--sw-width`: スイッチ幅/ピッチ (mm, デフォルト: 19.05)
- `--sw-height`: スイッチ高さ/ピッチ (mm, デフォルト: 19.05)
- `--no-diodes`: ダイオードを配置しない
- `--diode-offset-x`: ダイオードのX方向オフセット (mm)
- `--diode-offset-y`: ダイオードのY方向オフセット (mm)
- `--diode-rotation`: ダイオードの回転角度 (度)
- `--dry-run`: PCBを変更せずにパース結果のみ表示
- `-o, --output`: 出力ファイルパス

## KLE JSON形式について

keyboard-layout-editor.com でレイアウトを作成し、「Download JSON」でエクスポートしたファイルを使用します。

キーのラベルには `SW{row}{col}` 形式でリファレンスを設定してください：

```
SW00, SW01, SW02, ...  // 1行目
SW10, SW11, SW12, ...  // 2行目
```

対応するダイオードは `D{row}{col}` として自動的にマッピングされます：

```
SW00 → D00
SW01 → D01
```

## 設定パラメータ

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| Origin X | 50 mm | 配置開始位置のX座標 |
| Origin Y | 50 mm | 配置開始位置のY座標 |
| Switch Width | 19.05 mm | Cherry MX標準ピッチ |
| Switch Height | 19.05 mm | Cherry MX標準ピッチ |
| Diode Offset X | 0 mm | スイッチ中心からのX方向オフセット |
| Diode Offset Y | 5.08 mm | スイッチ中心からのY方向オフセット |
| Diode Rotation | 90° | ダイオードの回転角度 |

## ファイル構成

```
kle2kicad_plugin/
├── __init__.py           # プラグイン登録
├── __main__.py           # コマンドライン実行用
├── kle2kicad_action.py   # ActionPluginクラス（GUI）
├── kle2kicad_core.py     # コアロジック
├── metadata.json         # PCM用メタデータ
├── README.md             # このファイル
├── icon.png              # ツールバーアイコン（24x24）
└── icon_dark.png         # ダークテーマ用アイコン
```

## KiCAD バージョン対応

- KiCAD 8.0 以降

**注意**: KiCAD 9.0以降ではSWIG Python バインディングは非推奨となり、IPC APIに移行予定です。KiCAD 10.0での削除が予定されています。

## ライセンス

MIT License

## 謝辞

- [keyboard-layout-editor.com](http://www.keyboard-layout-editor.com/) - キーボードレイアウトエディタ
- [KiCAD](https://www.kicad.org/) - オープンソースPCB設計ツール
