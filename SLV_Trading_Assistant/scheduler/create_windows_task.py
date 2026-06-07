# Rev 1
"""
Windows Task Scheduler XML helper for the SLV Trading Assistant.

Generates a schtasks-compatible XML file that schedules daily runs of
main.py on weekdays at a configurable time.

Usage
-----
  python scheduler/create_windows_task.py
  python scheduler/create_windows_task.py --time 07:00 --style swing --output html
  python scheduler/create_windows_task.py --install   # also registers the task via schtasks

The generated XML is saved next to this script as slv_task.xml.
To register manually without --install:
  schtasks /Create /XML scheduler\\slv_task.xml /TN "SLV Trading Assistant"
To delete:
  schtasks /Delete /TN "SLV Trading Assistant" /F
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
_XML_PATH    = _SCRIPT_DIR / "slv_task.xml"
_TASK_NAME   = "SLV Trading Assistant"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Windows Task Scheduler XML for SLV Assistant")
    p.add_argument("--time",    default="06:30",
                   help="Daily run time in HH:MM (24h, local time). Default: 06:30")
    p.add_argument("--style",   default="swing",
                   choices=["day", "swing", "position", "long_term"],
                   help="Trading style passed to main.py. Default: swing")
    p.add_argument("--output",  default="html",
                   choices=["text", "html"],
                   help="Report format. Default: html")
    p.add_argument("--install", action="store_true",
                   help="Register the task via schtasks immediately after XML generation")
    p.add_argument("--no-browser", action="store_true",
                   help="Omit --open-browser from the scheduled command")
    return p.parse_args()


def build_xml(
    python_exe: str,
    main_py:    str,
    run_time:   str,
    style:      str,
    output:     str,
    open_browser: bool,
) -> str:
    """Return a Task Scheduler XML string."""
    browser_flag = " --open-browser" if open_browser else ""
    args_str     = f"--style {style} --output {output}{browser_flag}"

    # Task Scheduler XML uses ISO 8601 for start boundary
    # We set a far-future start so the repeating trigger fires indefinitely
    start_boundary = f"2024-01-01T{run_time}:00"

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>SLV Trading Assistant - daily signal and report generation</Description>
    <Author>SLV Trading Assistant</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start_boundary}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <WeeksInterval>1</WeeksInterval>
        <DaysOfWeek>
          <Monday />
          <Tuesday />
          <Wednesday />
          <Thursday />
          <Friday />
        </DaysOfWeek>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{main_py}" {args_str}</Arguments>
      <WorkingDirectory>{_PROJECT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""


def main() -> None:
    args = parse_args()

    python_exe  = sys.executable
    main_py     = str(_PROJECT_DIR / "main.py")
    open_browser = not args.no_browser and args.output == "html"

    xml = build_xml(
        python_exe   = python_exe,
        main_py      = main_py,
        run_time     = args.time,
        style        = args.style,
        output       = args.output,
        open_browser = open_browser,
    )

    # Task Scheduler requires UTF-16 encoding for XML files
    _XML_PATH.write_text(xml, encoding="utf-16")
    print(f"[OK] Task XML written to: {_XML_PATH}")
    print(f"     Schedule : weekdays at {args.time}")
    print(f"     Command  : python main.py --style {args.style} --output {args.output}"
          + (" --open-browser" if open_browser else ""))
    print()

    if args.install:
        _register_task()
    else:
        print("To register the task, run:")
        print(f'  schtasks /Create /XML "{_XML_PATH}" /TN "{_TASK_NAME}"')
        print()
        print("To delete the task later:")
        print(f'  schtasks /Delete /TN "{_TASK_NAME}" /F')


def _register_task() -> None:
    """Invoke schtasks to register the generated XML."""
    cmd = ["schtasks", "/Create", "/XML", str(_XML_PATH), "/TN", _TASK_NAME, "/F"]
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[OK] Task registered: {_TASK_NAME}")
        if result.stdout.strip():
            print(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] schtasks failed (exit {exc.returncode}):")
        print(exc.stderr or exc.stdout or "(no output)")
        print()
        print("You can register manually:")
        print(f'  schtasks /Create /XML "{_XML_PATH}" /TN "{_TASK_NAME}"')


if __name__ == "__main__":
    main()
