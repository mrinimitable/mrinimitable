# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import copy

import mrinimitable
from mrinimitable.core.doctype.version.version import get_diff
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.tests.utils import make_test_objects


class TestVersion(IntegrationTestCase):
	def test_get_diff(self):
		mrinimitable.set_user("Administrator")
		test_records = make_test_objects("Event", reset=True)
		old_doc = mrinimitable.get_doc("Event", test_records[0])
		new_doc = copy.deepcopy(old_doc)

		old_doc.color = None
		new_doc.color = "#fafafa"

		diff = get_diff(old_doc, new_doc)["changed"]

		self.assertEqual(get_fieldnames(diff)[0], "color")
		self.assertTrue(get_old_values(diff)[0] is None)
		self.assertEqual(get_new_values(diff)[0], "#fafafa")

		new_doc.starts_on = "2017-07-20"

		diff = get_diff(old_doc, new_doc)["changed"]

		self.assertEqual(get_fieldnames(diff)[1], "starts_on")
		self.assertEqual(get_old_values(diff)[1], "01-01-2014 00:00:00")
		self.assertEqual(get_new_values(diff)[1], "07-20-2017 00:00:00")

	def test_no_version_on_new_doc(self):
		from mrinimitable.desk.form.load import get_versions

		t = mrinimitable.get_doc(doctype="ToDo", description="something")
		t.save(ignore_version=False)

		self.assertFalse(get_versions(t))

		t = mrinimitable.get_doc(t.doctype, t.name)
		t.description = "changed"
		t.save(ignore_version=False)
		self.assertTrue(get_versions(t))


def get_fieldnames(change_array):
	return [d[0] for d in change_array]


def get_old_values(change_array):
	return [d[1] for d in change_array]


def get_new_values(change_array):
	return [d[2] for d in change_array]
