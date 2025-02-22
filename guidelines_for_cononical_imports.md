# Guidelines for Canonical Imports in the app_fastapi Project

This document outlines universal rules and best practices to ensure that all imports in the project are **canonical**. Adhering to these guidelines will prevent duplicate model registrations, which can occur when modules are imported inconsistently.

## Use Absolute Imports Consistently

Always use **absolute imports** to reference modules. Instead of using relative paths like:

```python
from models.climbing import BinnedCodeDict
```

always import using the full package path:

```python
from app_fastapi.models.climbing import BinnedCodeDict
```

This approach guarantees that the module is loaded exactly once, because Python will resolve the module using a single namespace.

## Import from the Public Package API

If your package defines a public API (for example, through an `__init__.py` file), always import models or shared components from that API rather than directly from submodules. For instance, in the `app_fastapi/models` package, use:

```python
from app_fastapi.models import BinnedCodeDict, User
```

This centralizes the imports and makes sure all parts of the project reference the same canonical version of each module.

## Configure the Execution Context

Ensure that your application and tests always run from the project root with a correctly configured **PYTHONPATH**. Running the application consistently prevents misinterpretation of paths, which can lead to multiple versions of the same module (and thus duplicate registrations).

## Avoid Mixing Absolute and Relative Imports

Do not mix relative and absolute import styles for the same package. If you are using absolute imports in most modules, do not use relative imports like:

```python
from .climbing import BinnedCodeDict
```

Such practices may lead to duplicate module loading depending on how the application is executed.

## Consider Localized Imports for Circular References

In cases where circular dependencies become problematic, use localized (or deferred) imports inside functions. Import the module only when it is needed rather than at the module level. This can break circularities without compromising the integrity of the canonical import hierarchy.

For example, if a function requires a model that might create a circular dependency, do:

```python
def some_function():
    from app_fastapi.models import SomeModel
    # Use SomeModel here
```

This defers the import until the function is invoked, reducing the likelihood of circular model registrations during startup.

## Summary

By always using **absolute imports** through the project's public API, configuring the **PYTHONPATH** properly, and avoiding the mix of relative and absolute imports, you enforce a consistent, canonical import strategy across the entire app. This consistent strategy ensures that each module is loaded only once, thereby preventing duplicate model registrations and related SQLAlchemy errors.

Adhering to these guidelines will result in cleaner dependency management and a more stable database initialization process for your application.
