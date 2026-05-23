"""
Robotics Agent — generates ROS2 nodes, URDF robot descriptions,
motion planning config, and ISO 10218-1 safety analysis.

Input:  robot_description (str), task (str), ros_distro (str),
        dof (int), safety_category (str)
Output: ros_node_code, urdf, launch_file, safety_report, code_path
"""
from __future__ import annotations

from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def robotics_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    robot_desc    = args.get("robot_description", "6-DOF robot arm")
    task          = args.get("task", "pick and place")
    ros_distro    = args.get("ros_distro", "humble")
    dof           = int(args.get("dof", 6))
    safety_cat    = args.get("safety_category", "PLd")

    system = (
        "You are a ROS2 robotics expert. Return JSON: "
        "{ros_node_code:str (Python rclpy), urdf_xml:str, "
        "launch_file_code:str (Python), motion_planning_config:object, "
        "safety_analysis:{category:str,ple:str,pfh:float,"
        "required_measures:[str],iso10218_checklist:[str]}, "
        "moveit_config_yaml:str, nav2_config_yaml:str, "
        "sensor_fusion_code:str, test_code:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"Robot: {robot_desc}\nTask: {task}\nROS2 distro: {ros_distro}\n"
        f"DOF: {dof}\nSafety category: {safety_cat}\n\n"
        "Generate complete ROS2 implementation."
    )

    data = _parse_json(_llm(prompt, system, "robotics_agent"), {
        "ros_node_code": "# ros2 stub", "urdf_xml": "", "safety_analysis": {},
    })

    ts = _ts()
    node_path   = _save("code",    f"ros2_node_{ros_distro}_{ts}.py",    data.get("ros_node_code", ""))
    urdf_path   = _save("code",    f"robot_{ts}.urdf",                   data.get("urdf_xml", ""))
    launch_path = _save("code",    f"launch_{ts}.py",                    data.get("launch_file_code", ""))
    safety_path = _save("reports", f"iso10218_safety_{ts}.md",
                         "# Safety Analysis\n\n"
                         + str(data.get("safety_analysis", {})))

    _record("robotics_agent", f"{ros_distro}:{robot_desc}", node_path)
    return {
        "motion_planning_config": data.get("motion_planning_config", {}),
        "safety_analysis":        data.get("safety_analysis", {}),
        "node_path":              node_path,
        "urdf_path":              urdf_path,
        "launch_path":            launch_path,
        "safety_report_path":     safety_path,
        "summary": f"ROS2 ({ros_distro}) for '{robot_desc}'. {dof} DOF. → {node_path}.",
    }
