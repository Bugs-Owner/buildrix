"""
Buildrix CLI — the agentic harness for building science skills.

Usage:
    buildrix login                      Authenticate with the hub
    buildrix logout                     Clear stored credentials
    buildrix whoami                     Show current user info
    buildrix config hub <url>           Set the hub URL

    buildrix new skill <name>           Scaffold a new skill from template
    buildrix new testcase <name>        Scaffold a new test case from template

    buildrix install <name> [name2 ...] Download & install skill(s) from the hub
    buildrix pull <name> [name2 ...]    Download skill archive(s) without installing
    buildrix pull --all                 Download every skill on the hub
    buildrix pull --mine                Download every skill you authored
    buildrix update [name ...] [--all]  Re-fetch installed skill(s) at latest version
    buildrix dev <skill-dir>            Install a local skill for development
    buildrix uninstall <name> [...]     Remove installed skill(s)
    buildrix list                       List installed skills

    buildrix push <dir> [dir2 ...]      Push skill(s) or test case(s) to the hub
    buildrix push <parent-dir> --all    Auto-discover and push all skills in a dir
    buildrix push <dir> --update        Update existing skill(s) you own
    buildrix delete <name> [...] --yes  Delete skill(s) you own from the hub
    buildrix search <query>             Search the hub for skills
    buildrix browse                     List all skills on the hub
    buildrix browse --domain <domain>   List skills filtered by domain
    buildrix domains                    Show valid domain categories

    buildrix info                       Show hub stats and connection info

    buildrix env info                   Show installed toolchain components
    buildrix env setup <skill-dir>      Provision toolchain for a skill
    buildrix env clean                  Remove cached downloads
"""

import argparse
import getpass
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="buildrix",
        description="Buildrix — open skill framework for building science AI agents",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── register ──
    p_reg = sub.add_parser("register", help="Create a new Buildrix Hub account")
    p_reg.add_argument("--hub", default="", help="Hub URL")

    # ── login ──
    p_login = sub.add_parser("login", help="Authenticate with the Buildrix Hub")
    p_login.add_argument("--hub", default="", help="Hub URL (e.g., https://buildrix.onrender.com)")
    p_login.add_argument("--register", action="store_true", help="Create a new account")

    # ── logout ──
    sub.add_parser("logout", help="Clear stored credentials")

    # ── whoami ──
    sub.add_parser("whoami", help="Show current user info")

    # ── config ──
    p_config = sub.add_parser("config", help="Configure buildrix settings")
    p_config.add_argument("key", choices=["hub"], help="Setting to configure")
    p_config.add_argument("value", help="Value to set")

    # ── new ──
    p_new = sub.add_parser("new", help="Create a new skill or test case from template")
    p_new.add_argument("type", choices=["skill", "testcase"], help="What to create")
    p_new.add_argument("name", help="Name (e.g., heat-wave-identification)")
    p_new.add_argument("--dir", default=".", help="Parent directory")

    # ── install ──
    p_install = sub.add_parser("install", help="Install skill(s) from the hub")
    p_install.add_argument("names", nargs="+", help="Skill name(s) to install")

    # ── pull ──  (fetch from hub, no install / no Claude Code linking)
    p_pull = sub.add_parser(
        "pull",
        help="Download skill archive(s) from the hub without installing them",
    )
    p_pull.add_argument("names", nargs="*", help="Skill name(s) to download")
    p_pull.add_argument("--all", action="store_true", dest="pull_all",
                        help="Download every skill on the hub")
    p_pull.add_argument("--mine", action="store_true",
                        help="Download every skill you authored (requires login)")
    p_pull.add_argument("--domain", default="",
                        help="With --all/--mine, restrict to a single domain")
    p_pull.add_argument("--dir", default=".", help="Destination directory (default: cwd)")
    p_pull.add_argument("--extract", action="store_true",
                        help="Extract the archive instead of keeping it zipped")

    # ── update ──  (re-fetch installed skill(s) at latest hub version)
    p_update = sub.add_parser(
        "update",
        help="Update locally installed skill(s) to the latest version from the hub",
    )
    p_update.add_argument("names", nargs="*", help="Skill name(s) to update (omit for all)")
    p_update.add_argument("--all", action="store_true", dest="update_all",
                          help="Update every installed skill")

    # ── dev ──
    p_dev = sub.add_parser("dev", help="Install a local skill for development/testing")
    p_dev.add_argument("path", help="Path to skill directory")

    # ── uninstall ──
    p_uninstall = sub.add_parser("uninstall", help="Remove installed skill(s)")
    p_uninstall.add_argument("names", nargs="+", help="Skill name(s) to remove")

    # ── list ──
    sub.add_parser("list", help="List installed skills")

    # ── push ──
    p_push = sub.add_parser("push", help="Push skill(s) or test case(s) to the hub")
    p_push.add_argument("paths", nargs="+", help="Path(s) to skill or test case directories")
    p_push.add_argument("--update", action="store_true",
                        help="Update existing skill(s) you own (instead of creating new)")
    p_push.add_argument("--all", action="store_true", dest="push_all",
                        help="Auto-discover and push all skills under a parent directory")

    # ── delete ──
    p_delete = sub.add_parser("delete", help="Delete skill(s) you own from the hub")
    p_delete.add_argument("names", nargs="+", help="Skill name(s) to delete")
    p_delete.add_argument("--yes", "-y", action="store_true",
                          help="Skip confirmation prompt")

    # ── search ──
    p_search = sub.add_parser("search", help="Search the hub for skills")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--domain", default="", help="Filter by domain")

    # ── browse ──
    p_browse = sub.add_parser("browse", help="List all skills on the hub")
    p_browse.add_argument("--domain", default="", help="Filter by domain")
    p_browse.add_argument(
        "--sort", default="newest",
        choices=["newest", "oldest", "most_liked", "most_downloaded", "most_saved"],
        help="Sort order (default: newest)",
    )

    # ── domains ──
    sub.add_parser("domains", help="List valid domain categories")

    # ── info ──
    sub.add_parser("info", help="Show hub stats and connection info")

    # ── env ──
    p_env = sub.add_parser("env", help="Manage the toolchain environment")
    env_sub = p_env.add_subparsers(dest="env_command", help="Env subcommands")
    env_sub.add_parser("info", help="Show installed toolchain components")
    p_env_setup = env_sub.add_parser("setup", help="Provision toolchain for a skill")
    p_env_setup.add_argument("path", help="Path to skill directory or installed skill name")
    env_sub.add_parser("clean", help="Remove cached downloads")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        commands = {
            "register": cmd_register,
            "login": cmd_login,
            "logout": cmd_logout,
            "whoami": cmd_whoami,
            "config": cmd_config,
            "new": cmd_new,
            "install": cmd_install,
            "pull": cmd_pull,
            "update": cmd_update,
            "dev": cmd_dev,
            "uninstall": cmd_uninstall,
            "list": cmd_list,
            "push": cmd_push,
            "delete": cmd_delete,
            "search": cmd_search,
            "browse": cmd_browse,
            "domains": cmd_domains,
            "info": cmd_info,
            "env": cmd_env,
        }
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nAborted.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════

