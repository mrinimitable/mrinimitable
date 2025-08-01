# Copyright (c) 2024, Mrinimitable Technologies and contributors
# For license information, please see license.txt

# import mrinimitable
from mrinimitable.model.document import Document


class SystemHealthReportWorkers(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		count: DF.Int
		failed_jobs: DF.Int
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		queues: DF.Data | None
		utilization: DF.Percent
	# end: auto-generated types

	def db_insert(self, *args, **kwargs):
		raise NotImplementedError

	def load_from_db(self):
		raise NotImplementedError

	def db_update(self):
		raise NotImplementedError

	def delete(self):
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs):
		pass

	@staticmethod
	def get_count(filters=None, **kwargs):
		pass

	@staticmethod
	def get_stats(**kwargs):
		pass
