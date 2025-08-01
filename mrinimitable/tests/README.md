# Mrinimitable Test Framework

This README provides an overview of the test case framework available in Mrinimitable. These utilities are designed to facilitate efficient and effective testing of Mrinimitable applications.

This is different from the `mrinimitable.testing` module which houses the discovery and runner infrastructure for CLI and CI.

## Directory Structure

The test framework is organized into the following structure:

```
mrinimitable/tests/
├── classes/
│   ├── context_managers.py
│   ├── unit_test_case.py
│   └── ...
├── utils/
│   ├── generators.py
│   └── ...
├── test_api.py
├── test_child_table.py
└── ...
```

## Key Components

1. Test case classes (UnitTestCase and IntegrationTestCase)
3. Framework and class specific context managers
4. Utility functions and generators
5. Specific test modules for various Mrinimitable components

### Test Case Classes

#### UnitTestCase ([`classes/unit_test_case.py`](./classes/unit_test_case.py))

###### Import convention: `from mrinimitable.tests import UnitTestCase`

This class extends `unittest.TestCase` and provides additional utilities specific to the Mrinimitable framework. It's designed for testing individual components or functions in isolation.

Key features include:
- Custom assertions for Mrinimitable-specific comparisons
- Utilities for HTML and SQL normalization
- Context managers for user switching and time freezing

#### IntegrationTestCase ([`classes/integration_test_case.py`](./classes/integration_test_case.py))

###### Import convention: `from mrinimitable.tests import IntegrationTestCase`

This class extends `UnitTestCase` and is designed for integration testing. It provides features for:
- Automatic site and connection setup
- Automatic test records loading
- Automatic reset of thread locals
- Context managers that depend on a site connection
- Asserts that depend on a site connection

For a detailed list of context managers, please refer to the code.

### Utility Functions and Generators ([`utils/generators.py`](./utils/generators.py))

This module contains utility functions for generating test records and managing test data.

### Specific Test Modules

Various test modules (e.g., test_api.py, test_document.py) contain tests for specific Mrinimitable core components and functionalities.

Note that Document tests are collocated alongside each Document module.

## Usage

To use these test utilities in your Mrinimitable application tests, you can inherit from the appropriate test case class:

```python
from mrinimitable.tests import UnitTestCase

class MyTestCase(UnitTestCase):
    def test_something(self):
        # Your test code here
        pass
```

## Contributing

When adding new test utilities or modifying existing ones:
1. Place them in the appropriate directory based on their function.
2. Update this README to reflect any significant changes in the framework structure or usage.
3. Ensure that your changes follow the existing coding style and conventions.

Remember to always refer to the actual code for the most up-to-date and detailed information on available methods and their usage.