def cmd_register(args):
    from buildrix.config import set_auth, set_hub_url
    from buildrix.hub_client import HubClient

    if args.hub:
        set_hub_url(args.hub)

    client = HubClient(hub_url=args.hub)
    print("🏗️  Buildrix — Create Account")
    print()
    email = input("  Email: ").strip()
    display_name = input("  Display name: ").strip()
    affiliation = input("  Affiliation (university/company): ").strip()
    password = getpass.getpass("  Password: ")
    password2 = getpass.getpass("  Confirm password: ")
    if password != password2:
        print("❌ Passwords don't match")
        return

    data = client.register(email, password, display_name, affiliation)
    set_auth(
        token=data["access_token"],
        user={"id": data["user_id"], "name": data["display_name"], "email": email},
        hub_url=args.hub,
    )
    print(f"\n✅ Welcome to Buildrix, {data['display_name']}!")
    print(f"  You're now logged in and ready to push skills.")

def cmd_login(args):
    from buildrix.config import set_auth, set_hub_url
    from buildrix.hub_client import HubClient

    if args.hub:
        set_hub_url(args.hub)

    client = HubClient(hub_url=args.hub)
    print("🏗️  Buildrix Hub Login")
    print()

    email = input("  Email: ").strip()

    if args.register:
        display_name = input("  Display name: ").strip()
        affiliation = input("  Affiliation (university/company): ").strip()
        password = getpass.getpass("  Password: ")
        password2 = getpass.getpass("  Confirm password: ")
        if password != password2:
            print("❌ Passwords don't match")
            return
        data = client.register(email, password, display_name, affiliation)
        print(f"\n✅ Account created! Welcome, {data['display_name']}")
    else:
        password = getpass.getpass("  Password: ")
        data = client.login(email, password)
        print(f"\n✅ Logged in as {data['display_name']}")

    set_auth(
        token=data["access_token"],
        user={"id": data["user_id"], "name": data["display_name"], "email": email},
        hub_url=args.hub,
    )


