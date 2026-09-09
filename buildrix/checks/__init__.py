"""Local checks for skills and tasks.

The same code runs on the contributor's machine (``buildrix skill check``,
``buildrix task check``) and on the hub at upload, so nothing is ever rejected
only after submitting.
"""

from buildrix.checks.skill import check_skill
from buildrix.checks.task import check_task

__all__ = ["check_skill", "check_task"]
