"""
Buildrix CLI.

One shape for everything: `buildrix <noun> <verb>`. The verbs mean the same
thing for a skill and for a task, so there is nothing extra to remember.

    buildrix skill  new | check | submit | status | install | list | remove
                    pull | update | dev | search | browse | delete
    buildrix task   new | check | submit | status | get | list
    buildrix bench  run | submit | status | list
    buildrix auth   login | logout | whoami | register
    buildrix domains [--task]
    buildrix info
    buildrix env    info | setup | clean
    buildrix config hub <url>

  new       scaffold the folder layout                              (local)
  check     run every mechanical gate - the same code the hub runs  (local)
  submit    upload, then print the checks and the review            (server)
  status    the current verdict, round, and what is still missing   (server)

Examples

    buildrix skill new chiller-plant-mpc
    buildrix skill check ./chiller-plant-mpc
    buildrix skill submit ./chiller-plant-mpc
    buildrix skill status chiller-plant-mpc

    buildrix task new ahu-fdd-fortnight
    buildrix task check ./ahu-fdd-fortnight
    buildrix task submit ./ahu-fdd-fortnight

The older flat commands (login, install, push, browse, ...) still work and print
a one-line note pointing at the new form.
"""

import argparse
import getpass
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="buildrix",
        description="Buildrix - open skill framework and benchmark for building science AI agents",
    )
    sub = parser.add_subparsers(dest="noun", metavar="<command>")

    # == skill ==============================================================
    p_skill = sub.add_parser("skill", help="Work with skills")
    sk = p_skill.add_subparsers(dest="verb")

    q = sk.add_parser("new", help="Scaffold a new skill")
    q.add_argument("name")
    q.add_argument("--dir", default=".", help="Parent directory")

    q = sk.add_parser("check", help="Run every skill/2.0 gate locally")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--no-tests", action="store_true", help="Skip running tests/")
    q.add_argument("--determinism", action="store_true",
                   help="Run the tests twice and compare the output")

    q = sk.add_parser("submit", help="Upload a skill and print the review")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--force", action="store_true",
                   help="Upload even if the local checks found blockers")
    q.add_argument("--no-tests", action="store_true", help="Skip running tests/")

    q = sk.add_parser("status", help="Show the current review for a skill")
    q.add_argument("name")

    q = sk.add_parser("install", help="Install skill(s) from the hub")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="install_all")
    q.add_argument("--mine", action="store_true")
    q.add_argument("--domain", default="")

    q = sk.add_parser("pull", help="Download skill archive(s) without installing")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="pull_all")
    q.add_argument("--mine", action="store_true")
    q.add_argument("--domain", default="")
    q.add_argument("--dir", default=".")
    q.add_argument("--extract", action="store_true")

    q = sk.add_parser("update", help="Update installed skill(s) from the hub")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="update_all")

    q = sk.add_parser("dev", help="Link a local skill for development")
    q.add_argument("path")

    q = sk.add_parser("remove", help="Remove installed skill(s)")
    q.add_argument("names", nargs="+")

    sk.add_parser("list", help="List installed skills")

    q = sk.add_parser("search", help="Search the hub for skills")
    q.add_argument("query")
    q.add_argument("--domain", default="")

    q = sk.add_parser("browse", help="List skills on the hub")
    q.add_argument("--domain", default="")
    q.add_argument("--sort", default="newest",
                   choices=["newest", "oldest", "most_liked", "most_downloaded", "most_saved"])

    q = sk.add_parser("delete", help="Delete your skill(s) from the hub")
    q.add_argument("names", nargs="+")
    q.add_argument("--yes", "-y", action="store_true")

    # == task ===============================================================
    p_task = sub.add_parser("task", help="Work with benchmark tasks")
    tk = p_task.add_subparsers(dest="verb")

    q = tk.add_parser("new", help="Scaffold a new task")
    q.add_argument("name")
    q.add_argument("--dir", default=".", help="Parent directory")

    q = tk.add_parser("check", help="Run every task/2.0 gate locally")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--no-grader", action="store_true",
                   help="Skip running your grader against the reference")

    q = tk.add_parser("submit", help="Upload a task and print the review")
    q.add_argument("path", nargs="?", default=".")
    q.add_argument("--force", action="store_true",
                   help="Upload even if the local gates found blockers")

    q = tk.add_parser("status", help="Show the current review for a task")
    q.add_argument("slug")

    q = tk.add_parser("get", help="Download a task's public half")
    q.add_argument("slug")
    q.add_argument("--dir", default=".")

    q = tk.add_parser("list", help="List tasks on the hub")
    q.add_argument("--domain", default="")
    q.add_argument("--search", default="")

    # == bench ==============================================================
    p_bench = sub.add_parser("bench", help="Run the paired benchmark")
    bn = p_bench.add_subparsers(dest="verb")

    q = bn.add_parser("run", help="Run both arms of a suite on this machine")
    q.add_argument("--suite", default="core-v1")
    q.add_argument("--model", default="")
    q.add_argument("--harness", default="claude-code")
    q.add_argument("--skills", default="", help="Comma-separated skill names for arm B")
    q.add_argument("--trials", type=int, default=3)
    q.add_argument("--task", default="", help="Restrict to one task id")

    q = bn.add_parser("submit", help="Upload a finished run for grading")
    q.add_argument("path", nargs="?", default=".")

    q = bn.add_parser("status", help="Show the grading status of a run")
    q.add_argument("run_id")

    bn.add_parser("list", help="List your submitted runs")

    # == auth, domains, info, env, config ===================================
    p_auth = sub.add_parser("auth", help="Account and credentials")
    au = p_auth.add_subparsers(dest="verb")
    q = au.add_parser("login", help="Authenticate with the hub")
    q.add_argument("--hub", default="")
    q.add_argument("--register", action="store_true")
    au.add_parser("logout", help="Clear stored credentials")
    au.add_parser("whoami", help="Show the current user")
    q = au.add_parser("register", help="Create an account")
    q.add_argument("--hub", default="")

    q = sub.add_parser("domains", help="List the valid domains")
    q.add_argument("--task", action="store_true", dest="task_only",
                   help="Show only the domains a task may use")

    sub.add_parser("info", help="Hub stats and connection info")

    p_env = sub.add_parser("env", help="Manage the toolchain environment")
    ev = p_env.add_subparsers(dest="env_command")
    ev.add_parser("info", help="Show installed toolchain components")
    q = ev.add_parser("setup", help="Provision the toolchain for a skill")
    q.add_argument("path")
    ev.add_parser("clean", help="Remove cached downloads")

    q = sub.add_parser("config", help="Configure buildrix")
    q.add_argument("key", choices=["hub"])
    q.add_argument("value")

    # == legacy flat commands ===============================================
    _add_legacy(sub)

    args = parser.parse_args()
    if not args.noun:
        parser.print_help()
        return

    nouns = {
        "skill": (p_skill, SKILL_VERBS),
        "task": (p_task, TASK_VERBS),
        "bench": (p_bench, BENCH_VERBS),
        "auth": (p_auth, AUTH_VERBS),
    }

    try:
        if args.noun in nouns:
            group, table = nouns[args.noun]
            verb = getattr(args, "verb", None)
            if not verb:
                group.print_help()
                return
            sys.exit(table[verb](args) or 0)

        if args.noun in TOP_LEVEL:
            sys.exit(TOP_LEVEL[args.noun](args) or 0)

        if args.noun in LEGACY:
            new_form, handler = LEGACY[args.noun]
            print(f"note: `buildrix {args.noun}` is now `{new_form}`.")
            sys.exit(handler(args) or 0)

        parser.print_help()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as e:
        print(f"error: {e}")
        sys.exit(1)


