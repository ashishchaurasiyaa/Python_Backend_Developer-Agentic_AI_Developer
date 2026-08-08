"""
Redis Practical 18 — ACL & Security
Run: python 18_acl_security.py [legacy|create|permissions|inspect|cleanup|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine
  (default connection below assumes NO requirepass/ACL is set on `default` —
   i.e. a fresh local dev container. ACL demos create their OWN restricted
   user via this admin/default connection, then open a SECOND connection
   authenticating as that restricted user to prove permissions are enforced.)
"""

import sys
import redis
from redis.exceptions import ResponseError

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── The restricted user we create/use/inspect/delete across sections ───
ACL_USER = "report_svc"
ACL_PASSWORD = "report_pw_2024"
KEY_PATTERN = "report:*"       # this user may ONLY touch keys under report:


# ════════════════════════════════════════════
# SECTION 0: LEGACY AUTH — requirepass / default user recap
# ════════════════════════════════════════════
def demo_legacy_auth():
    print("\n" + "=" * 50)
    print("  SECTION 0: LEGACY AUTH (requirepass) vs ACL")
    print("=" * 50)

    requirepass = r.config_get("requirepass").get("requirepass", "")
    print(f"📊 Current requirepass on this instance: "
          f"{'(set)' if requirepass else '(empty — no password!)'}")

    whoami = r.acl_whoami()
    print(f"📊 This connection is authenticated as ACL user: '{whoami}'")

    default_user = r.acl_getuser("default")
    print(f"📊 default user flags: {default_user.get('flags')}")
    if "on" in default_user.get("flags", []) and requirepass == "":
        print("⚠️  default user is ON with no password — on an internet-")
        print("   exposed box this is THE classic Redis ransomware vector")
        print("   (FLUSHALL + ransom note). Local dev container hai, so")
        print("   it's fine here, but never ship this to a reachable host.")

    print("\n   requirepass is just sugar for setting default user's")
    print("   password under the hood in Redis 6+ — it is NOT a separate")
    print("   mechanism from ACLs, it's ACLs with exactly one user.")


# ════════════════════════════════════════════
# SECTION 1: CREATE — ACL SETUSER with least-privilege scoping
# ════════════════════════════════════════════
def ensure_restricted_user():
    """Idempotent: safe to call from any section independently."""
    r.acl_setuser(
        ACL_USER,
        enabled=True,
        passwords=[f"+{ACL_PASSWORD}"],
        keys=[f"~{KEY_PATTERN}"],
        categories=["+@read", "-@dangerous"],   # read-only, no admin/danger cmds
    )


def demo_create():
    print("\n" + "=" * 50)
    print("  SECTION 1: ACL SETUSER — READ-ONLY SCOPED USER")
    print("=" * 50)

    ensure_restricted_user()
    print(f"✅ Created/updated user '{ACL_USER}':")
    print(f"   ~{KEY_PATTERN}   +@read -@dangerous")
    print("   Equivalent CLI:")
    print(f"   ACL SETUSER {ACL_USER} on >{ACL_PASSWORD} "
          f"~{KEY_PATTERN} +@read -@dangerous")

    # ─── Seed a key inside AND outside this user's allowed pattern ───
    r.set("report:daily_signups", "142")
    r.set("orders:secret_total", "99999")   # this one report_svc must NOT touch
    print("📊 Seeded 'report:daily_signups' (in-scope) and "
          "'orders:secret_total' (out-of-scope)")


