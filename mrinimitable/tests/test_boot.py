import mrinimitable
from mrinimitable.boot import get_user_pages_or_reports
from mrinimitable.desk.doctype.note.note import _get_unseen_notes, get_unseen_notes, mark_as_seen
from mrinimitable.tests import IntegrationTestCase


class TestBootData(IntegrationTestCase):
	def test_get_unseen_notes(self):
		mrinimitable.db.delete("Note")
		mrinimitable.db.delete("Note Seen By")
		note = mrinimitable.get_doc(
			{
				"doctype": "Note",
				"title": "Test Note",
				"notify_on_login": 1,
				"content": "Test Note 1",
				"public": 1,
			}
		)
		note.insert()

		mrinimitable.set_user("test@example.com")
		_get_unseen_notes()
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, ["Test Note"])

		mark_as_seen(note.name)
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, [])


class TestPermissionQueries(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def test_get_user_pages_or_reports_with_permission_query(self):
		# Create a ToDo custom report with admin user
		mrinimitable.set_user("Administrator")
		mrinimitable.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "ToDo",
				"report_name": "Test Admin Report",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert()

		# Add permission query such that each user can only see their own custom reports
		mrinimitable.get_doc(
			doctype="Server Script",
			name="test_report_permission_query",
			script_type="Permission Query",
			reference_doctype="Report",
			script="""conditions = f"(`tabReport`.is_standard = 'Yes' or `tabReport`.owner = '{mrinimitable.session.user}')"
				""",
		).insert()

		# Create a ToDo custom report with test user
		mrinimitable.set_user("test@example.com")
		mrinimitable.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "ToDo",
				"report_name": "Test User Report",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)

		get_user_pages_or_reports("Report")
		allowed_reports = mrinimitable.cache.get_value("has_role:Report", user=mrinimitable.session.user)

		# Test user must not see admin user's report
		self.assertNotIn("Test Admin Report", allowed_reports)
		self.assertIn("Test User Report", allowed_reports)
