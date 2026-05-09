"""
Buildrix CLI — the agentic harness for building science skills.

Usage:
    buildrix login                      Authenticate with the hub
    buildrix logout                     Clear stored credentials
    buildrix whoami                     Show current user info
    buildrix config hub <url>           Set the hub URL

    buildrix new skill <name>           Scaffold a new skill from template
    buildrix new testcase <name>        Scaffold a new test case from template

    buildrix install <skill-name>       Download & install a skill from the hub
    buildrix dev <skill-dir>            Install a local skill for development
    buildrix uninstall <skill-name>     Remove an installed skill
    buildrix list                       List installed skills

    buildrix push <directory>           Push a skill or test case to the hub
    buildrix search <query>             Search the hub for skills

    buildrix info                       Show hub stats and connection info
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

    # ── login ──
    p_login = sub.add_parser("login", help="Authenticate with the Buildrix Hub")
    p_login.add_argument("--hub", default="", help="Hub URL (e.g., https://buildrix.onrender.com)")
    p_login.add_argument("--register", action="store_true", help="Create a new account")

    # ── register ──
    p_reg = sub.add_parser("register", help="Create a new Buildrix Hub account")
    p_reg.add_argument("--hub", default="", help="Hub URL")

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
    p_install = sub.add_parser("install", help="Install a skill from the hub")
    p_install.add_argument("name", help="Skill name to install")

    # ── dev ──
    p_dev = sub.add_parser("dev", help="Install a local skill for development/testing")
    p_dev.add_argument("path", help="Path to skill directory")

    # ── uninstall ──
    p_uninstall = sub.add_parser("uninstall", help="Remove an installed skill")
    p_uninstall.add_argument("name", help="Skill name to remove")

    # ── list ──
    sub.add_parser("list", help="List installed skills")

    # ── push ──
    p_push = sub.add_parser("push", help="Push a skill or test case to the hub")
    p_push.add_argument("path", help="Path to skill or test case directory")

    # ── search ──
    p_search = sub.add_parser("search", help="Search the hub for skills")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--domain", default="", help="Filter by domain")

    # ── info ──
    sub.add_parser("info", help="Show hub stats and connection info")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        commands = {
            "login": cmd_login,
            "register": cmd_register,
            "logout": cmd_logout,
            "whoami": cmd_whoami,
            "config": cmd_config,
            "new": cmd_new,
            "install": cmd_install,
            "dev": cmd_dev,
            "uninstall": cmd_uninstall,
            "list": cmd_list,
            "push": cmd_push,
            "search": cmd_search,
            "info": cmd_info,
        }
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nAborted.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════

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
    install_skill(args.name)
    print(f"\n✅ Skill '{args.name}' installed and linked to Claude Code")


def cmd_dev(args):
    from buildrix.skill_manager import install_local
    install_local(Path(args.path))
    print(f"\n✅ Dev skill installed and linked to Claude Code")


def cmd_uninstall(args):
    from buildrix.skill_manager import uninstall_skill
    uninstall_skill(args.name)
    print(f"✅ Skill '{args.name}' removed")


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


def cmd_push(args):
    from buildrix.config import get_token, get_user
    from buildrix.hub_client import HubClient

    if not get_token():
        print("❌ Not logged in. Run: buildrix login")
        return

    path = Path(args.path)
    if not path.is_dir():
        print(f"❌ Not a directory: {path}")
        return

    client = HubClient()
    user = get_user()

    if (path / "SKILL.md").exists():
        print(f"  Pushing skill from {path}...")
        result = client.push_skill(path)
        print(f"✅ Skill '{result['name']}' submitted!")
        print(f"  ID:     {result['id']}")
        print(f"  Status: {result['status']}")
        print(f"  Author: {user.get('name', '')} ({user.get('email', '')})")
        print(f"\n  View on hub or wait for LLM review.")

    elif (path / "TESTCASE.yaml").exists():
        print(f"  Pushing test case from {path}...")
        result = client.push_testcase(path)
        print(f"✅ Test case '{result['name']}' submitted!")
        print(f"  ID:     {result['id']}")
        print(f"  Status: {result['status']}")
        print(f"  Author: {user.get('name', '')} ({user.get('email', '')})")
        print(f"\n  An LLM reviewer will evaluate your submission.")

    else:
        print(f"❌ No SKILL.md or TESTCASE.yaml found in {path}")


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


if __name__ == "__main__":
    main()
