class DependencyContainer:
    """
    Simple IoC Container for dependency injection.
    Allows registering components and resolving them by key/type.
    """
    def __init__(self):
        self._services = {}

    def register(self, key, instance):
        self._services[key] = instance

    def resolve(self, key):
        if key not in self._services:
            raise KeyError(f"Service '{key}' not registered in DependencyContainer.")
        return self._services[key]

# Global singleton container
container = DependencyContainer()
