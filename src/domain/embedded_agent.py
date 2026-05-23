"""
Embedded Agent — generates firmware, HAL, and RTOS code for
Arduino, ESP32, Raspberry Pi, and STM32 projects.

Input:  hardware_description (str), target_platform (str), peripherals (list),
        rtos (str), language (str)
Output: firmware_code, hal_code, cmake_config, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def embedded_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    hw_desc    = args.get("hardware_description", "IoT sensor node")
    platform   = args.get("target_platform", "esp32")
    perifs: List[str] = args.get("peripherals", ["uart", "i2c", "gpio"])
    rtos       = args.get("rtos", "freertos")
    language   = args.get("language", "c")

    system = (
        "You are an embedded systems expert. Return JSON: "
        "{firmware_code:str, hal_code:str, cmake_cmakelists:str, "
        "power_management_code:str, ota_update_code:str, "
        "memory_map:object, timing_analysis:object, "
        "safety_checklist:[str], pinout_config:object}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Platform: {platform}\nHardware: {hw_desc}\n"
        f"Peripherals: {json.dumps(perifs)}\nRTOS: {rtos}\nLanguage: {language}\n\n"
        "Generate complete embedded firmware."
    )

    data = _parse_json(_llm(prompt, system, "embedded_agent"), {
        "firmware_code": "// firmware stub", "hal_code": "", "cmake_cmakelists": "",
    })

    ext = "c" if language == "c" else "cpp"
    ts = _ts()
    fw_path    = _save("code", f"firmware_{platform}_{ts}.{ext}", data.get("firmware_code", ""))
    hal_path   = _save("code", f"hal_{platform}_{ts}.h",          data.get("hal_code", ""))
    cmake_path = _save("code", f"CMakeLists_{ts}.txt",            data.get("cmake_cmakelists", ""))
    ota_path   = _save("code", f"ota_update_{ts}.{ext}",          data.get("ota_update_code", ""))

    _record("embedded_agent", f"{platform}:{hw_desc}", fw_path)
    return {
        "memory_map":       data.get("memory_map", {}),
        "timing_analysis":  data.get("timing_analysis", {}),
        "safety_checklist": data.get("safety_checklist", []),
        "pinout_config":    data.get("pinout_config", {}),
        "firmware_path":    fw_path,
        "hal_path":         hal_path,
        "cmake_path":       cmake_path,
        "ota_path":         ota_path,
        "summary": f"Firmware for {platform} ({rtos}). '{hw_desc}'. → {fw_path}.",
    }