def _add_legacy(sub):
    """The pre-2.0 flat commands, kept working."""
    q = sub.add_parser("login")
    q.add_argument("--hub", default="")
    q.add_argument("--register", action="store_true")
    sub.add_parser("logout")
    sub.add_parser("whoami")
    q = sub.add_parser("register")
    q.add_argument("--hub", default="")

    q = sub.add_parser("new")
    q.add_argument("type", choices=["skill", "task", "testcase"])
    q.add_argument("name")
    q.add_argument("--dir", default=".")

    q = sub.add_parser("install")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="install_all")
    q.add_argument("--mine", action="store_true")
    q.add_argument("--domain", default="")

    q = sub.add_parser("pull")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="pull_all")
    q.add_argument("--mine", action="store_true")
    q.add_argument("--domain", default="")
    q.add_argument("--dir", default=".")
    q.add_argument("--extract", action="store_true")

    q = sub.add_parser("update")
    q.add_argument("names", nargs="*")
    q.add_argument("--all", action="store_true", dest="update_all")

    q = sub.add_parser("dev")
    q.add_argument("path")

    q = sub.add_parser("uninstall")
    q.add_argument("names", nargs="+")

    sub.add_parser("list")

    q = sub.add_parser("push")
    q.add_argument("paths", nargs="+")
    q.add_argument("--update", action="store_true")
    q.add_argument("--all", action="store_true", dest="push_all")

    q = sub.add_parser("delete")
    q.add_argument("names", nargs="+")
    q.add_argument("--yes", "-y", action="store_true")

    q = sub.add_parser("search")
    q.add_argument("query")
    q.add_argument("--domain", default="")

    q = sub.add_parser("browse")
    q.add_argument("--domain", default="")
    q.add_argument("--sort", default="newest",
                   choices=["newest", "oldest", "most_liked", "most_downloaded", "most_saved"])


