import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: mrinimitable.boot.sentry_dsn,
	release: mrinimitable?.boot?.versions?.mrinimitable,
	autoSessionTracking: false,
	initialScope: {
		// don't use mrinimitable.session.user, it's set much later and will fail because of async loading
		user: { id: mrinimitable.boot.sitename },
		tags: { mrinimitable_user: mrinimitable.boot.user.name ?? "Unidentified" },
	},
	beforeSend(event, hint) {
		// Check if it was caused by mrinimitable.throw()
		if (
			hint.originalException instanceof Error &&
			hint.originalException.stack &&
			hint.originalException.stack.includes("mrinimitable.throw")
		) {
			return null;
		}
		return event;
	},
});
