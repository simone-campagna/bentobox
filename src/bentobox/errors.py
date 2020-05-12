"""
Exception classes
"""


class BoxError(ValueError):
    pass


class BoxNameError(BoxError):
    pass


class BoxPathError(BoxError):
    pass


class BoxCommandError(BoxError):
    pass


class BoxPackageInfoError(BoxError):
    pass


class BoxInvalidVersionSpec(BoxPackageInfoError):
    pass


class BoxInvalidPackagePath(BoxPackageInfoError):
    pass


class BoxInvalidRequirement(BoxPackageInfoError):
    pass
