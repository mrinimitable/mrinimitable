import mrinimitable


class MaxFileSizeReachedError(mrinimitable.ValidationError):
	pass


class FolderNotEmpty(mrinimitable.ValidationError):
	pass


class FileTypeNotAllowed(mrinimitable.ValidationError):
	pass


from mrinimitable.exceptions import *
