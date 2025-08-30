# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""
mrinimitable.coverage
~~~~~~~~~~~~~~~~

Coverage settings for mrinimitable
"""

STANDARD_INCLUSIONS = ["*.py"]

STANDARD_EXCLUSIONS = [
	"*.js",
	"*.xml",
	"*.pyc",
	"*.css",
	"*.less",
	"*.scss",
	"*.vue",
	"*.html",
	"*/test_*/*",
	"*/node_modules/*",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
]

# tested via commands' test suite
TESTED_VIA_CLI = [
	"*/mrinimitable/installer.py",
	"*/mrinimitable/utils/install.py",
	"*/mrinimitable/utils/scheduler.py",
	"*/mrinimitable/utils/doctor.py",
	"*/mrinimitable/build.py",
	"*/mrinimitable/database/__init__.py",
	"*/mrinimitable/database/db_manager.py",
	"*/mrinimitable/database/**/setup_db.py",
]

MRINIMITABLE_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/mrinimitable/change_log/*",
	"*/mrinimitable/exceptions*",
	"*/mrinimitable/desk/page/setup_wizard/setup_wizard.py",
	"*/mrinimitable/coverage.py",
	"*mrinimitable/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	*TESTED_VIA_CLI,
]


class CodeCoverage:
	"""
	Context manager for handling code coverage.

	This class sets up code coverage measurement for a specific app,
	applying the appropriate inclusion and exclusion patterns.
	"""

	def __init__(self, with_coverage, app, outfile="coverage.xml"):
		self.with_coverage = with_coverage
		self.app = app or "mrinimitable"
		self.outfile = outfile

	def __enter__(self):
		if self.with_coverage:
			import os

			from coverage import Coverage

			from mrinimitable.utils import get_shashi_path

			# Generate coverage report only for app that is being tested
			source_path = os.path.join(get_shashi_path(), "apps", self.app)
			omit = STANDARD_EXCLUSIONS[:]

			if self.app == "mrinimitable":
				omit.extend(MRINIMITABLE_EXCLUSIONS)

			self.coverage = Coverage(source=[source_path], omit=omit, include=STANDARD_INCLUSIONS)
			self.coverage.start()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if self.with_coverage:
			self.coverage.stop()
			self.coverage.save()
			self.coverage.xml_report(outfile=self.outfile)
			print("Saved Coverage")