# ==========================================================================

def cmd_register(args):
    from buildrix.config import set_auth, set_hub_url
    from buildrix.hub_client import HubClient

    if args.hub:
        set_hub_url(args.hub)

    client = HubClient(hub_url=args.hub)
    print("  Buildrix - Create Account")
    print()
    email = input("  Email: ").strip()
    display_name = input("  Display name: ").strip()
    affiliation = input("  Affiliation (university/company): ").strip()
    password = getpass.getpass("  Password: ")
    password2 = getpass.getpass("  Confirm password: ")
    if password != password2:
        print("error: Passwords don't match")
        return

    data = client.register(email, password, display_name, affiliation)
    set_auth(
        token=data["access_token"],
        user={"id": data["user_id"], "name": data["display_name"], "email": email},
        hub_url=args.hub,
    )
    print(f"\nok Welcome to Buildrix, {data['display_name']}!")
    print(f"  You're now logged in and ready to push skills.")

def cmd_login(args):
    from buildrix.config import set_auth, set_hub_url
    from buildrix.hub_client import HubClient

    if args.hub:
        set_hub_url(args.hub)

    client = HubClient(hub_url=args.hub)
    print("  Buildrix Hub Login")
    print()

    email = input("  Email: ").strip()

    if args.register:
        display_name = input("  Display name: ").strip()
        affiliation = input("  Affiliation (university/company): ").strip()
        password = getpass.getpass("  Password: ")
        password2 = getpass.getpass("  Confirm password: ")
        if password != password2:
            print("error: Passwords don't match")
            return
        data = client.register(email, password, display_name, affiliation)
        print(f"\nok Account created! Welcome, {data['display_name']}")
    else:
        password = getpass.getpass("  Password: ")
        data = client.login(email, password)
        print(f"\nok Logged in as {data['display_name']}")

    set_auth(
        token=data["access_token"],
        user={"id": data["user_id"], "name": data["display_name"], "email": email},
        hub_url=args.hub,
    )


def cmd_logout(args):
    from buildrix.config import clear_auth
    clear_auth()
    print("ok Logged out")


def cmd_whoami(args):
    from buildrix.config import get_user, get_hub_url
    user = get_user()
    if not user:
        print("Not logged in. Run: buildrix login")
        return
    print(f"  User:  {user.get('name', 'unknown')}")
    print(f"  Email: {user.get('email', 'unknown')}")
    print(f"  Hub:   {get_hub_url()}")


def cmd_config(args):
    if args.key == "hub":
        from buildrix.config import set_hub_url
        set_hub_url(args.value)
        print(f"ok Hub URL set to {args.value}")


def cmd_new(args):
    from buildrix.scaffold import scaffold_skill, scaffold_testcase
    if args.type == "skill":
        scaffold_skill(args.name, args.dir)
    elif args.type == "testcase":
        scaffold_testcase(args.name, args.dir)


def cmd_install(args):
    from buildrix.skill_manager import install_skill

    # Resolve which skill names to install.
    if args.install_all or args.mine:
        from buildrix.config import get_user
        from buildrix.hub_client import HubClient

        if args.names:
            print("!  Ignoring explicit names because --all/--mine was given.")

        client = HubClient()
        skills = client.list_skills(domain=args.domain, sort_by="newest")

        if args.mine:
            user = get_user()
            if not user:
                print("error: Not logged in. Run: buildrix login")
                return
            my_name = user.get("name", "")
            skills = [s for s in skills if s.get("author_name") == my_name]

        if not skills:
            scope = "you authored" if args.mine else "on the hub"
            extra = f" in domain '{args.domain}'" if args.domain else ""
            print(f"  No skills {scope}{extra}.")
            return

        names = [s["name"] for s in skills]
        print(f"  Installing {len(names)} skill(s)...\n")
    else:
        if not args.names:
            print("error: Nothing to install. Pass skill name(s), or use --all / --mine.")
            return
        names = args.names

    ok, fail = [], []
    for name in names:
        try:
            install_skill(name)
            ok.append(name)
            print(f"ok '{name}' installed")
        except Exception as e:
            fail.append(name)
            print(f"error: '{name}' failed: {e}")

    if len(names) > 1:
        print(f"\n  Summary: {len(ok)} installed, {len(fail)} failed")


