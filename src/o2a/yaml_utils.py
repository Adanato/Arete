import yaml  # type: ignore

# ---------- YAML dumper that preserves multiline strings & math ----------


class _LiteralDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _is_mathy(s: str) -> bool:
    return any(ch in s for ch in ("\\", "$", "{", "}", "^", "_", "~"))


def _str_representer(dumper, data: str):
    if "\n" in data or _is_mathy(data):
        if data.endswith("\n"):
            data = data.rstrip("\n")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralDumper.add_representer(str, _str_representer)
