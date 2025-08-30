import mrinimitable


def execute():
	"""Remove stale docfields from legacy version"""
	mrinimitable.db.delete("DocField", {"options": "Data Import", "parent": "Data Import Legacy"})
