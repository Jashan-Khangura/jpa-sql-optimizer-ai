import yaml
from pathlib import Path


class PromptStore:
    def __init__(self, path="prompts.yaml"):
        self.path = Path(path)
        self._prompts = self._load()

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_prompt(self, key, **kwargs):
        template = self._prompts[key]
        return template.format(**kwargs)


prompt_store = PromptStore()
