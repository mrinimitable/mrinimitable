import mrinimitable
import mrinimitable.share


def execute():
	for user in mrinimitable.STANDARD_USERS:
		mrinimitable.share.remove("User", user, user)
