# Contributing to DuruOn

Thank you for your interest in contributing to DuruOn! We welcome contributions from the community.

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, please include as many details as possible:

- Use a clear and descriptive title
- Describe the exact steps to reproduce the problem
- Provide specific examples and sample output
- Describe what you expected vs. what actually happened
- Include hardware and software version information

### Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/duruon-bathroom-monitoring.git`
3. Create a virtual environment: `python3 -m venv venv`
4. Activate it: `source venv/bin/activate`
5. Install dependencies: `pip install -r requirements.txt`

### Making Changes

1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes and add tests
3. Run the test suite: `python -m tests.run_all`
4. Commit with clear messages
5. Keep documentation in sync (English `README.md` and Korean `README_ko.md`)

#### Configuration Variants
The root keeps only primary configs:
- `config.yaml` (production baseline)
- `config_debug.yaml` (debug instrumentation)
- `config_mock.yaml` (mock backend / no hardware)
- `config_launcher_demo.yaml` (demo launch tweaks)

Additional example / legacy variants live under `examples/`:
- `config_practical.yaml` (conservative delays)
- `config_test_sensitive.yaml` (aggressive thresholds for quick tests)
- `examples/legacy/config_test.yaml` (legacy baseline, avoid editing)

When proposing new variants:
- Prefer adding to `examples/` instead of root.
- Provide a short comment header describing purpose & differences.
- Update `examples/README.md` and avoid duplicating parameters identical to defaults.

Removed legacy entrypoints (`main_original.py`, `main_full.py`, `main_slim.py`). Use `src/main.py` only. If you need a specialized mode, add guarded flags/config rather than duplicating files.

### Security Guidelines

- Never commit sensitive data (tokens, keys, personal information)
- Ensure on-device processing remains on-device
- Follow principle of least privilege
- Consider privacy implications of all changes

### Submitting Changes

1. Push to your fork: `git push origin feature/your-feature-name`
2. Create a Pull Request
3. Fill out the PR template completely
4. Wait for review and address feedback

Thank you for contributing to DuruOn!