from database.repositories import Repository

def fmt_mass(value):
    if value is None:
        return "—"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))} г"
    return f"{value:.2f}".rstrip("0").rstrip(".") + " г"

async def folder_mass(repo: Repository, folder_id: int) -> float:
    folders, files, components, _ = await repo.list_folder_content(folder_id)
    total = 0.0
    for f in files:
        if f["current_mass"] is not None:
            total += float(f["current_mass"]) * int(f["quantity"])
    for c in components:
        if c["mass_g"] is not None:
            total += float(c["mass_g"]) * int(c["quantity"])
    for sub in folders:
        total += await folder_mass(repo, sub["id"])
    return total