def cmd_pull(args):
    """
    Download skill archive(s) from the hub to disk WITHOUT installing them.

    Use this when you want to inspect or vendor a skill rather than make it
    visible to Claude Code. For the "install + link to ~/.claude/skills"
    behavior, use `buildrix install` instead.

    Targets can be given three ways:
      - explicit names:  buildrix pull skill-a skill-b
      - everything:      buildrix pull --all
      - your own skills: buildrix pull --mine
    """
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    client = HubClient()
    dest_root = Path(args.dir).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    # -- Resolve the list of skills to download --
    if args.pull_all or args.mine:
        if args.names:
            print("!  Ignoring explicit names because --all/--mine was given.")

        # Pull a generous page so we get everything, not just the default 50.
        skills = client.list_skills(domain=args.domain, sort_by="newest")

        if args.mine:
            user = get_user()
            if not user:
                print("error: Not logged in. Run: buildrix login")
                return
            my_name = user.get("name", "")
            skills = [s for s in skills if s.get("author_name") == my_name]

        if not skills:
            scope = "you authored" if args.mine else "on the hub"
            extra = f" in domain '{args.domain}'" if args.domain else ""
            print(f"  No skills {scope}{extra}.")
            return

        targets = [(s["name"], s["id"]) for s in skills]
        print(f"  Downloading {len(targets)} skill(s) -> {dest_root}\n")
    else:
        if not args.names:
            print("error: Nothing to pull. Pass skill name(s), or use --all / --mine.")
            return
        # Resolve names -> ids up front so errors are clear.
        targets = []
        for name in args.names:
            skill = client.get_skill_by_name(name)
            if not skill:
                print(f"error: '{name}' not found on the hub.")
                continue
            targets.append((skill["name"], skill["id"]))
        if not targets:
            return

    # -- Download loop (shared by all modes) --
    ok, fail = 0, 0
    for name, skill_id in targets:
        try:
            if args.extract:
                target = dest_root / name
                client.download_skill(skill_id, target)
                print(f"ok '{name}' downloaded and extracted -> {target}")
            else:
                target = dest_root / f"{name}.zip"
                client.download_skill_archive(skill_id, target)
                print(f"ok '{name}' downloaded -> {target}")
            ok += 1
        except Exception as e:
            print(f"error: '{name}' failed: {e}")
            fail += 1

    if len(targets) > 1:
        print(f"\n  Summary: {ok} pulled, {fail} failed")


def cmd_update(args):
    """
    Re-fetch installed skill(s) at the latest hub version and relink to
    Claude Code. With --all (or no names), updates every installed skill.
    """
    from buildrix.skill_manager import installed_skills, install_skill

    installed = installed_skills()
    if not installed:
        print("No skills installed. Try: buildrix install <name>")
        return

    if args.update_all or not args.names:
        names = [s["name"] for s in installed]
        print(f"  Updating {len(names)} installed skill(s)...\n")
    else:
        installed_names = {s["name"] for s in installed}
        names = []
        for n in args.names:
            if n not in installed_names:
                print(f"!  '{n}' is not installed locally - skipping. "
                      f"(Use `buildrix install {n}` to install it for the first time.)")
                continue
            names.append(n)
        if not names:
            return

    ok, fail = 0, 0
    for name in names:
        try:
            # install_skill removes any existing copy before installing,
            # so it doubles as the update path.
            install_skill(name)
            print(f"ok '{name}' updated to latest version")
            ok += 1
        except Exception as e:
            print(f"error: '{name}' failed: {e}")
            fail += 1

    if len(names) > 1:
        print(f"\n  Summary: {ok} updated, {fail} failed")


def cmd_dev(args):
    from buildrix.skill_manager import install_local
    install_local(Path(args.path))
    print(f"\nok Dev skill installed and linked to Claude Code")


def cmd_uninstall(args):
    from buildrix.skill_manager import uninstall_skill

    for name in args.names:
        try:
            uninstall_skill(name)
            print(f"ok '{name}' removed")
        except Exception as e:
            print(f"error: '{name}' failed: {e}")


def cmd_list(args):
    from buildrix.skill_manager import installed_skills
    skills = installed_skills()
    if not skills:
        print("No skills installed. Try: buildrix install weather-data-extraction")
        return
    print(f"\n  Installed skills ({len(skills)}):\n")
    for s in skills:
        desc = s.get("description", "")[:60]
        ver = s.get("version", "")
        domain = s.get("domain", "")
        print(f"  - {s['name']}", end="")
        if ver:
            print(f" (v{ver})", end="")
        if domain:
            print(f" [{domain}]", end="")
        print()
        if desc:
            print(f"    {desc}")
    print()


