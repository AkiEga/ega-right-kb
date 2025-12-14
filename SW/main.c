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

//--------------------------------------------------------------------+
// MACRO CONSTANT TYPEDEF PROTYPES
//--------------------------------------------------------------------+

// Matrix dimensions
#define NUM_ROWS 6
#define NUM_COLS 10
#define NUM_KEYS 50

// GPIO pin for keyboard as matrix circuit
#define GPIO_ROW_0 (21)
#define GPIO_ROW_1 (20)
#define GPIO_ROW_2 (19)
#define GPIO_ROW_3 (18)
#define GPIO_ROW_4 (17)
#define GPIO_ROW_5 (16)

#define GPIO_COL_0 (4)
#define GPIO_COL_1 (5)
#define GPIO_COL_2 (6)
#define GPIO_COL_3 (7)
#define GPIO_COL_4 (8)
#define GPIO_COL_5 (9)
#define GPIO_COL_6 (3)
#define GPIO_COL_7 (2)
#define GPIO_COL_8 (1)
#define GPIO_COL_9 (0)

// Row and Column GPIO arrays
static const uint row_pins[NUM_ROWS] = {
  GPIO_ROW_0, GPIO_ROW_1, GPIO_ROW_2, 
  GPIO_ROW_3, GPIO_ROW_4, GPIO_ROW_5
};

static const uint col_pins[NUM_COLS] = {
  GPIO_COL_0, GPIO_COL_1, GPIO_COL_2, GPIO_COL_3, GPIO_COL_4,
  GPIO_COL_5, GPIO_COL_6, GPIO_COL_7, GPIO_COL_8, GPIO_COL_9
};

// Key to HID keycode mapping table
// Index = row * 10 + col, Value = HID keycode
// Based on README.md matrix layout (JIS layout right-hand side)
static const uint8_t keycode_map[NUM_ROWS][NUM_COLS] = {
  // ROW0: F4, F5, F6, F7, F8, F9, F10, F11, F12, (empty)
  { HID_KEY_F4, HID_KEY_F5, HID_KEY_F6, HID_KEY_F7, HID_KEY_F8, 
    HID_KEY_F9, HID_KEY_F10, HID_KEY_F11, HID_KEY_F12, 0 },
  
  // ROW1: 5, 6, 7, 8, 9, 0, -, ^, \, Backspace
  { HID_KEY_5, HID_KEY_6, HID_KEY_7, HID_KEY_8, HID_KEY_9,
    HID_KEY_0, HID_KEY_MINUS, HID_KEY_EQUAL, HID_KEY_BACKSLASH, HID_KEY_BACKSPACE },
  
  // ROW2: T, Y, U, I, O, P, @, [, Enter, (empty)
  { HID_KEY_T, HID_KEY_Y, HID_KEY_U, HID_KEY_I, HID_KEY_O,
    HID_KEY_P, HID_KEY_BRACKET_LEFT, HID_KEY_BRACKET_RIGHT, HID_KEY_ENTER, 0 },
  
  // ROW3: G, H, J, K, L, ;, :, ](む), (empty), (empty)
  // HID_KEY_EUROPE_1 (0x32) = JIS "む" key (] and })
  { HID_KEY_G, HID_KEY_H, HID_KEY_J, HID_KEY_K, HID_KEY_L,
    HID_KEY_SEMICOLON, HID_KEY_APOSTROPHE, HID_KEY_EUROPE_1, 0, 0 },
  
  // ROW4: B, N, M, <(,), >(.), /, \(ろ), RShift, (empty), (empty)
  // HID_KEY_KANJI1 (0x87) = JIS "ろ" key (\ and _)
  { HID_KEY_B, HID_KEY_N, HID_KEY_M, HID_KEY_COMMA, HID_KEY_PERIOD,
    HID_KEY_SLASH, HID_KEY_KANJI1, 0, 0, 0 },
  
  // ROW5: 無変換, Space, 変換, Alt, Context, RCtrl, (empty), (empty), (empty), (empty)
  // HID_KEY_KANJI2 (0x88) = 無変換, HID_KEY_KANJI4 (0x8A) = 変換
  { HID_KEY_KANJI2, HID_KEY_SPACE, HID_KEY_KANJI4, 0, HID_KEY_APPLICATION, 0, 0, 0, 0, 0 }
};

// Modifier key positions (row * 10 + col)
#define KEY_POS_RSHIFT  (4 * 10 + 7)  // SW44 - Right Shift
#define KEY_POS_RALT    (5 * 10 + 3)  // SW48 - Right Alt
#define KEY_POS_RCTRL   (5 * 10 + 5)  // SW50 - Right Ctrl

// Keyboard state - 64 bits for up to 60 keys
static uint64_t g_key_state = 0;

void hid_task(void);
void keyboard_switch_read(uint64_t* key_state);

/*------------- MAIN -------------*/
int main(void)
{
  board_init();

  // init device stack on configured roothub port
  tud_init(BOARD_TUD_RHPORT);

  if (board_init_after_tusb) {
    board_init_after_tusb();
  }

  // GPIO initialization AFTER board_init to ensure our settings are not overwritten
  // init output pins (columns - active low scan)
  for (size_t i = 0; i < NUM_COLS; ++i) {
    gpio_init(col_pins[i]);
    gpio_set_dir(col_pins[i], GPIO_OUT);
    gpio_put(col_pins[i], 1);  // Default high (inactive)
  }

  // init input pins (rows - pull-up, read low when key pressed)
  for (size_t i = 0; i < NUM_ROWS; ++i) {
    gpio_init(row_pins[i]);
    gpio_set_dir(row_pins[i], GPIO_IN);
    gpio_pull_up(row_pins[i]);
  }

  while (1)
  {
    tud_task(); // tinyusb device task
    hid_task();
  }
}

