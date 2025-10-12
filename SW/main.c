/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Ha Thach (tinyusb.org)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board_api.h"
#include "tusb.h"

#include "usb_descriptors.h"
#include "hardware/gpio.h"

// Portable fallback for C11 Annex K memset_s (not provided by newlib on many embedded toolchains)
#ifndef __STDC_LIB_EXT1__
static inline int memset_s(void *s, size_t smax, int c, size_t n) {
    if (s == NULL) return 22;                // EINVAL
    if (n > smax) return 22;                 // EINVAL
    memset(s, c, n); // NOLINT(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
    return 0;
}
#endif

//--------------------------------------------------------------------+
// MACRO CONSTANT TYPEDEF PROTYPES
//--------------------------------------------------------------------+
// Bit patterns for directions (wrapped in parentheses for macro safety)
#define BIT_PTRN_UP    (0b0001)
#define BIT_PTRN_DOWN  (0b0010)
#define BIT_PTRN_LEFT  (0b0100)
#define BIT_PTRN_RIGHT (0b1000)

// GPIO pin mapping for directional buttons
// GPIO pin mapping for directional buttons (wrapped in parentheses)
#define GPIO_AS_UP_BTN    (28)
#define GPIO_AS_RIGHT_BTN (27)
#define GPIO_AS_DOWN_BTN  (26)
#define GPIO_AS_LEFT_BTN  (22)
// Mouse click button
// Mouse click button
#define GPIO_AS_CLICK_BTN (2)

enum { IDX_UP    = 0,
       IDX_RIGHT = 1,
       IDX_DOWN  = 2,
       IDX_LEFT  = 3,
       DIR_COUNT = 4 };
static const uint32_t DIR_BITS[DIR_COUNT] = {BIT_PTRN_UP, BIT_PTRN_RIGHT, BIT_PTRN_DOWN, BIT_PTRN_LEFT};

// 押下履歴（直近10件）
#define HISTORY_SIZE (10)
typedef struct {
    uint32_t t_ms;    // 記録時刻（ms）
    uint8_t  dir_idx; // IDX_UP/IDX_RIGHT/IDX_DOWN/IDX_LEFT
} key_event_t;
static key_event_t g_history[HISTORY_SIZE];
static uint8_t     g_hist_head  = 0; // 次に書く位置
static uint8_t     g_hist_count = 0; // 現在の要素数（最大HISTORY_SIZE）

// 長押しカウンタ（10ms刻み）
static uint32_t g_hold_ticks[DIR_COUNT] = {0};

// キーボードマクロ（Alt+Tab 等）送信用の簡易ステート
typedef struct {
    bool    active;  // マクロ処理中
    uint8_t stage;   // 0: 押下送信待ち, 1: 解放送信待ち
    uint8_t mods;    // 修飾キー
    uint8_t keys[6]; // キー配列
} kbd_macro_t;
static kbd_macro_t g_kbd_macro = {0};

static inline void history_push(uint8_t dir_idx) {
    key_event_t ev;
    ev.t_ms                = board_millis();
    ev.dir_idx             = dir_idx;
    g_history[g_hist_head] = ev;
    g_hist_head            = (uint8_t) ((g_hist_head + 1) % HISTORY_SIZE);
    if (g_hist_count < HISTORY_SIZE)
        g_hist_count++;
}

static inline int8_t step_from_hold(uint32_t ticks) {
    // 10ms周期カウント: ~0-190ms:4, 200-490ms:8, 500-990ms:12, 1000ms~:18
    if (ticks >= 100)
        return 18; // >= 100*10ms = 1000ms
    if (ticks >= 50)
        return 12; // >= 500ms
    if (ticks >= 20)
        return 8; // >= 200ms
    return 4;     // 初期速度
}

/* Blink pattern
 * - 250 ms  : device not mounted
 * - 1000 ms : device mounted
 * - 2500 ms : device is suspended
 */
enum {
    BLINK_NOT_MOUNTED = 250,
    BLINK_MOUNTED     = 1000,
    BLINK_SUSPENDED   = 2500,
};

static uint32_t blink_interval_ms = BLINK_NOT_MOUNTED;

void led_blinking_task(void);
void hid_task(void);

/*------------- MAIN -------------*/
int main(void) {
    board_init();
    // 入力ピンの初期化（内部プルアップ有効、Lowで押下）
    const uint key_pins[] = {GPIO_AS_UP_BTN, GPIO_AS_RIGHT_BTN, GPIO_AS_DOWN_BTN, GPIO_AS_LEFT_BTN, GPIO_AS_CLICK_BTN};
    for (size_t i = 0; i < (sizeof(key_pins) / sizeof(key_pins[0])); ++i) {
        gpio_init(key_pins[i]);
        gpio_set_dir(key_pins[i], GPIO_IN);
        gpio_pull_up(key_pins[i]);
    }

    // init device stack on configured roothub port
    tud_init(BOARD_TUD_RHPORT);

    if (board_init_after_tusb) {
        board_init_after_tusb();
    }

    while (1) {
        tud_task(); // tinyusb device task
        led_blinking_task();

        hid_task();
    }
}