def _discover_skill_dirs(paths: list[str], push_all: bool) -> list[Path]:
    """Resolve paths into a flat list of pushable skill/testcase directories."""
    dirs = []
    for p in paths:
        path = Path(p)
        if not path.is_dir():
            print(f"!  Skipping (not a directory): {path}")
            continue

        if push_all:
            # Auto-discover: find all sub-dirs containing SKILL.md or TESTCASE.yaml
            found = sorted(
                sub for sub in path.iterdir()
                if sub.is_dir()
                and ((sub / "SKILL.md").exists() or (sub / "TESTCASE.yaml").exists())
            )
            if not found:
                print(f"!  No skills or test cases found under {path}/")
            dirs.extend(found)
        elif (path / "SKILL.md").exists() or (path / "TESTCASE.yaml").exists():
            dirs.append(path)
        else:
            # Maybe the user meant --all? Check if children look like skills.
            children = [
                sub for sub in path.iterdir()
                if sub.is_dir()
                and ((sub / "SKILL.md").exists() or (sub / "TESTCASE.yaml").exists())
            ]
            if children:
                print(f"!  '{path}' has no SKILL.md itself, but contains {len(children)} skill(s).")
                print(f"  Did you mean:  buildrix push {path} --all")
            else:
                print(f"error: No SKILL.md or TESTCASE.yaml found in {path}")
    return dirs


def _push_one(path: Path, client, user: dict, update: bool) -> bool:
    """Push a single skill or test case. Returns True on success."""
    from buildrix.hub_client import _parse_frontmatter

    if (path / "SKILL.md").exists():
        meta = _parse_frontmatter((path / "SKILL.md").read_text())
        skill_name = meta.get("name", path.name)

        # Warn about invalid domain
        from buildrix.config import VALID_DOMAINS
        skill_domain = meta.get("metadata", {}).get("domain", "general")
        if skill_domain not in VALID_DOMAINS:
            print(f"  !  Domain '{skill_domain}' is not a recognized hub category.")
            print(f"    Valid: {', '.join(VALID_DOMAINS)}")

        existing = client.get_skill_by_name(skill_name)

        if existing and update:
            if existing["author_id"] != user.get("id", ""):
                print(f"  error: '{skill_name}' belongs to another contributor.")
                return False
            result = client.update_skill(existing["id"], path)
            print(f"  ok '{result['name']}' updated (v{result['version']}, {result['status']})")
            return True

        elif existing and not update:
            if existing["author_id"] == user.get("id", ""):
                print(f"  !  '{skill_name}' already exists. Use --update to overwrite.")
            else:
                print(f"  error: '{skill_name}' already exists (owned by someone else).")
            return False

        else:
            result = client.push_skill(path)
            print(f"  ok '{result['name']}' submitted ({result['status']})")
            return True

    elif (path / "TESTCASE.yaml").exists():
        result = client.push_testcase(path)
        print(f"  ok Test case '{result['name']}' submitted ({result['status']})")
        return True

    else:
        print(f"  error: No SKILL.md or TESTCASE.yaml in {path}")
        return False


def cmd_push(args):
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    if not get_token():
        print("error: Not logged in. Run: buildrix login")
        return

    dirs = _discover_skill_dirs(args.paths, args.push_all)
    if not dirs:
        return

    client = HubClient()
    user = get_user()

    if len(dirs) > 1:
        print(f"\n  Pushing {len(dirs)} item(s)...\n")

    ok, fail = 0, 0
    for d in dirs:
        print(f"  [{d.name}]")
        try:
            if _push_one(d, client, user, args.update):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  error: {d.name}: {e}")
            fail += 1

    if len(dirs) > 1:
        print(f"\n  Summary: {ok} pushed, {fail} failed")



def cmd_delete(args):
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    if not get_token():
        print("error: Not logged in. Run: buildrix login")
        return

    client = HubClient()
    user = get_user()

    # Resolve all skills first so we can show a summary before confirming
    to_delete = []
    for name in args.names:
        skill = client.get_skill_by_name(name)
        if not skill:
            print(f"error: '{name}' not found on the hub.")
            continue
        if skill["author_id"] != user.get("id", ""):
            print(f"error: '{name}' belongs to another contributor. Skipping.")
            continue
        to_delete.append(skill)

    if not to_delete:
        return

    # Show what will be deleted
    print()
    for s in to_delete:
        print(f"  - {s['name']} (v{s['version']}, {s['download_count']} downloads)")
    print()

    # Confirm unless --yes flag
    if not args.yes:
        noun = "skill" if len(to_delete) == 1 else f"{len(to_delete)} skills"
        confirm = input(f"  !  Permanently delete {noun} and all likes/comments? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Cancelled.")
            return

    ok = 0
    for s in to_delete:
        try:
            client.delete_skill(s["id"])
            print(f"  ok '{s['name']}' deleted")
            ok += 1
        except Exception as e:
            print(f"  error: '{s['name']}' failed: {e}")

    if len(to_delete) > 1:
        print(f"\n  Summary: {ok}/{len(to_delete)} deleted")


