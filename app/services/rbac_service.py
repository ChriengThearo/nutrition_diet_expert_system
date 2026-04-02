from typing import Dict
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import NoSuchTableError
from extensions import db
from app.models.permission import PermissionTable
from app.models.role import RoleTable


def _get_role(name: str) -> RoleTable | None:
    return db.session.scalar(
        db.select(RoleTable).filter(func.lower(RoleTable.name) == name.lower())
    )


def get_permissions() -> Dict[str, PermissionTable]:
    return {
        perm.code: perm for perm in db.session.scalars(db.select(PermissionTable)).all()
    }


def _normalize_permission_code(code: str) -> str:
    normalized = (code or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("_", ".")
    normalized = normalized.replace("user.dash.", "user.dashboard.")
    parts = [("read" if part == "view" else part) for part in normalized.split(".")]
    normalized = ".".join(parts)
    return normalized


def _build_aliases(code: str) -> set[str]:
    aliases = set()
    if not code:
        return aliases
    aliases.add(code)
    if "." in code:
        aliases.add(code.replace(".", "_"))
    if "_" in code:
        aliases.add(code.replace("_", "."))
    if "user.dashboard." in code:
        short = code.replace("user.dashboard.", "user.dash.")
        aliases.add(short)
        aliases.add(short.replace(".", "_"))
    if "user.dash." in code:
        long_form = code.replace("user.dash.", "user.dashboard.")
        aliases.add(long_form)
        aliases.add(long_form.replace(".", "_"))
    if ".read" in code:
        aliases.add(code.replace(".read", ".view"))
    if ".view" in code:
        aliases.add(code.replace(".view", ".read"))
    for action in ("read", "create", "update", "delete"):
        short = f"user.{action}"
        long_form = f"user.dashboard.{action}"
        if code == short:
            aliases.add(long_form)
            aliases.add(long_form.replace(".", "_"))
        if code == long_form:
            aliases.add(short)
            aliases.add(short.replace(".", "_"))
    return aliases


def ensure_permission_aliases_column() -> None:
    inspector = inspect(db.engine)
    try:
        columns = {col["name"] for col in inspector.get_columns("tbl_permissions")}
    except NoSuchTableError:
        return
    if "aliases" in columns:
        return
    db.session.execute(text("ALTER TABLE tbl_permissions ADD COLUMN aliases TEXT"))
    db.session.commit()


def migrate_permission_codes() -> bool:
    ensure_permission_aliases_column()
    inspector = inspect(db.engine)
    if not inspector.has_table("tbl_permissions"):
        return False
    perms = db.session.scalars(db.select(PermissionTable)).all()
    perms = list(perms)
    if not perms:
        return False

    by_code = {perm.code: perm for perm in perms}
    changed = False

    for perm in perms:
        old_code = perm.code
        new_code = _normalize_permission_code(perm.code)
        alias_set = _build_aliases(old_code)
        if new_code and new_code != old_code:
            alias_set.add(old_code)
            alias_set |= _build_aliases(new_code)
            target = by_code.get(new_code)
            if target and target is not perm:
                for role in perm.roles:
                    if role not in target.roles:
                        target.roles.append(role)
                merged = set(target.get_aliases())
                merged |= alias_set
                target.set_aliases(sorted(merged))
                db.session.delete(perm)
                changed = True
                continue
            perm.code = new_code
            by_code[new_code] = perm
            changed = True

        current_aliases = set(perm.get_aliases())
        alias_set |= current_aliases
        alias_set.discard(perm.code)
        if current_aliases != alias_set:
            perm.set_aliases(sorted(alias_set))
            changed = True

    if changed:
        db.session.commit()
    return changed


def sync_rbac() -> None:
    migrate_permission_codes()
    permissions = get_permissions()
    if not permissions:
        return

    role = _get_role("admin")
    if not role:
        role = RoleTable(name="admin", description="Administrator")
        db.session.add(role)
        db.session.flush()

    existing = {perm.code for perm in role.permissions}
    changed = False
    for perm in permissions.values():
        if perm.code in existing:
            continue
        role.permissions.append(perm)
        changed = True
    if changed:
        db.session.commit()