def cmd_logout(args):
    from buildrix.config import clear_auth
    clear_auth()
    print("✅ Logged out")


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
        print(f"✅ Hub URL set to {args.value}")


def cmd_new(args):
    from buildrix.scaffold import scaffold_skill, scaffold_testcase
    if args.type == "skill":
        scaffold_skill(args.name, args.dir)
    elif args.type == "testcase":
        scaffold_testcase(args.name, args.dir)


def cmd_install(args):
    from buildrix.skill_manager import install_skill

    ok, fail = [], []
    for name in args.names:
        try:
            install_skill(name)
            ok.append(name)
            print(f"✅ '{name}' installed")
        except Exception as e:
            fail.append(name)
            print(f"❌ '{name}' failed: {e}")

    if len(args.names) > 1:
        print(f"\n  Summary: {len(ok)} installed, {len(fail)} failed")


def cmd_pull(args):
    """
    Download skill archive(s) from the hub to disk WITHOUT installing them.

    Use this when you want to inspect or vendor a skill rather than make it
    visible to Claude Code. For the "install + link to ~/.claude/skills"
    behavior, use `buildrix install` instead.

    Targets can be given three ways:
      • explicit names:  buildrix pull skill-a skill-b
      • everything:      buildrix pull --all
      • your own skills: buildrix pull --mine
    """
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    client = HubClient()
    dest_root = Path(args.dir).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    # ── Resolve the list of skills to download ──
    if args.pull_all or args.mine:
        if args.names:
            print("⚠️  Ignoring explicit names because --all/--mine was given.")

        # Pull a generous page so we get everything, not just the default 50.
        skills = client.list_skills(domain=args.domain, sort_by="newest")

        if args.mine:
            user = get_user()
            if not user:
                print("❌ Not logged in. Run: buildrix login")
                return
            my_name = user.get("name", "")
            skills = [s for s in skills if s.get("author_name") == my_name]

        if not skills:
            scope = "you authored" if args.mine else "on the hub"
            extra = f" in domain '{args.domain}'" if args.domain else ""
            print(f"  No skills {scope}{extra}.")
            return

        targets = [(s["name"], s["id"]) for s in skills]
        print(f"  Downloading {len(targets)} skill(s) → {dest_root}\n")
    else:
        if not args.names:
            print("❌ Nothing to pull. Pass skill name(s), or use --all / --mine.")
            return
        # Resolve names → ids up front so errors are clear.
        targets = []
        for name in args.names:
            skill = client.get_skill_by_name(name)
            if not skill:
                print(f"❌ '{name}' not found on the hub.")
                continue
            targets.append((skill["name"], skill["id"]))
        if not targets:
            return

    # ── Download loop (shared by all modes) ──
    ok, fail = 0, 0
    for name, skill_id in targets:
        try:
            if args.extract:
                target = dest_root / name
                client.download_skill(skill_id, target)
                print(f"✅ '{name}' downloaded and extracted → {target}")
            else:
                target = dest_root / f"{name}.zip"
                client.download_skill_archive(skill_id, target)
                print(f"✅ '{name}' downloaded → {target}")
            ok += 1
        except Exception as e:
            print(f"❌ '{name}' failed: {e}")
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
                print(f"⚠️  '{n}' is not installed locally — skipping. "
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
            print(f"✅ '{name}' updated to latest version")
            ok += 1
        except Exception as e:
            print(f"❌ '{name}' failed: {e}")
            fail += 1

    if len(names) > 1:
        print(f"\n  Summary: {ok} updated, {fail} failed")


def cmd_dev(args):
    from buildrix.skill_manager import install_local
    install_local(Path(args.path))
    print(f"\n✅ Dev skill installed and linked to Claude Code")


def cmd_uninstall(args):
    from buildrix.skill_manager import uninstall_skill

    for name in args.names:
        try:
            uninstall_skill(name)
            print(f"✅ '{name}' removed")
        except Exception as e:
            print(f"❌ '{name}' failed: {e}")


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
        print(f"  • {s['name']}", end="")
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
            print(f"⚠️  Skipping (not a directory): {path}")
            continue

        if push_all:
            # Auto-discover: find all sub-dirs containing SKILL.md or TESTCASE.yaml
            found = sorted(
                sub for sub in path.iterdir()
                if sub.is_dir()
                and ((sub / "SKILL.md").exists() or (sub / "TESTCASE.yaml").exists())
            )
            if not found:
                print(f"⚠️  No skills or test cases found under {path}/")
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
                print(f"⚠️  '{path}' has no SKILL.md itself, but contains {len(children)} skill(s).")
                print(f"  Did you mean:  buildrix push {path} --all")
            else:
                print(f"❌ No SKILL.md or TESTCASE.yaml found in {path}")
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
            print(f"  ⚠️  Domain '{skill_domain}' is not a recognized hub category.")
            print(f"    Valid: {', '.join(VALID_DOMAINS)}")

        existing = client.get_skill_by_name(skill_name)

        if existing and update:
            if existing["author_id"] != user.get("id", ""):
                print(f"  ❌ '{skill_name}' belongs to another contributor.")
                return False
            result = client.update_skill(existing["id"], path)
            print(f"  ✅ '{result['name']}' updated (v{result['version']}, {result['status']})")
            return True

        elif existing and not update:
            if existing["author_id"] == user.get("id", ""):
                print(f"  ⚠️  '{skill_name}' already exists. Use --update to overwrite.")
            else:
                print(f"  ❌ '{skill_name}' already exists (owned by someone else).")
            return False

        else:
            result = client.push_skill(path)
            print(f"  ✅ '{result['name']}' submitted ({result['status']})")
            return True

    elif (path / "TESTCASE.yaml").exists():
        result = client.push_testcase(path)
        print(f"  ✅ Test case '{result['name']}' submitted ({result['status']})")
        return True

    else:
        print(f"  ❌ No SKILL.md or TESTCASE.yaml in {path}")
        return False


def cmd_push(args):
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    if not get_token():
        print("❌ Not logged in. Run: buildrix login")
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
            print(f"  ❌ {d.name}: {e}")
            fail += 1

    if len(dirs) > 1:
        print(f"\n  Summary: {ok} pushed, {fail} failed")



def cmd_delete(args):
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    if not get_token():
        print("❌ Not logged in. Run: buildrix login")
        return

    client = HubClient()
    user = get_user()

    # Resolve all skills first so we can show a summary before confirming
    to_delete = []
    for name in args.names:
        skill = client.get_skill_by_name(name)
        if not skill:
            print(f"❌ '{name}' not found on the hub.")
            continue
        if skill["author_id"] != user.get("id", ""):
            print(f"❌ '{name}' belongs to another contributor. Skipping.")
            continue
        to_delete.append(skill)

    if not to_delete:
        return

    # Show what will be deleted
    print()
    for s in to_delete:
        print(f"  • {s['name']} (v{s['version']}, {s['download_count']} downloads)")
    print()

    # Confirm unless --yes flag
    if not args.yes:
        noun = "skill" if len(to_delete) == 1 else f"{len(to_delete)} skills"
        confirm = input(f"  ⚠️  Permanently delete {noun} and all likes/comments? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Cancelled.")
            return

    ok = 0
    for s in to_delete:
        try:
            client.delete_skill(s["id"])
            print(f"  ✅ '{s['name']}' deleted")
            ok += 1
        except Exception as e:
            print(f"  ❌ '{s['name']}' failed: {e}")

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
        print(f"  • {s['name']} [{s['domain']}] — {s['status']}")
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
        status_icon = "✅" if s["status"] == "accepted" else "📝"
        print(f"  {status_icon} {s['name']} [{s['domain']}]")
        print(f"    {s['description'][:80]}")
        print(f"    by {s['author_name']} | v{s['version']} | ♡ {s.get('like_count', 0)} | ↓ {s['download_count']}")
        print()


def cmd_domains(args):
    from buildrix.config import VALID_DOMAINS
    print("\n  Valid domain categories:\n")
    for d in VALID_DOMAINS:
        print(f"  • {d}")
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
    print("  🏗️  Buildrix Info")
    print(f"  ─────────────────────────")
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
        print(f"\n  ⚠️  Could not reach hub at {hub_url}")
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
        print("  🔧 Buildrix Toolchain")
        print(f"  ─────────────────────────")
        print(f"  Location:    {TOOLCHAIN_DIR}")
        print(f"  Cache:       {DOWNLOAD_CACHE}")
        print(f"  Weather:     {info.weather_dir}")
        print()
        if info.versions:
            print("  Installed:")
            for tool, ver in info.versions.items():
                print(f"    • {tool} {ver}")
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
            print(f"❌ Skill not found: {args.path}")
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
            print(f"  ✅ Cleared download cache ({size / 1024 / 1024:.0f} MB freed)")
        else:
            print("  Cache is already empty.")


if __name__ == "__main__":
    main()