def cmd_search(args):
    from buildrix.hub_client import HubClient
    client = HubClient()
    skills = client.list_skills(domain=args.domain, search=args.query)

    if not skills:
        print(f"  No skills found for '{args.query}'")
        return

    print(f"\n  Found {len(skills)} skill(s):\n")
    for s in skills:
        print(f"  - {s['name']} [{s['domain']}] - {s['status']}")
        print(f"    {s['description'][:80]}")
        print(f"    by {s['author_name']} | v{s['version']} | {s['download_count']} downloads")
        print()


def cmd_browse(args):
    from buildrix.hub_client import HubClient
    client = HubClient()
    skills = client.list_skills(
        domain=args.domain,
        sort_by=args.sort,
    )

    if not skills:
        domain_hint = f" in domain '{args.domain}'" if args.domain else ""
        print(f"  No skills found{domain_hint}.")
        return

    print(f"\n  Hub skills ({len(skills)}):\n")
    for s in skills:
        status_icon = "ok" if s["status"] == "accepted" else ""
        print(f"  {status_icon} {s['name']} [{s['domain']}]")
        print(f"    {s['description'][:80]}")
        print(f"    by {s['author_name']} | v{s['version']} | likes {s.get('like_count', 0)} | dl {s['download_count']}")
        print()


def cmd_domains(args):
    from buildrix.config import VALID_DOMAINS
    print("\n  Valid domain categories:\n")
    for d in VALID_DOMAINS:
        print(f"  - {d}")
    print()
    print("  Use these in your SKILL.md frontmatter and config.yaml.")
    print("  Example: domain: energy-modeling")
    print()


def cmd_info(args):
    from buildrix.config import get_hub_url, get_user, SKILLS_DIR
    from buildrix.skill_manager import installed_skills

    hub_url = get_hub_url()
    user = get_user()

    print()
    print("    Buildrix Info")
    print(f"  -------------------------")
    print(f"  Hub:       {hub_url}")
    print(f"  User:      {user['name'] if user else 'not logged in'}")
    print(f"  Skills:    {SKILLS_DIR}")
    print(f"  Installed: {len(installed_skills())} skills")

    try:
        from buildrix.hub_client import HubClient
        stats = HubClient().stats()
        print()
        print(f"  Hub Stats:")
        print(f"    Skills:       {stats.get('skills', 0)}")
        print(f"    Test Cases:   {stats.get('testcases', 0)}")
        print(f"    Challenges:   {stats.get('challenges', 0)}")
        print(f"    Contributors: {stats.get('contributors', 0)}")
    except Exception:
        print(f"\n  !  Could not reach hub at {hub_url}")
    print()


def cmd_env(args):
    if not args.env_command:
        print("Usage: buildrix env {info|setup|clean}")
        return

    if args.env_command == "info":
        from buildrix.env.toolchain import Toolchain, TOOLCHAIN_DIR, DOWNLOAD_CACHE
        tc = Toolchain()
        info = tc.info()
        print()
        print("   Buildrix Toolchain")
        print(f"  -------------------------")
        print(f"  Location:    {TOOLCHAIN_DIR}")
        print(f"  Cache:       {DOWNLOAD_CACHE}")
        print(f"  Weather:     {info.weather_dir}")
        print()
        if info.versions:
            print("  Installed:")
            for tool, ver in info.versions.items():
                print(f"    - {tool} {ver}")
            if info.energyplus_bin:
                print(f"      EnergyPlus binary: {info.energyplus_bin}")
            if info.openstudio_bin:
                print(f"      OpenStudio binary: {info.openstudio_bin}")
            if info.idd_path:
                print(f"      Energy+.idd:       {info.idd_path}")
            if info.resstock_dir:
                print(f"      ResStock repo:     {info.resstock_dir}")
        else:
            print("  No tools installed yet.")
            print("  Install a skill that needs tools: buildrix install resstock-building-generation")
        print()

    elif args.env_command == "setup":
        from buildrix.skill_manager import provision_toolchain
        from buildrix.config import SKILLS_DIR

        path = Path(args.path)
        # If it's just a name, look in installed skills
        if not path.exists():
            path = SKILLS_DIR / args.path
        if not path.exists():
            print(f"error: Skill not found: {args.path}")
            print(f"   Checked: {Path(args.path).resolve()} and {SKILLS_DIR / args.path}")
            return

        provisioned = provision_toolchain(path)
        if not provisioned:
            print("  No toolchain requirements in this skill's config.yaml.")

    elif args.env_command == "clean":
        from buildrix.env.toolchain import DOWNLOAD_CACHE
        if DOWNLOAD_CACHE.exists():
            import shutil
            size = sum(f.stat().st_size for f in DOWNLOAD_CACHE.rglob("*") if f.is_file())
            shutil.rmtree(DOWNLOAD_CACHE)
            DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
            print(f"  ok Cleared download cache ({size / 1024 / 1024:.0f} MB freed)")
        else:
            print("  Cache is already empty.")


