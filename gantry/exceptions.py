class GantryError(Exception):
    """
    Base exception for all error types that Gantry might raise.
    """


class GitError(GantryError):
    pass


class DirtyRepoError(GitError):
    pass


class UnpushedChangesError(GitError):
    pass


class InvalidRemoteError(GitError):
    pass


class InvalidSecretError(GantryError):
    pass


class RemoteBranchNotFoundError(GitError):
    pass


class ConfigurationError(GantryError):
    pass


class ExperimentFailedError(GantryError):
    pass


class EntrypointChecksumError(GantryError):
    pass


class GitHubTokenSecretNotFound(GantryError):
    pass


class TermInterrupt(GantryError):
    pass


class NotFoundError(GantryError):
    pass


class BeakerJobTimeoutError(GantryError, TimeoutError):
    pass


class GantryInterruptWorkload(GantryError):
    """Raised by callbacks to forcefully interrupt a workload."""
