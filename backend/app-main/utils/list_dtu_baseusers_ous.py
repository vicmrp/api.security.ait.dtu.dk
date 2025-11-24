"""List sub-organisational units under win.dtu.dk/DTUBaseUsers.*"""

from django.conf import settings

from active_directory.services import execute_active_directory_query
from myview.models import ADGroupAssociation


def _first_level_children(base_canonical: str) -> list[str]:
    base_canonical = base_canonical.rstrip('/')
    base_dn = ADGroupAssociation._canonical_to_distinguished_name(base_canonical)
    if not base_dn:
        raise ValueError(f"Unable to convert {base_canonical} to a distinguished name")

    entries = execute_active_directory_query(
        base_dn=base_dn,
        search_filter='(objectClass=organizationalUnit)',
        search_attributes=['distinguishedName'],
    ) or []

    children: set[str] = set()
    for entry in entries:
        dn_values = entry.get('distinguishedName') or entry.get('distinguishedname')
        if isinstance(dn_values, list):
            dn = dn_values[0]
        else:
            dn = dn_values
        if not dn:
            continue

        canonical = ADGroupAssociation._dn_to_canonical(dn)
        if not canonical:
            continue
        canonical = canonical.rstrip('/')
        if not canonical.startswith(base_canonical):
            continue

        relative = canonical[len(base_canonical):].lstrip('/')
        if not relative:
            continue

        first_segment = relative.split('/', 1)[0]
        children.add(f"{base_canonical}/{first_segment}")

    return sorted(children)


def list_dtu_baseusers_ous(base_prefixes=None) -> list[tuple[str, list[str]]]:
    if base_prefixes is None:
        base_prefixes = getattr(
            settings,
            'AD_OU_LIMITER_BASES',
            ('win.dtu.dk/DTUBaseUsers',),
        )

    results: list[tuple[str, list[str]]] = []
    for base in base_prefixes:
        try:
            children = _first_level_children(base)
        except Exception as exc:  # noqa: BLE001
            results.append((base, [f"Error: {exc}"]))
            continue
        results.append((base, children))
    return results


def run():  # pragma: no cover - invoked from admin utility runner
    for base, children in list_dtu_baseusers_ous():
        print(f"Base OU: {base}")
        if not children:
            print("  (no child OUs discovered)")
        else:
            for child in children:
                print(f"  - {child}")
            print(f"  Total: {len(children)}")
        print()


if __name__ == "__main__":
    run()