# ==========================================================================
#  check | submit | status - the four verbs that matter
# ==========================================================================

def _print(rep) -> int:
    from buildrix.report import render, supports_color
    print(render(rep, color=supports_color()))
    return rep.exit_code


def cmd_skill_check(args) -> int:
    from buildrix.checks import check_skill
    rep = check_skill(args.path, run_tests=not args.no_tests,
                      check_determinism=args.determinism)
    code = _print(rep)
    if code == 0:
        print(f"  ready:  buildrix skill submit {args.path}\n")
    return code


def cmd_skill_submit(args) -> int:
    from buildrix.checks import check_skill
    from buildrix.hub_client import HubClient
    from buildrix.config import get_token
    from buildrix.report import Report

    rep = check_skill(args.path, run_tests=not args.no_tests)
    if rep.blockers and not args.force:
        _print(rep)
        print("  not uploaded. Fix the blockers, or pass --force.\n")
        return 1

    if not get_token():
        print("Not logged in. Run `buildrix auth login` first.")
        return 1

    print(f"  uploading {Path(args.path).resolve().name} ...")
    payload = HubClient().submit_skill(Path(args.path))
    review = Report.from_hub(payload, title=f"skill review | {Path(args.path).name}")
    for f in rep.findings:               # keep the local results in the report
        review.findings.insert(0, f)
    code = _print(review)
    name = payload.get("name") or Path(args.path).name
    print(f"  full report:  buildrix skill status {name}\n")
    return code


def cmd_skill_status(args) -> int:
    from buildrix.hub_client import HubClient
    from buildrix.report import Report
    try:
        payload = HubClient().skill_review(args.name)
    except Exception as e:
        return _not_found("skill", args.name, e)
    return _print(Report.from_hub(payload, title=f"skill review | {args.name}"))


def cmd_task_check(args) -> int:
    from buildrix.checks import check_task
    rep = check_task(args.path, run_grader=not args.no_grader)
    code = _print(rep)
    if code == 0:
        print(f"  ready:  buildrix task submit {args.path}\n")
    return code


def cmd_task_submit(args) -> int:
    from buildrix.checks import check_task
    from buildrix.hub_client import HubClient
    from buildrix.config import get_token
    from buildrix.report import Report

    rep = check_task(args.path)
    if rep.blockers and not args.force:
        _print(rep)
        print("  not uploaded. Fix the blockers, or pass --force.\n")
        return 1

    if not get_token():
        print("Not logged in. Run `buildrix auth login` first.")
        return 1

    print(f"  uploading {Path(args.path).resolve().name} ...")
    payload = HubClient().submit_task(Path(args.path))
    review = Report.from_hub(payload, title=f"task review | {Path(args.path).name}")
    for f in rep.findings:
        review.findings.insert(0, f)
    if rep.missing and not review.missing:
        review.missing = rep.missing
    code = _print(review)
    slug = payload.get("slug") or Path(args.path).name
    print(f"  full report:  buildrix task status {slug}\n")
    return code


def cmd_task_status(args) -> int:
    from buildrix.hub_client import HubClient
    from buildrix.report import Report
    try:
        payload = HubClient().task_review(args.slug)
    except Exception as e:
        return _not_found("task", args.slug, e)
    return _print(Report.from_hub(payload, title=f"task review | {args.slug}"))


def _not_found(kind: str, name: str, err: Exception) -> int:
    from buildrix.config import get_hub_url, get_token
    if "404" in str(err):
        print()
        print(f"  No {kind} called '{name}' on {get_hub_url()}.")
        if not get_token():
            print("  You are not logged in, so drafts of your own are not visible.")
            print("  Try: buildrix auth login")
        print()
        return 1
    print(f"error: {err}")
    return 1


# ==========================================================================
#  scaffolding, listing, and the rest
# ==========================================================================

def cmd_skill_new(args) -> int:
    from buildrix.scaffold import scaffold_skill
    scaffold_skill(args.name, args.dir)
    return 0


def cmd_task_new(args) -> int:
    from buildrix.scaffold import scaffold_task
    scaffold_task(args.name, args.dir)
    return 0


