"""TokenEconomizer add-on: CodeBuddy CLI host support.

This package is loaded by the CodeBuddy launcher before the upstream package's hook/CLI entry
point. It registers CodeBuddy into the upstream runtime without editing any upstream file, so a
`git pull` of the original main branch never conflicts with this adaptation.

    from codebuddy.shim import install
    install()   # idempotent
"""
__version__ = "0.2.0"