# ════════════════════════════════════════════
# SECTION 2: PERMISSIONS — connect AS the restricted user, prove enforcement
# ════════════════════════════════════════════
def demo_permissions():
    print("\n" + "=" * 50)
    print("  SECTION 2: PERMISSION ENFORCEMENT")
    print("=" * 50)

    ensure_restricted_user()
    r.set("report:daily_signups", "142")

    scoped = redis.Redis(
        host='localhost', port=6379, decode_responses=True,
        username=ACL_USER, password=ACL_PASSWORD,
    )

    # ─── ALLOWED: read a key inside ~report:* with a +@read command ───
    value = scoped.get("report:daily_signups")
    print(f"✅ ALLOWED — GET report:daily_signups (in ~{KEY_PATTERN}, "
          f"@read) → '{value}'")

    # ─── DISALLOWED (wrong key pattern): key outside ~report:* ───
    try:
        scoped.get("orders:secret_total")
        print("⚠️ UNEXPECTED — read outside allowed key pattern succeeded!")
    except ResponseError as e:
        print(f"✅ BLOCKED (key pattern) — GET orders:secret_total → {e}")

    # ─── DISALLOWED (wrong command category): write cmd, user is read-only ───
    try:
        scoped.set("report:daily_signups", "999")
        print("⚠️ UNEXPECTED — write with read-only user succeeded!")
    except ResponseError as e:
        print(f"✅ BLOCKED (command category) — SET report:daily_signups → {e}")

    # ─── DISALLOWED (dangerous category, even though it'd be in-scope-ish) ───
    try:
        scoped.execute_command("FLUSHDB")
        print("⚠️ UNEXPECTED — FLUSHDB with restricted user succeeded!")
    except ResponseError as e:
        print(f"✅ BLOCKED (@dangerous) — FLUSHDB → {e}")

    print("\n   NoPermissionError is a subclass of ResponseError in redis-py")
    print("   — catch ResponseError if you want a single except clause that")
    print("   covers both key-pattern AND command-category denials.")

    scoped.close()


# ════════════════════════════════════════════
# SECTION 3: INSPECT — ACL LIST / ACL GETUSER / ACL CAT
# ════════════════════════════════════════════
def demo_inspect():
    print("\n" + "=" * 50)
    print("  SECTION 3: INSPECTING ACLs")
    print("=" * 50)

    ensure_restricted_user()

    print(f"📊 ACL WHOAMI (this script's own connection): {r.acl_whoami()}")

    print("\n📊 ACL LIST (all users, SETUSER-reproducible rule strings):")
    for rule in r.acl_list():
        print(f"   {rule}")

    detail = r.acl_getuser(ACL_USER)
    print(f"\n📊 ACL GETUSER {ACL_USER}:")
    print(f"   flags:    {detail.get('flags')}")
    print(f"   keys:     {detail.get('keys')}")
    print(f"   commands: {detail.get('commands')}")

    read_cmds = r.acl_cat("read")
    print(f"\n📊 ACL CAT read — sample commands in @read category: "
          f"{read_cmds[:8]}... ({len(read_cmds)} total)")

    dangerous_cmds = r.acl_cat("dangerous")
    print(f"📊 ACL CAT dangerous — sample: {dangerous_cmds[:8]}... "
          f"({len(dangerous_cmds)} total)")

    print("\n   GOTCHA: none of this survives a restart unless `aclfile` is")
    print("   configured AND `ACL SAVE` was called — this demo intentionally")
    print("   does NOT persist, so cleanup below just deletes in-memory state.")


# ════════════════════════════════════════════
# SECTION 4: CLEANUP — ACL DELUSER + key cleanup
# ════════════════════════════════════════════
def demo_cleanup():
    print("\n" + "=" * 50)
    print("  SECTION 4: CLEANUP")
    print("=" * 50)

    deleted = r.acl_deluser(ACL_USER)
    print(f"✅ ACL DELUSER {ACL_USER} → removed: {bool(deleted)}")

    remaining = r.acl_getuser(ACL_USER)
    print(f"📊 ACL GETUSER {ACL_USER} after delete: {remaining} "
          "(None = confirmed gone)")

    r.delete("report:daily_signups", "orders:secret_total")
    print("✅ Demo keys deleted — instance back to clean state")


if __name__ == "__main__":
    sections = {
        "legacy": demo_legacy_auth,
        "create": demo_create,
        "permissions": demo_permissions,
        "inspect": demo_inspect,
        "cleanup": demo_cleanup,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 18_acl_security.py [{'|'.join(sections)}|all]")
