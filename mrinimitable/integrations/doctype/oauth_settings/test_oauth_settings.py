# Copyright (c) 2025, Mrinimitable Technologies and Contributors
# See license.txt

# import mrinimitable
from mrinimitable.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestOAuthSettings(IntegrationTestCase):
	"""
	Integration tests for OAuthSettings.
	Use this class for testing interactions between multiple components.
	"""

	pass
