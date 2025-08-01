import mrinimitable
from mrinimitable.utils import update_progress_bar


def execute():
	mrinimitable.db.auto_commit_on_many_writes = True

	Sessions = mrinimitable.qb.DocType("Sessions")

	current_sessions = (mrinimitable.qb.from_(Sessions).select(Sessions.sid, Sessions.sessiondata)).run(
		as_dict=True
	)

	for i, session in enumerate(current_sessions):
		try:
			new_data = mrinimitable.as_json(mrinimitable.safe_eval(session.sessiondata))
		except Exception:
			# Rerunning patch or already converted.
			continue

		(
			mrinimitable.qb.update(Sessions).where(Sessions.sid == session.sid).set(Sessions.sessiondata, new_data)
		).run()
		update_progress_bar("Patching sessions", i, len(current_sessions))
