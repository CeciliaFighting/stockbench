from pathlib import Path

import yaml


BASE = Path("/mnt/d/intern_life/efunds")
WORKTREES = [
    "stockbench-f11f-v2-reliability-haircut",
    "stockbench-f11f-v2-prompt-warning",
    "stockbench-f11k-v3-loser-cooldown",
    "stockbench-f11k-v3-prompt-warning",
    "stockbench-f11g-v2-signal-conflict",
    "stockbench-f11j-v2-crowding-loser",
    "stockbench-f11l-v2-weekly-throttle",
    "stockbench-f11e-v2-news-dryrun",
    "stockbench-f11c-v2-memory-dryrun",
    "stockbench-f11-combo-v1",
]


def main() -> None:
    for wt in WORKTREES:
        cfg_path = BASE / wt / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        assert cfg.get("stage4", {}).get("base") == "F6_FUND1_COOLDOWN_5D", wt
        mods = cfg.get("f11_modules") or {}
        enabled = [k for k, v in mods.items() if isinstance(v, dict) and v.get("enabled")]
        assert enabled, wt
        print(f"{wt}: {enabled}")


if __name__ == "__main__":
    main()
