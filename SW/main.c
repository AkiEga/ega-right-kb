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

// Keyboard state structure to hold all 50 keys
typedef struct {
  // Modifier keys (8 bits)
  struct {
    uint8_t left_ctrl  : 1;
    uint8_t left_shift : 1;
    uint8_t left_alt   : 1;
    uint8_t left_gui   : 1;  // Windows/Command key
    uint8_t right_ctrl : 1;
    uint8_t right_shift: 1;
    uint8_t right_alt  : 1;
    uint8_t right_gui  : 1;
  } modifiers;

  // Regular keys (up to 42 keys for alphanumeric and other keys)
  // Using bit field for each key position
  uint64_t keys;  // 64 bits = enough for 50 keys (row * 10 + col)
} keyboard_state_t;

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

void hid_task(void);

/*------------- MAIN -------------*/
int main(void)
{
  board_init();

  // init output pins（pull-up, high)
  const uint output_pins[] = {GPIO_COL_0, GPIO_COL_1, GPIO_COL_2, GPIO_COL_3,
                             GPIO_COL_4, GPIO_COL_5, GPIO_COL_6, GPIO_COL_7,
                             GPIO_COL_8, GPIO_COL_9 };
  for (size_t i = 0; i < (sizeof(output_pins) / sizeof(output_pins[0])); ++i) {
    gpio_init(output_pins[i]);
    gpio_set_dir(output_pins[i], GPIO_OUT);
    gpio_pull_up(output_pins[i]);
    gpio_put(output_pins[i], 1);
  }

  const uint input_pins[] = {GPIO_ROW_0, GPIO_ROW_1, GPIO_ROW_2, GPIO_ROW_3,
                            GPIO_ROW_4, GPIO_ROW_5};
  for (size_t i = 0; i < (sizeof(input_pins) / sizeof(input_pins[0])); ++i) {
    gpio_init(input_pins[i]);
    gpio_set_dir(input_pins[i], GPIO_IN);
    gpio_pull_up(input_pins[i]);
  }

  // init device stack on configured roothub port
  tud_init(BOARD_TUD_RHPORT);

  if (board_init_after_tusb) {
    board_init_after_tusb();
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
// remote_wakeup_en : if host allow us  to perform remote wakeup
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

static void send_hid_report(uint8_t report_id, const keyboard_state_t* state)
{
  // skip if hid is not ready yet
  if ( !tud_hid_ready() ) return;

  switch(report_id)
  {
    case REPORT_ID_KEYBOARD:
    {
      // use to avoid send multiple consecutive zero report for keyboard
      static bool has_keyboard_key = false;

      // Check if any key is pressed
      bool has_key = (state->keys != 0);

      if ( has_key )
      {
        // Build modifier byte from bit fields
        uint8_t modifier = 0;
        if (state->modifiers.left_ctrl)   modifier |= KEYBOARD_MODIFIER_LEFTCTRL;
        if (state->modifiers.left_shift)  modifier |= KEYBOARD_MODIFIER_LEFTSHIFT;
        if (state->modifiers.left_alt)    modifier |= KEYBOARD_MODIFIER_LEFTALT;
        if (state->modifiers.left_gui)    modifier |= KEYBOARD_MODIFIER_LEFTGUI;
        if (state->modifiers.right_ctrl)  modifier |= KEYBOARD_MODIFIER_RIGHTCTRL;
        if (state->modifiers.right_shift) modifier |= KEYBOARD_MODIFIER_RIGHTSHIFT;
        if (state->modifiers.right_alt)   modifier |= KEYBOARD_MODIFIER_RIGHTALT;
        if (state->modifiers.right_gui)   modifier |= KEYBOARD_MODIFIER_RIGHTGUI;

        // TODO: Map bit positions to HID keycodes
        // For now, send HID_KEY_A as placeholder
        uint8_t keycode[6] = { 0 };
        keycode[0] = HID_KEY_A;

        tud_hid_keyboard_report(REPORT_ID_KEYBOARD, modifier, keycode);
        has_keyboard_key = true;
      }else
      {
        // send empty key report if previously has key pressed
        if (has_keyboard_key) tud_hid_keyboard_report(REPORT_ID_KEYBOARD, 0, NULL);
        has_keyboard_key = false;
      }
    }
    break;

    case REPORT_ID_MOUSE:
    {
      int8_t const delta = 5;

      // no button, right + down, no scroll, no pan
      tud_hid_mouse_report(REPORT_ID_MOUSE, 0x00, delta, delta, 0, 0);
    }
    break;

    default: break;
  }
}

// @brief keyboard switch read function
// Scan the keyboard matrix and return the key states as a structure
// @param state Pointer to keyboard_state_t to store the scan results
void keyboard_switch_read(keyboard_state_t* state)
{
  // Clear the state
  memset(state, 0, sizeof(keyboard_state_t));

  // Column GPIO pins array (outputs)
  const uint col_pins[] = {GPIO_COL_0, GPIO_COL_1, GPIO_COL_2, GPIO_COL_3,
                           GPIO_COL_4, GPIO_COL_5, GPIO_COL_6, GPIO_COL_7,
                           GPIO_COL_8, GPIO_COL_9};
  
  // Row GPIO pins array (inputs)
  const uint row_pins[] = {GPIO_ROW_0, GPIO_ROW_1, GPIO_ROW_2, 
                           GPIO_ROW_3, GPIO_ROW_4, GPIO_ROW_5};

  // Scan each column
  for (uint col = 0; col < 10; ++col) {
    // Set current column low (active)
    gpio_put(col_pins[col], 0);
    
    // Small delay to allow signal to stabilize
    sleep_us(1);

    // Read all rows
    for (uint row = 0; row < 6; ++row) {
      // If row is low, key is pressed (active low with pull-up)
      if (gpio_get(row_pins[row]) == 0) {
        // Calculate bit position for this key
        // Layout: row 0-5, col 0-9 = bit position 0-49
        uint32_t bit_pos = row * 10 + col;
        
        if (bit_pos < 64) {  // Safety check for 64-bit field
          // Set the corresponding bit in the keys field
          state->keys |= (1ULL << bit_pos);
        }
      }
    }

  static keyboard_state_t key_state;
  keyboard_switch_read(&key_state);

  // Remote wakeup
  if ( tud_suspended() && key_state.keys != 0 )
  {
    // Wake up host if we are in suspend mode
    // and REMOTE_WAKEUP feature is enabled by host
    tud_remote_wakeup();
  }else
  {
    // 
    // Send the 1st of report chain, the rest will be sent by tud_hid_report_complete_cb()
    send_hid_report(REPORT_ID_KEYBOARD, &key_state
  if ( board_millis() - start_ms < interval_ms) return; // not enough time
  start_ms += interval_ms;

  uint32_t const btn = keyboard_switch_read();

  // Remote wakeup
  if ( tud_suspended() && btn )
  {
    // Wake up host if we are in suspend mode
    // and REMOTE_WAKEUP feature is enabled by host
    tud_remote_wakeup();
  }else
  {
    // 
    /tatic keyboard_state_t key_state;
    keyboard_switch_read(&key_state);
    send_hid_report(next_report_id, &key_state by tud_hid_report_complete_cb()
    send_hid_report(REPORT_ID_KEYBOARD, btn);
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
    send_hid_report(next_report_id, keyboard_switch_read());
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
}

