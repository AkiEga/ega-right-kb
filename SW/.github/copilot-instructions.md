# ega-right-kb - Copilot Instructions

Custom 50-key keyboard firmware (RP2040 + TinyUSB). Full details in [README.md](../README.md).

## Quick Reference
- **Build:** VS Code task "Compile Project" → `build/ega_right_kb.uf2`
- **Flash:** "Run Project" (picotool) or drag .uf2 to RPI-RP2 drive
- **Priority:** Implement `keyboard_switch_read()` matrix scanning in [main.c](../main.c#L179)

## Key Points
- 6×10 matrix: Columns=outputs (GPIO 0-9), Rows=inputs (GPIO 16-21)
- Columns driven low to scan, rows pulled up (active low)
- HID-only device (no CDC/MSC), 10ms polling, no RTOS
- Use VS Code tasks (handle SDK paths automatically)
