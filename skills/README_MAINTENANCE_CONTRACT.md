# README Maintenance Contract

Use this checklist for every SchemaGlow change.

## Trigger Conditions

Update `README.md` in the same change whenever any of these move:

- CLI commands, flags, defaults, or output formats
- compatibility rules or severity semantics
- supported file formats
- dependencies listed in `pyproject.toml`
- release, security, or contribution policies

## Mandatory README Sections

1. Feature list and positioning summary
2. Examples for `diff`, `inspect`, `snapshot`, and `compare`
3. Compatibility rule descriptions for `SAFE`, `WARNING`, and `BREAKING`
4. Architecture and tools used
5. Verification commands and standards links

## Merge Checklist

- README examples match the live CLI
- compatibility claims are covered by tests
- dependency list matches `pyproject.toml`
- architecture section still reflects current modules
- links to contribution, security, license, and citation docs still work