def cmd_new_legacy(args) -> int:
    args.name = args.name
    if args.type == "skill":
        return cmd_skill_new(args)
    return cmd_task_new(args)


def cmd_task_list(args) -> int:
    from buildrix.hub_client import HubClient
    from buildrix import domains as dm
    rows = HubClient().list_tasks(domain=args.domain, search=args.search)
    if not rows:
        print("No tasks on the hub yet.")
        return 0
    print()
    for r in rows:
        slug = r.get("slug") or r.get("id", "")
        dom = dm.short(r.get("domain", ""))
        base = r.get("baseline_pass_rate")
        base_txt = f"{float(base) * 100:4.0f}%" if base not in (None, "") else "   -"
        print(f"  {dom:<9}  {base_txt}  {slug:<34}  {r.get('name', '')}")
    print(f"\n  {len(rows)} task(s)\n")
    return 0


def cmd_task_get(args) -> int:
    from buildrix.hub_client import HubClient
    from buildrix.report import Report
    client = HubClient()
    row = client.task_review(args.slug)
    dest = Path(args.dir) / args.slug
    print(f"  {row.get('name') or args.slug}")
    print(f"  The public half downloads to {dest} once the hub exposes /tasks/"
          f"{args.slug}/bundle.")
    print("  Until then, browse it on the site.")
    return 0


def cmd_domains_v2(args) -> int:
    from buildrix import domains as dm
    kind = "task" if getattr(args, "task_only", False) else "skill"
    print()
    print(f"  Valid domains for a {kind}:\n")
    print(dm.listing(kind))
    if kind == "skill":
        print("\n  `general` is for cross-cutting tooling. A task cannot use it.")
    print()
    return 0


def cmd_bench(args) -> int:
    verb = getattr(args, "verb", "run")
    print()
    print("  buildrix bench is not in this release yet.")
    print()
    print("  When it lands, one command runs both arms of a paired run on your")
    print("  machine and uploads only the graded bundle:")
    print()
    print("    buildrix bench run --suite core-v1 --model claude-opus-5 \\")
    print("                       --harness claude-code --trials 3 \\")
    print("                       --skills weather-data-extraction,ahu-fault-rules")
    print()
    print("  Arm A runs with no skills on disk, arm B with the ones you name.")
    print("  Same model, same harness, same budget, fresh container per trial,")
    print("  order randomised. A run without its control arm is refused on upload.")
    print()
    print(f"  ({verb}: waiting on the first golden tasks - build some and it becomes useful.)")
    print()
    return 0


# ==========================================================================
#  dispatch tables
# ==========================================================================

SKILL_VERBS = {
    "new": cmd_skill_new,
    "check": cmd_skill_check,
    "submit": cmd_skill_submit,
    "status": cmd_skill_status,
    "install": cmd_install,
    "pull": cmd_pull,
    "update": cmd_update,
    "dev": cmd_dev,
    "remove": cmd_uninstall,
    "list": cmd_list,
    "search": cmd_search,
    "browse": cmd_browse,
    "delete": cmd_delete,
}

TASK_VERBS = {
    "new": cmd_task_new,
    "check": cmd_task_check,
    "submit": cmd_task_submit,
    "status": cmd_task_status,
    "get": cmd_task_get,
    "list": cmd_task_list,
}

BENCH_VERBS = {v: cmd_bench for v in ("run", "submit", "status", "list")}

AUTH_VERBS = {
    "login": cmd_login,
    "logout": cmd_logout,
    "whoami": cmd_whoami,
    "register": cmd_register,
}

TOP_LEVEL = {
    "domains": cmd_domains_v2,
    "info": cmd_info,
    "env": cmd_env,
    "config": cmd_config,
}

LEGACY = {
    "login":     ("buildrix auth login", cmd_login),
    "logout":    ("buildrix auth logout", cmd_logout),
    "whoami":    ("buildrix auth whoami", cmd_whoami),
    "register":  ("buildrix auth register", cmd_register),
    "new":       ("buildrix skill new / buildrix task new", cmd_new_legacy),
    "install":   ("buildrix skill install", cmd_install),
    "pull":      ("buildrix skill pull", cmd_pull),
    "update":    ("buildrix skill update", cmd_update),
    "dev":       ("buildrix skill dev", cmd_dev),
    "uninstall": ("buildrix skill remove", cmd_uninstall),
    "list":      ("buildrix skill list", cmd_list),
    "push":      ("buildrix skill submit", cmd_push),
    "delete":    ("buildrix skill delete", cmd_delete),
    "search":    ("buildrix skill search", cmd_search),
    "browse":    ("buildrix skill browse", cmd_browse),
}


if __name__ == "__main__":
    main()
