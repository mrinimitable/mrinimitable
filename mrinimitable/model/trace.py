"""
Traced Fields for Mrinimitable

This module provides utilities for creating traced fields in Mrinimitable documents,
which is particularly useful for enforcing strict value lifetime validation rules.

Key features:
- Create fields that can be monitored for specific value changes
- Enforce forbidden values on fields
- Apply custom validation logic to fields
- Seamlessly integrate with Mrinimitable's document model

Example of standard usage:
		from mrinimitable.model.trace import TracedDocument, traced_field

		class CustomSalesInvoice(SalesInvoice, TracedDocument):
			...
			def validate_amount(self, value):
				if value < 0:
					raise AssertionError("Amount cannot be negative")

			loyalty_program = traced_field("Loyalty Program", forbidden_values = ["FORBIDDEN_PROGRAM"])
			amount = traced_field("Amount", custom_validation = validate_amount)
			...

See mrinimitable.tests.classes.context_managers for a context manager built into test classes.
"""

import mrinimitable
from mrinimitable.model.document import Document


class TracedValue:
	"""
	A descriptor class for creating traced fields in Mrinimitable documents.

	This class allows for monitoring and validating changes to specific fields
	in a Mrinimitable document. It can enforce forbidden values and apply custom
	validation logic.

	Attributes:
	        field_name (str): The name of the field being traced.
	        forbidden_values (list): A list of values that are not allowed for this field.
	        custom_validation (callable): A function for custom validation logic.
	"""

	def __init__(self, field_name, forbidden_values=None, custom_validation=None):
		"""
		Initialize a TracedValue instance.

		Args:
		        field_name (str): The name of the field to be traced.
		        forbidden_values (list, optional): A list of values that should not be allowed.
		        custom_validation (callable, optional): A function for additional validation.
		"""
		self.field_name = field_name
		self.forbidden_values = forbidden_values or []
		self.custom_validation = custom_validation

	def __get__(self, obj, objtype=None):
		"""
		Get the value of the traced field.

		Args:
		        obj (object): The instance that this descriptor is accessed from.
		        objtype (type, optional): The type of the instance.

		Returns:
		        The value of the traced field, or self if accessed from the class.
		"""
		if obj is None:
			return self

		return getattr(obj, f"_{self.field_name}", None)

	def __set__(self, obj, value):
		"""
		Set the value of the traced field with validation.

		This method checks against forbidden values and applies custom validation
		before setting the value.

		Args:
		        obj (object): The instance that this descriptor is accessed from.
		        value: The value to set for the traced field.

		Raises:
		        ValueError: If the value is forbidden or fails custom validation.
		            Note: returns AssertionError in test mode to debug with the `--pdb` flag.

		"""
		if value in self.forbidden_values:
			if mrinimitable.in_test:
				mrinimitable.throw(f"{self.field_name} cannot be set to {value}", AssertionError)
			else:
				mrinimitable.throw(f"{self.field_name} cannot be set to {value}")

		if self.custom_validation:
			try:
				self.custom_validation(obj, value)
			except Exception as e:
				if mrinimitable.in_test:
					mrinimitable.throw(str(e), AssertionError)
				else:
					mrinimitable.throw(str(e))

		setattr(obj, f"_{self.field_name}", value)


class TracedDocument(Document):
	"""
	A base class for Mrinimitable documents with traced fields.

	This class extends Mrinimitable's Document class to provide support for
	traced fields created with TracedValue.

	Attributes:
	        Inherits all attributes from mrinimitable.model.document.Document
	"""

	def __init__(self, *args, **kwargs):
		"""
		Initialize a TracedDocument instance.

		This method sets up traced fields and initializes the parent Document.

		Args:
		        *args: Positional arguments to pass to the parent constructor.
		        **kwargs: Keyword arguments to pass to the parent constructor.
		"""
		super().__init__(*args, **kwargs)
		for name, attr in self.__class__.__dict__.items():
			if isinstance(attr, TracedValue):
				setattr(self, f"_{name}", getattr(self, name))

	def get_valid_dict(self, *args, **kwargs):
		"""
		Get a valid dictionary representation of the document.

		This method extends the parent method to properly handle traced fields.

		Args:
		        *args: Positional arguments to pass to the parent method.
		        **kwargs: Keyword arguments to pass to the parent method.

		Returns:
		        dict: A dictionary representation of the document, including traced fields.
		"""
		d = super().get_valid_dict(*args, **kwargs)
		for name, attr in self.__class__.__dict__.items():
			if isinstance(attr, TracedValue):
				d[name] = getattr(self, name)
		return d


def traced_field(*args, **kwargs):
	"""
	A convenience function for creating TracedValue instances.

	This function simplifies the creation of traced fields in Mrinimitable documents.

	Args:
	        *args: Positional arguments to pass to TracedValue constructor.
	        **kwargs: Keyword arguments to pass to TracedValue constructor.

	Returns:
	        TracedValue: An instance of the TracedValue descriptor.
	"""
	return TracedValue(*args, **kwargs)


from mrinimitable.deprecation_dumpster import model_trace_traced_field_context as traced_field_context
