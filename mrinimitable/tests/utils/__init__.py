import logging

import mrinimitable

logger = logging.Logger(__file__)

from .generators import *


def check_orpahned_doctypes():
	"""Check that all doctypes in DB actually exist after patch test"""
	from mrinimitable.model.base_document import get_controller

	doctypes = mrinimitable.get_all("DocType", {"custom": 0}, pluck="name")
	orpahned_doctypes = []

	for doctype in doctypes:
		try:
			get_controller(doctype)
		except ImportError:
			orpahned_doctypes.append(doctype)

	if orpahned_doctypes:
		mrinimitable.throw(
			"Following doctypes exist in DB without controller.\n {}".format("\n".join(orpahned_doctypes))
		)


def toggle_test_mode(enable: bool):
	"""Enable or disable `mrinimitable.in_test` (and related deprecated flag)"""
	mrinimitable.in_test = enable
	mrinimitable.local.flags.in_test = enable


from mrinimitable.deprecation_dumpster import (
	get_tests_CompatMrinimitableTestCase,
)
from mrinimitable.deprecation_dumpster import (
	tests_change_settings as change_settings,
)
from mrinimitable.deprecation_dumpster import (
	tests_debug_on as debug_on,
)

MrinimitableTestCase = get_tests_CompatMrinimitableTestCase()

from mrinimitable.deprecation_dumpster import (
	tests_patch_hooks as patch_hooks,
)
from mrinimitable.deprecation_dumpster import (
	tests_timeout as timeout,
)
from mrinimitable.deprecation_dumpster import (
	tests_utils_get_dependencies as get_dependencies,
)
