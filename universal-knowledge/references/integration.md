# Integration workflow

Run setup in plan mode before generation. It detects Python (pyproject.toml/requirements.txt), Node (package.json), Go (go.mod), and Rust (Cargo.toml). Detection is advisory: generated service is Python, and clients are provided in Python and TypeScript. Integrate existing identity systems through the Principal boundary, never through arbitrary tenant headers.

Default output is `<project>/knowledge`; `--output` accepts a relative directory within the target. Existing files require digest-bound confirmation. Symlink destinations and traversal are rejected. Environment secrets are never generated from project files. Setup writes a manifest in the generated directory and refuses to overwrite it on subsequent runs without approval.

Run `python scripts/setup.py --target /project --output services/knowledge --plan`, review the printed file list, then generate. The generator intentionally does not edit existing package manifests, route registries, Docker files, or authentication code. Prepare separate diffs for those integrations and confirm any replacements.

Use examples/customer-support for public/team knowledge and examples/internal-assistant for named readers. Both examples run against the reference API. Provider or authentication changes must rerun isolation, deletion, and citation tests against PostgreSQL. Outbound provider calls disclose document/query text to that provider; enable only with the project's authorization.
