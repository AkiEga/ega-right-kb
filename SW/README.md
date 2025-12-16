# ega-right-kb ファームウェア

Raspberry Pi Pico 上で TinyUSB を使用するカスタムキーボードファームウェア。6×10 マトリックスの 50 キー右手用キーボード。TinyUSB の`hid_composite`サンプルをベースにしています。

## ハードウェア構成

- **マトリックス:** 6 行 × 10 列 = 50 スイッチ
- **行ピン（入力）:** GPIO 16-21（プルアップ有効、アクティブ Low）
- **列ピン（出力）:** GPIO 0-9（アクティブ Low スキャン）
- **レイアウト:** `../HW/keyboard-layout-editor/ega-right-kb-layout.json`を参照

### GPIO 規約

- **列 = 出力:** デフォルトで High に設定、スキャン時に Low に駆動
- **行 = 入力:** プルアップ有効、キー押下時に Low として読み取り

### スイッチマトリックス配置
基本的にはJIS配列分割キーボードの右側のみ。プラス、Bボタンなど右側に1列分追加している

回路図に基づくマトリックス配置（ROW × COLUMN）：

|      |        | COL0         | COL1        | COL2       | COL3      | COL4          | COL5        | COL6     | COL7         | COL8        | COL9     |
| ---- | ------ | ------------ | ----------- | ---------- | --------- | ------------- | ----------- | -------- | ------------ | ----------- | -------- |
|      |        | GPIO4        | GPIO5       | GPIO6      | GPIO7     | GPIO8         | GPIO9       | GPIO3    | GPIO2        | GPIO1       | GPIO0    |
| ROW0 | GPIO21 | SW1(F4)      | SW2(F5)     | SW3(F6)    | SW4(F7)   | SW5(F8)       | SW6(F9)     | SW7(F10) | SW8(F11)     | SW9(F12)    |          |
| ROW1 | GPIO20 | SW10(5)      | SW11(6)     | SW12(7)    | SW13(8)   | SW14(9)       | SW15(0)     | SW16(-)  | SW17(^)      | SW18(\\)    | SW19(BS) |
| ROW2 | GPIO19 | SW20(T)      | SW21(Y)     | SW22(U)    | SW23(I)   | SW24(O)       | SW25(P)     | SW26(@)  | SW27(\[)     | SW28(Enter) |          |
| ROW3 | GPIO18 | SW29(G)      | SW30(H)     | SW31(J)    | SW32(K)   | SW33(L)       | SW34(;)     | SW35(:)  | SW36(\])     |             |          |
| ROW4 | GPIO17 | SW37(B)      | SW38(N)     | SW39(M)    | SW40(<)   | SW41(>)       | SW42(/)     | SW43(\_) | SW44(RShift) |             |          |
| ROW5 | GPIO16 | SW45(Space) | SW46(変換) | SW47(Alt) | SW48(PrintScreen) | SW49(Delete) | SW50(RCtrl) |          |              |             |          |

**注：** 回路図では 50 スイッチが 6 行（ROW0-5）× 10 列（COL0-9）に配置されています。各行のスイッチ数は物理レイアウトに応じて異なります。

## アーキテクチャ

### コアファイル

- **[main.c](main.c)** - メインループ、GPIO 初期化、HID タスク（10ms ポーリング）
- **[usb_descriptors.c](usb_descriptors.c)** - USB デバイス設定（VID: 0xCafe、コンポジット HID）
- **[tusb_config.h](tusb_config.h)** - TinyUSB 設定（HID のみ、RTOS 非使用）

### ビルドシステム

- CMake + [Pico SDK](https://github.com/raspberrypi/pico-sdk)
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

1. **"Run Project"** タスク - picotool 経由で USB 書き込み
2. **"Flash"** タスク - OpenOCD + CMSIS-DAP 使用
3. **手動** - `build/ega_right_kb.uf2`を RPI-RP2 ドライブにドラッグ

### デバッグタスク

- **"Rescue Reset"** - OpenOCD レスキューモード
- **"RISC-V Reset (RP2350)"** - アーキテクチャ切り替え

## 実装状況

### ⚠️ マトリックススキャン（未実装）

[main.c](main.c#L179)の`keyboard_switch_read()`は**スタブ**です。実装が必要:

1. 一度に 1 列ずつ Low に駆動
2. 全 6 行の入力を読み取り（LOW = 押下）
3. (行, 列)を 32 ビットビットマスクのビット位置にマッピング
4. 次に進む前に列を High に戻す

関数内にサンプルロジックがコメントアウトされています。

### HID レポートチェーン

- `hid_task()`が 10ms ごとに REPORT_ID_KEYBOARD を送信
- `tud_hid_report_complete_cb()`がマウス/コンシューマ/ゲームパッドレポートを自動連鎖
- 現在はキーボードレポートのみが実データを使用

### USB ウェイクアップ

- ディスクリプタでリモートウェイクアップ有効
- サスペンド時のキー押下で`tud_remote_wakeup()`を呼び出し

## 一般的なタスク

### USB ID の変更

[usb_descriptors.c](usb_descriptors.c)を編集:

- `USB_VID`（32 行目）: 0xCafe（非公式）
- `string_desc_arr[]`（205 行目）: "TinyUSB"メーカー/製品名

### キーマッピングの追加

1. `keyboard_switch_read()`でマトリックススキャンを実装
2. ビット位置 →HID キーコードの変換テーブルを作成
3. [main.c](main.c#L143)の`HID_KEY_A`プレースホルダーを置換
4. Shift/Ctrl/Alt は`modifier`パラメータを使用

### スキャンレートの調整

[main.c](main.c#L213)の`interval_ms`を変更（デフォルト: 10ms = 100Hz）

## 制約事項

- **RTOS 非使用:** 協調的マルチタスクのみ（`CFG_TUSB_OS = OPT_OS_NONE`）
- **単一 HID エンドポイント:** 全レポートタイプが EP 0x81 を共有
- **RP2040 専用:** GPIO 番号は Pico ボードに依存
- **Windows 開発環境:** SDK パスに`$env:USERPROFILE`を使用

## 注意事項

- ソースファイル追加時は CMake 再生成が必要
- VS Code タスクを使用（SDK パスを自動処理）
- ディスクリプタ変更後は USB 列挙をテスト
