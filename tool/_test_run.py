"""Headless mode test for wiki_nohighlight.yaml"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")

from src.dsl.parser import DslParser
from src.core.runner import Runner, RunnerConfig
from src.steps import create_full_registry

parser = DslParser()
scenario = parser.load("flows/wiki_nohighlight.yaml")
config = RunnerConfig(headed=False, workers=1)
registry = create_full_registry()
runner = Runner(registry)
result = asyncio.run(runner.run(scenario, config))
print(f"Status: {result.status}")
for s in result.steps:
    err = s.error or ""
    print(f"  [{s.status}] {s.step_name} ({s.step_type}) {s.duration_ms:.0f}ms {err}")

# Check screenshots
if result.artifacts_dir:
    ss_dir = result.artifacts_dir / "screenshots"
    if ss_dir.exists():
        files = list(ss_dir.iterdir())
        print(f"Screenshots: {len(files)} files in {ss_dir}")
        for f in files:
            print(f"  {f.name} ({f.stat().st_size} bytes)")
