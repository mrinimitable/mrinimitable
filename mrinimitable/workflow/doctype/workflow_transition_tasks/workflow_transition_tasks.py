# Copyright (c) 2025, Mrinimitable Technologies and contributors
# For license information, please see license.txt

# import mrinimitable
from mrinimitable.model.document import Document


class WorkflowTransitionTasks(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF
		from mrinimitable.workflow.doctype.workflow_transition_task.workflow_transition_task import (
			WorkflowTransitionTask,
		)

		tasks: DF.Table[WorkflowTransitionTask]
	# end: auto-generated types

	pass
