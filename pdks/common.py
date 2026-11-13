"""PDK-neutral helpers shared by the driver and the adapters."""
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AdapterError(Exception):
    """A problem the user should read as-is (the message is shown unchanged)."""


@dataclass
class CheckResult:
    ok: bool
    count: int        # violations, mismatches; -1 if the checker did not complete
    report: Path
    detail: str       # one line for the result table


def run_tool(argv: list, cwd: Path, log: Path, timeout: int = 600) -> int:
    """Run a command with output going to `log`. Returns its exit code, or -1 on
    timeout or when the executable cannot be started."""
    Path(cwd).mkdir(parents=True, exist_ok=True)
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as f:
        try:
            r = subprocess.run([str(a) for a in argv], cwd=cwd, stdout=f,
                               stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            f.write(f"\n[timeout after {timeout}s]\n")
            return -1
        except OSError as e:
            f.write(f"\n[cannot run {argv[0]}: {e}]\n")
            return -1
    return r.returncode
