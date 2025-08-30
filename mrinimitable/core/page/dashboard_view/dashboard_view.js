// Copyright (c) 2019, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.dashboards");
mrinimitable.provide("mrinimitable.dashboards.chart_sources");

mrinimitable.pages["dashboard-view"].on_page_load = function (wrapper) {
	mrinimitable.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard"),
		single_column: true,
	});

	mrinimitable.dashboard = new Dashboard(wrapper);
	$(wrapper).bind("show", function () {
		mrinimitable.dashboard.show();
	});
};

class Dashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		$(`<div class="dashboard" style="overflow: visible; margin: var(--margin-sm);">
			<div class="dashboard-graph"></div>
		</div>`).appendTo(this.wrapper.find(".page-content").empty());
		this.container = this.wrapper.find(".dashboard-graph");
		this.page = wrapper.page;
	}

	show() {
		this.route = mrinimitable.get_route();
		this.set_breadcrumbs();
		if (this.route.length > 1) {
			// from route
			this.show_dashboard(this.route.slice(-1)[0]);
		} else {
			// last opened
			if (mrinimitable.last_dashboard) {
				mrinimitable.set_re_route("dashboard-view", mrinimitable.last_dashboard);
			} else {
				// default dashboard
				mrinimitable.db.get_list("Dashboard", { filters: { is_default: 1 } }).then((data) => {
					if (data && data.length) {
						mrinimitable.set_re_route("dashboard-view", data[0].name);
					} else {
						// no default, get the latest one
						mrinimitable.db.get_list("Dashboard", { limit: 1 }).then((data) => {
							if (data && data.length) {
								mrinimitable.set_re_route("dashboard-view", data[0].name);
							} else {
								// create a new dashboard!
								mrinimitable.new_doc("Dashboard");
							}
						});
					}
				});
			}
		}
	}

	show_dashboard(current_dashboard_name) {
		if (this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__("dashboard"))) {
				// ensure dashboard title has "dashboard"
				title = __("{0} Dashboard", [__(title)]);
			}
			this.page.set_title(__(title));
			this.set_dropdown();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
		mrinimitable.last_dashboard = current_dashboard_name;
	}

	set_breadcrumbs() {
		mrinimitable.breadcrumbs.add("Desk", "Dashboard");
	}

	refresh() {
		mrinimitable.run_serially([() => this.render_cards(), () => this.render_charts()]);
	}

	render_charts() {
		return this.get_permitted_items(
			"mrinimitable.desk.doctype.dashboard.dashboard.get_permitted_charts"
		).then((charts) => {
			if (!charts.length) {
				mrinimitable.msgprint(
					__("No Permitted Charts on this Dashboard"),
					__("No Permitted Charts")
				);
			}

			mrinimitable.dashboard_utils.get_dashboard_settings().then((settings) => {
				let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
				this.charts = charts.map((chart) => {
					return {
						chart_name: chart.chart,
						label: chart.chart,
						chart_settings: chart_config[chart.chart] || {},
						...chart,
					};
				});

				this.chart_group = new mrinimitable.widget.WidgetGroup({
					title: null,
					container: this.container,
					type: "chart",
					columns: 2,
					options: {
						allow_sorting: false,
						allow_create: false,
						allow_delete: false,
						allow_hiding: false,
						allow_edit: false,
					},
					widgets: this.charts,
				});
			});
		});
	}

	render_cards() {
		return this.get_permitted_items(
			"mrinimitable.desk.doctype.dashboard.dashboard.get_permitted_cards"
		).then((cards) => {
			if (!cards.length) {
				return;
			}

			this.number_cards = cards.map((card) => {
				return {
					name: card.card,
				};
			});

			this.number_card_group = new mrinimitable.widget.WidgetGroup({
				container: this.container,
				type: "number_card",
				columns: 3,
				options: {
					allow_sorting: false,
					allow_create: false,
					allow_delete: false,
					allow_hiding: false,
					allow_edit: false,
				},
				widgets: this.number_cards,
			});
		});
	}

	get_permitted_items(method) {
		return mrinimitable
			.xcall(method, {
				dashboard_name: this.dashboard_name,
			})
			.then((items) => {
				return items;
			});
	}

	set_dropdown() {
		this.page.clear_menu();

		this.page.add_menu_item(__("Edit"), () => {
			mrinimitable.set_route("Form", "Dashboard", mrinimitable.dashboard.dashboard_name);
		});

		this.page.add_menu_item(__("New"), () => {
			mrinimitable.new_doc("Dashboard");
		});

		this.page.add_menu_item(__("Refresh All"), () => {
			this.chart_group && this.chart_group.widgets_list.forEach((chart) => chart.refresh());
			this.number_card_group &&
				this.number_card_group.widgets_list.forEach((card) => card.render_card());
		});

		mrinimitable.db.get_list("Dashboard").then((dashboards) => {
			dashboards.map((dashboard) => {
				let name = dashboard.name;
				if (name != this.dashboard_name) {
					this.page.add_menu_item(
						name,
						() => mrinimitable.set_route("dashboard-view", name),
						1
					);
				}
			});
		});
	}
}
