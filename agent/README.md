# AI Infra Monitor Agent

Local monitoring agent for AI Infrastructure Monitoring.

## Features

- Mock metrics collection (CPU, RAM, disk, network)
- CLI interface with click
- JSON output format

## Installation

```bash
pip install -e agent/
```

## Usage

Run the agent in dry-run mode:

```bash
python -m agent run --dry-run
```

View help:

```bash
python -m agent --help
python -m agent run --help
```

## Testing

Run tests:

```bash
pytest agent/tests/
```