//--------------------------------------------------------------------+
// Device callbacks
//--------------------------------------------------------------------+

// Invoked when device is mounted
void tud_mount_cb(void) {
    blink_interval_ms = BLINK_MOUNTED;
}

// Invoked when device is unmounted
void tud_umount_cb(void) {
    blink_interval_ms = BLINK_NOT_MOUNTED;
}

// Invoked when usb bus is suspended
// remote_wakeup_en : if host allow us  to perform remote wakeup
// Within 7ms, device must draw an average of current less than 2.5 mA from bus
void tud_suspend_cb(bool remote_wakeup_en) {
    (void) remote_wakeup_en;
    blink_interval_ms = BLINK_SUSPENDED;
}

// Invoked when usb bus is resumed
void tud_resume_cb(void) {
    blink_interval_ms = tud_mounted() ? BLINK_MOUNTED : BLINK_NOT_MOUNTED;
}

//--------------------------------------------------------------------+
// USB HID
//--------------------------------------------------------------------+

static void send_hid_report(uint8_t report_id, uint32_t pressed_mask) {
    // skip if hid is not ready yet
    if (!tud_hid_ready())
        return;

    switch (report_id) {
    case REPORT_ID_MOUSE: {
        // 方向割当: bit0:GP28=Left, bit1:GP27=Right, bit2:GP26=Up, bit3:GP22=Down
        int8_t dx = 0, dy = 0;
        if (pressed_mask & BIT_PTRN_LEFT)
            dx -= step_from_hold(g_hold_ticks[IDX_LEFT]); // Left
        if (pressed_mask & BIT_PTRN_RIGHT)
            dx += step_from_hold(g_hold_ticks[IDX_RIGHT]); // Right
        if (pressed_mask & BIT_PTRN_UP)
            dy -= step_from_hold(g_hold_ticks[IDX_UP]); // Up
        if (pressed_mask & BIT_PTRN_DOWN)
            dy += step_from_hold(g_hold_ticks[IDX_DOWN]); // Down

        // 変化がない場合は送信をスキップ（無駄なトラフィック抑制）
        uint8_t buttons = (gpio_get(GPIO_AS_CLICK_BTN) == 0) ? 0x01 : 0x00; // 左クリック
        if (dx != 0 || dy != 0 || buttons != 0) {
            tud_hid_mouse_report(REPORT_ID_MOUSE, buttons, dx, dy, 0, 0);
        }
    } break;

    default:
        break;
    }
}

// Every 10ms, we will sent 1 report for each HID profile (keyboard, mouse etc ..)
// tud_hid_report_complete_cb() is used to send the next report after previous one is complete
void hid_task(void) {
    // Poll every 10ms
    const uint32_t  interval_ms = 10;
    static uint32_t start_ms    = 0;
    static uint32_t prev_mask   = 0;
    // ダブルタップ検出用（同一方向の連続押下の時間間隔をみる）
    static uint32_t last_press_time[DIR_COUNT] = {0};
    // static uint8_t  last_was_pressed[DIR_COUNT] = {0}; // 未使用

    if (board_millis() - start_ms < interval_ms)
        return; // not enough time
    start_ms += interval_ms;

    // 各GPIOの押下状態をビットマスク化
    uint32_t pressed_mask = 0;
    if (gpio_get(GPIO_AS_UP_BTN) == 0)
        pressed_mask |= BIT_PTRN_UP;
    if (gpio_get(GPIO_AS_RIGHT_BTN) == 0)
        pressed_mask |= BIT_PTRN_RIGHT;
    if (gpio_get(GPIO_AS_DOWN_BTN) == 0)
        pressed_mask |= BIT_PTRN_DOWN;
    if (gpio_get(GPIO_AS_LEFT_BTN) == 0)
        pressed_mask |= BIT_PTRN_LEFT;

    // 押下エッジ検出（履歴に記録 & ダブルタップ）
    uint32_t rising = pressed_mask & ~prev_mask;
    for (uint8_t i = 0; i < DIR_COUNT; ++i) {
        if (rising & DIR_BITS[i]) {
            history_push(i);
            // ダブルタップ：200ms以内に同方向を2回
            uint32_t now       = board_millis();
            uint32_t delta     = now - last_press_time[i];
            last_press_time[i] = now;
            if (delta <= 200) {
                // 右右 => Alt+Tab, 左左 => Shift+Alt+Tab
                if (!g_kbd_macro.active) {
                    g_kbd_macro.active = true;
                    g_kbd_macro.stage  = 0; // 押下送信から開始
                    (void)memset_s(g_kbd_macro.keys,
                                   sizeof(g_kbd_macro.keys),
                                   0,
                                   sizeof(g_kbd_macro.keys));
                    g_kbd_macro.keys[0] = HID_KEY_TAB;
                    if (i == IDX_RIGHT) {
                        g_kbd_macro.mods = KEYBOARD_MODIFIER_LEFTALT;
                    } else if (i == IDX_LEFT) {
                        g_kbd_macro.mods = KEYBOARD_MODIFIER_LEFTALT | KEYBOARD_MODIFIER_LEFTSHIFT;
                    } else {
                        g_kbd_macro.active = false; // 対象外方向
                    }
                }
            }
        }
    }

    // 長押しカウンタ更新
    for (uint8_t i = 0; i < DIR_COUNT; ++i) {
        if (pressed_mask & DIR_BITS[i]) {
            if (g_hold_ticks[i] < 1000000u)
                g_hold_ticks[i]++; // 過剰なオーバーフロー防止
        } else {
            g_hold_ticks[i] = 0;
        }
    }
    prev_mask = pressed_mask;

    // Remote wakeup
    if (tud_suspended() && (pressed_mask || (gpio_get(GPIO_AS_CLICK_BTN) == 0))) {
        // Wake up host if we are in suspend mode
        // and REMOTE_WAKEUP feature is enabled by host
        tud_remote_wakeup();
    } else {
        // 先にキーボードマクロの押下が未送信なら送る
        if (g_kbd_macro.active && g_kbd_macro.stage == 0 && tud_hid_ready()) {
            tud_hid_keyboard_report(REPORT_ID_KEYBOARD, g_kbd_macro.mods, g_kbd_macro.keys);
            g_kbd_macro.stage = 1; // 次は解放
        }
        // マウス移動を送信
        send_hid_report(REPORT_ID_MOUSE, pressed_mask);
    }
}

