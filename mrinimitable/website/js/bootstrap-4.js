import "bootstrap/dist/js/bootstrap.bundle";

// multilevel dropdown
$(".dropdown-menu a.dropdown-toggle").on("click", function (e) {
	e.preventDefault();
	e.stopImmediatePropagation();
	if (!$(this).next().hasClass("show")) {
		$(this).parents(".dropdown-menu").first().find(".show").removeClass("show");
	}
	var $subMenu = $(this).next(".dropdown-menu");
	$subMenu.toggleClass("show");

	$(this)
		.parents("li.nav-item.dropdown.show")
		.on("hidden.bs.dropdown", function () {
			$(".dropdown-submenu .show").removeClass("show");
		});

	return false;
});

mrinimitable.get_modal = function (title, content) {
	return $(
		`<div class="modal" tabindex="-1" role="dialog">
			<div class="modal-dialog" role="document">
				<div class="modal-content">
					<div class="modal-header">
						<h5 class="modal-title">${title}</h5>
						<button type="button" class="close" data-dismiss="modal" aria-label="Close">
						${mrinimitable.utils.icon("close-alt", "sm", "close-alt")}
						</button>
					</div>
					<div class="modal-body">
						${content}
					</div>
					<div class="modal-footer hidden">
						<button type="button" class="btn btn-default btn-sm btn-modal-close" data-dismiss="modal">
							<i class="octicon octicon-x visible-xs" style="padding: 1px 0px;"></i>
							<span class="hidden-xs">${__("Close")}</span>
						</button>
						<button type="button" class="btn btn-sm btn-primary hidden"></button>
					</div>
				</div>
			</div>
		</div>`
	);
};

mrinimitable.ui.Dialog = class Dialog extends mrinimitable.ui.Dialog {
	get_primary_btn() {
		return this.$wrapper.find(".modal-footer .btn-primary");
	}

	set_primary_action(label, click) {
		this.$wrapper.find(".modal-footer").removeClass("hidden");
		return super.set_primary_action(label, click).removeClass("hidden");
	}

	make() {
		super.make();
		if (this.fields) {
			this.$wrapper.find(".section-body").addClass("w-100");
		}
	}
};
