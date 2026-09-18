from verify_post_p5_complete_tracks import main

if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main("f1c"))
