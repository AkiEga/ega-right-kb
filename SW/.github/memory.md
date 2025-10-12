# Project Memory (2025-09-13)

本メモは本日の作業内容と意思決定の履歴を簡潔にまとめたものです。

## 概要

- 対象: Raspberry Pi Pico 2 W（RP2350, `PICO_BOARD pico2_w`）
- ベース: `dev_hid_composite`（TinyUSB HID コンポジットのサンプル）
- 目的: 物理スイッチ入力を使って HID 入力デバイスを実装

## 実装の変遷

1) 単キー・キーボード（初期）
- GP28（内部プルアップ、押下=Low）で "A" キーを送信する最小構成。
- HIDはキーボード単体構成に簡素化。
- `hardware/gpio.h` を使用、`hardware_gpio` を `target_link_libraries` に追加。

2) 4キー・キーボード化
- 追加配線：GP27, GP26, GP22 をそれぞれ B, C, D に割当。
- 同時押し対応：押下マスクから最大6キーに展開して送信。

3) マウス制御への置換
- HIDをマウス専用に変更し、各ピンを方向入力へ変更。
  - GP28: Up, GP27: Right, GP26: Down, GP22: Left（内部プルアップ、押下=Low）
- 押下中は一定ステップでカーソル移動。変化なし時はレポート送信をスキップ。

4) 長押し加速 + 押下履歴
- 直近10件の押下履歴（リングバッファ）を追加。
- 長押しで移動ステップ増加（10ms刻みのホールド時間で段階的に 4→8→12→18）。

5) ダブルタップで Alt+Tab / Shift+Alt+Tab（キーボード+マウス複合）
- HIDをキーボード+マウスの複合に戻し、以下を実装：
  - 右右（GP27 を 200ms 以内に 2回）: Alt+Tab
  - 左左（GP22 を 200ms 以内に 2回）: Shift+Alt+Tab
- キーボードレポートの押下→解放を確実にするためステート管理を導入：
  - 押下は `hid_task` で送信、解放は `tud_hid_report_complete_cb` で送信。
  - 即時2連送（押下→解放）を廃止し、別トランザクションで確実に解放。

## コード上の主な変更点

- `CMakeLists.txt`
  - `hardware_gpio` をリンクに追加。

- `tusb_config.h`
  - 既存設定を流用（`CFG_TUD_HID=1`、EPバッファ 16）。

- `usb_descriptors.h / .c`
  - 段階3: マウス単体 → 段階5: キーボード+マウス複合へ戻す。
  - 製品名を用途に応じて更新（例: "Pico GPIO Mouse"）。

- `main.c`
  - GPIO初期化（28, 27, 26, 22 いずれも内部プルアップ入力）。
  - 方向ビット定義（UP/DOWN/LEFT/RIGHT）とインデックスを統一的に使用。
  - マウス移動：押下状態とホールド時間に応じて dx/dy を計算して送信。
  - 履歴10件のリングバッファ実装。
  - ダブルタップ検知（200ms以内の同方向2回）で Alt+Tab / Shift+Alt+Tab を送信。
  - キーボードマクロを押下→完了通知→解放の順で確実に送るための簡易ステートマシンを実装。
  - Remote wakeup に対応（押下があればホストを起床）。

## ビルド/書き込み

- VS Code タスク
  - Build: 「Compile Project」（ninja）
  - Picotool ロード: 「Run Project」
  - OpenOCD Flash: 「Flash」
- 生成物: `build/dev_hid_composite.uf2`（BOOTSEL でD&D可能）

## 既知の注意点/今後の改善余地

- ダブルタップ判定幅（現在 200ms）は環境/好みで調整可。
- Alt+Tab の UI を維持（Alt を保持）する動作にも拡張可能。
- ソフト的デバウンスを追加可能（必要なら20ms程度）。
- マッピングや加速カーブ（ステップ/閾値）は運用に合わせて可変にできる。

## ピン割当（最終仕様）

- GP28: Up（マウス）
- GP27: Right（マウス）＋ ダブルタップ＝ Alt+Tab
- GP26: Down（マウス）
- GP22: Left（マウス）＋ ダブルタップ＝ Shift+Alt+Tab

---
メモ更新者: 開発セッション（2025-09-13）