"""Shared transport dependency and project credential compatibility."""
import os

from shared_actions._lib.atomgit_api import AtomGitAPI


def resolve_token(environ=None):
    """Prefer the current secret name while preserving existing installations."""
    values = os.environ if environ is None else environ
    return values.get('ATOMGIT_TOKEN') or values.get('GITCODE_TOKEN') or ''
