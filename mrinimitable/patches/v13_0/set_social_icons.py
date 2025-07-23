import mrinimitable


def execute():
	providers = mrinimitable.get_all("Social Login Key")

	for provider in providers:
		doc = mrinimitable.get_doc("Social Login Key", provider)
		doc.set_icon()
		doc.save()
