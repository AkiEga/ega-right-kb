# ega-right-kb ファームウェア

Raspberry Pi Pico上でTinyUSBを使用するカスタムキーボードファームウェア。6×10マトリックスの50キー右手用キーボード。TinyUSBの`hid_composite`サンプルをベースにしています。

## ハードウェア構成

- **マトリックス:** 6行 × 10列 = 50スイッチ
- **行ピン（入力）:** GPIO 16-21（プルアップ有効、アクティブLow）
- **列ピン（出力）:** GPIO 0-9（アクティブLowスキャン）
- **レイアウト:** `../HW/keyboard-layout-editor/ega-right-kb-layout.json`を参照

### GPIO規約
- **列 = 出力:** デフォルトでHighに設定、スキャン時にLowに駆動
- **行 = 入力:** プルアップ有効、キー押下時にLowとして読み取り

## アーキテクチャ

### コアファイル
- **[main.c](main.c)** - メインループ、GPIO初期化、HIDタスク（10msポーリング）
- **[usb_descriptors.c](usb_descriptors.c)** - USBデバイス設定（VID: 0xCafe、コンポジットHID）
- **[tusb_config.h](tusb_config.h)** - TinyUSB設定（HIDのみ、RTOS非使用）

### ビルドシステム
- **CMake + Pico SDK 2.2.0**（ツールチェーン: 14_2_Rel1）
- 出力: `build/ega_right_kb.uf2`
- 依存関係: `pico_stdlib`, `tinyusb_device`, `tinyusb_board`, `hardware_gpio`

## 開発

### ビルド
```powershell
# VS Codeタスク経由
"Compile Project"

# または直接実行
~/.pico-sdk/ninja/v1.12.1/ninja.exe -C build
```

### 書き込み
1. **"Run Project"** タスク - picotool経由でUSB書き込み
2. **"Flash"** タスク - OpenOCD + CMSIS-DAP使用
3. **手動** - `build/ega_right_kb.uf2`をRPI-RP2ドライブにドラッグ

### デバッグタスク
- **"Rescue Reset"** - OpenOCDレスキューモード
- **"RISC-V Reset (RP2350)"** - アーキテクチャ切り替え

## 実装状況

### ⚠️ マトリックススキャン（未実装）
[main.c](main.c#L179)の`keyboard_switch_read()`は**スタブ**です。実装が必要:
1. 一度に1列ずつLowに駆動
2. 全6行の入力を読み取り（LOW = 押下）
3. (行, 列)を32ビットビットマスクのビット位置にマッピング
4. 次に進む前に列をHighに戻す

関数内にサンプルロジックがコメントアウトされています。

### HIDレポートチェーン
- `hid_task()`が10msごとにREPORT_ID_KEYBOARDを送信
- `tud_hid_report_complete_cb()`がマウス/コンシューマ/ゲームパッドレポートを自動連鎖
- 現在はキーボードレポートのみが実データを使用

### USBウェイクアップ
- ディスクリプタでリモートウェイクアップ有効
- サスペンド時のキー押下で`tud_remote_wakeup()`を呼び出し

## 一般的なタスク

### USB IDの変更
[usb_descriptors.c](usb_descriptors.c)を編集:
- `USB_VID`（32行目）: 0xCafe（非公式）
- `string_desc_arr[]`（205行目）: "TinyUSB"メーカー/製品名

### キーマッピングの追加
1. `keyboard_switch_read()`でマトリックススキャンを実装
2. ビット位置→HIDキーコードの変換テーブルを作成
3. [main.c](main.c#L143)の`HID_KEY_A`プレースホルダーを置換
4. Shift/Ctrl/Altは`modifier`パラメータを使用

### スキャンレートの調整
[main.c](main.c#L213)の`interval_ms`を変更（デフォルト: 10ms = 100Hz）

## 制約事項
- **RTOS非使用:** 協調的マルチタスクのみ（`CFG_TUSB_OS = OPT_OS_NONE`）
- **単一HIDエンドポイント:** 全レポートタイプがEP 0x81を共有
- **RP2040専用:** GPIO番号はPicoボードに依存
- **Windows開発環境:** SDK パスに`$env:USERPROFILE`を使用

## 注意事項
- ソースファイル追加時はCMake再生成が必要
- VS Codeタスクを使用（SDKパスを自動処理）
- ディスクリプタ変更後はUSB列挙をテスト