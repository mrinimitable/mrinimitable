mrinimitable.route_history_queue = [];
const routes_to_skip = ["Form", "social", "setup-wizard", "recorder"];

const save_routes = mrinimitable.utils.debounce(() => {
	if (mrinimitable.session.user === "Guest") return;
	const routes = mrinimitable.route_history_queue;
	if (!routes.length) return;

	mrinimitable.route_history_queue = [];

	mrinimitable
		.xcall("mrinimitable.desk.doctype.route_history.route_history.deferred_insert", {
			routes: routes,
		})
		.catch(() => {
			mrinimitable.route_history_queue.concat(routes);
		});
}, 10000);

mrinimitable.router.on("change", () => {
	const route = mrinimitable.get_route();
	if (is_route_useful(route)) {
		mrinimitable.route_history_queue.push({
			creation: mrinimitable.datetime.now_datetime(),
			route: mrinimitable.get_route_str(),
		});

		save_routes();
	}
});

function is_route_useful(route) {
	if (!route[1]) {
		return false;
	} else if ((route[0] === "List" && !route[2]) || routes_to_skip.includes(route[0])) {
		return false;
	} else {
		return true;
	}
}