// Invoked when sent REPORT successfully to host
// Application can use this to send the next report
// Note: For composite reports, report[0] is report ID
void tud_hid_report_complete_cb(uint8_t instance, uint8_t const* report, uint16_t len) {
    (void) instance;
    (void) len;

    uint8_t next_report_id = report[0] + 1u;

    // 直前がキーボードレポートで、マクロの解放が残っていれば先に解放を送る
    if (report[0] == REPORT_ID_KEYBOARD && g_kbd_macro.active && g_kbd_macro.stage == 1) {
        tud_hid_keyboard_report(REPORT_ID_KEYBOARD, 0, NULL); // 解放
        g_kbd_macro.active = false;
        g_kbd_macro.stage  = 0;
        return; // このコールバックではここで終了
    }

    if (next_report_id < REPORT_ID_COUNT) {
        // 連鎖レポート送信時も現状の押下マスクを使用（マクロで統一）
        uint32_t pressed_mask = 0;
        if (gpio_get(GPIO_AS_UP_BTN) == 0)
            pressed_mask |= BIT_PTRN_UP;
        if (gpio_get(GPIO_AS_RIGHT_BTN) == 0)
            pressed_mask |= BIT_PTRN_RIGHT;
        if (gpio_get(GPIO_AS_DOWN_BTN) == 0)
            pressed_mask |= BIT_PTRN_DOWN;
        if (gpio_get(GPIO_AS_LEFT_BTN) == 0)
            pressed_mask |= BIT_PTRN_LEFT;
        send_hid_report(next_report_id, pressed_mask);
    }
}

// Invoked when received GET_REPORT control request
// Application must fill buffer report's content and return its length.
// Return zero will cause the stack to STALL request
uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type, uint8_t* buffer, uint16_t reqlen) {
    // TODO not Implemented
    (void) instance;
    (void) report_id;
    (void) report_type;
    (void) buffer;
    (void) reqlen;

    return 0;
}

// Invoked when received SET_REPORT control request or
// received data on OUT endpoint ( Report ID = 0, Type = 0 )
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type, uint8_t const* buffer, uint16_t bufsize) {
    (void) instance;
    (void) report_id;
    (void) report_type;
    (void) buffer;
    (void) bufsize;
    // マウス専用のため、SET_REPORTで行う処理はなし
}

//--------------------------------------------------------------------+
// BLINKING TASK
//--------------------------------------------------------------------+
void led_blinking_task(void) {
    static uint32_t start_ms  = 0;
    static bool     led_state = false;

    // blink is disabled
    if (!blink_interval_ms)
        return;

    // Blink every interval ms
    if (board_millis() - start_ms < blink_interval_ms)
        return; // not enough time
    start_ms += blink_interval_ms;

    board_led_write(led_state);
    led_state = 1 - led_state; // toggle
}
