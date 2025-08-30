import mrinimitable


# no context object is accepted
def get_context():
	context = mrinimitable._dict()
	context.body = "Custom Content"
	return context