//--------------------------------------------------------------------+
// Device callbacks
//--------------------------------------------------------------------+

// Invoked when device is mounted
void tud_mount_cb(void)
{
}

// Invoked when device is unmounted
void tud_umount_cb(void)
{
}

// Invoked when usb bus is suspended
// remote_wakeup_en : if host allow us to perform remote wakeup
// Within 7ms, device must draw an average of current less than 2.5 mA from bus
void tud_suspend_cb(bool remote_wakeup_en)
{
  (void) remote_wakeup_en;
}

// Invoked when usb bus is resumed
void tud_resume_cb(void)
{
}

//--------------------------------------------------------------------+
// USB HID
//--------------------------------------------------------------------+

// @brief keyboard switch read function
// Scan the keyboard matrix and return the key states as a bitmask
// @param key_state Pointer to uint64_t to store the scan results (bit per key)
void keyboard_switch_read(uint64_t* key_state)
{
  *key_state = 0;

  // Scan each column (output)
  for (uint col = 0; col < NUM_COLS; ++col) {
    // Set current column low (active)
    gpio_put(col_pins[col], 0);
    
    // Delay to allow signal to stabilize
    sleep_us(10);

    // Read all rows (input)
    for (uint row = 0; row < NUM_ROWS; ++row) {
      // If row is low, key is pressed (active low with pull-up)
      if (gpio_get(row_pins[row]) == 0) {
        // Calculate bit position for this key
        uint32_t bit_pos = row * NUM_COLS + col;
        *key_state |= (1ULL << bit_pos);
      }
    }

    // Set column back to high (inactive)
    gpio_put(col_pins[col], 1);
    
    // Small delay before next column
    sleep_us(5);
  }
}

// Build HID report from key state bitmask
static void send_hid_report(uint8_t report_id, uint64_t key_state)
{
  // skip if hid is not ready yet
  if (!tud_hid_ready()) return;

  switch(report_id)
  {
    case REPORT_ID_KEYBOARD:
    {
      static bool has_keyboard_key = false;

      if (key_state != 0)
      {
        uint8_t modifier = 0;
        uint8_t keycode[6] = { 0 };
        uint8_t key_count = 0;

        // Check modifier keys and build keycode array
        for (uint row = 0; row < NUM_ROWS && key_count < 6; ++row) {
          for (uint col = 0; col < NUM_COLS && key_count < 6; ++col) {
            uint32_t bit_pos = row * NUM_COLS + col;
            
            if (key_state & (1ULL << bit_pos)) {
              // Check if this is a modifier key
              if (bit_pos == KEY_POS_RSHIFT) {
                modifier |= KEYBOARD_MODIFIER_RIGHTSHIFT;
              } else if (bit_pos == KEY_POS_RALT) {
                modifier |= KEYBOARD_MODIFIER_RIGHTALT;
              } else if (bit_pos == KEY_POS_RCTRL) {
                modifier |= KEYBOARD_MODIFIER_RIGHTCTRL;
              } else {
                // Regular key - add to keycode array
                uint8_t kc = keycode_map[row][col];
                if (kc != 0 && key_count < 6) {
                  keycode[key_count++] = kc;
                }
              }
            }
          }
        }

        tud_hid_keyboard_report(REPORT_ID_KEYBOARD, modifier, keycode);
        has_keyboard_key = true;
      }
      else
      {
        // send empty key report if previously had key pressed
        if (has_keyboard_key) {
          tud_hid_keyboard_report(REPORT_ID_KEYBOARD, 0, NULL);
        }
        has_keyboard_key = false;
      }
    }
    break;

    case REPORT_ID_MOUSE:
    {
      // Mouse report - not used for keyboard only
      // tud_hid_mouse_report(REPORT_ID_MOUSE, 0x00, 0, 0, 0, 0);
    }
    break;

    default: break;
  }
}

// HID task - called from main loop
void hid_task(void)
{
  // Poll every 10ms
  const uint32_t interval_ms = 10;
  static uint32_t start_ms = 0;

  if (board_millis() - start_ms < interval_ms) return;
  start_ms += interval_ms;

  // Read keyboard matrix
  keyboard_switch_read(&g_key_state);

  // LED on when any key is pressed
  board_led_write(g_key_state != 0);

  // Remote wakeup
  if (tud_suspended() && g_key_state != 0)
  {
    // Wake up host if we are in suspend mode
    // and REMOTE_WAKEUP feature is enabled by host
    tud_remote_wakeup();
  }
  else
  {
    // Send keyboard report
    send_hid_report(REPORT_ID_KEYBOARD, g_key_state);
  }
}

// Invoked when sent REPORT successfully to host
// Application can use this to send the next report
// Note: For composite reports, report[0] is report ID
void tud_hid_report_complete_cb(uint8_t instance, uint8_t const* report, uint16_t len)
{
  (void) instance;
  (void) len;

  uint8_t next_report_id = report[0] + 1u;

  if (next_report_id < REPORT_ID_COUNT)
  {
    send_hid_report(next_report_id, g_key_state);
  }
}

// Invoked when received GET_REPORT control request
// Application must fill buffer report's content and return its length.
// Return zero will cause the stack to STALL request
uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type, uint8_t* buffer, uint16_t reqlen)
{
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
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type, uint8_t const* buffer, uint16_t bufsize)
{
  (void) instance;
  (void) report_id;
  (void) report_type;
  (void) buffer;
  (void) bufsize;
}

