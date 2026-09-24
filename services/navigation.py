from database.repositories import Repository

async def folder_path(repo: Repository, folder_id: int) -> str:
    names = []
    row = await repo.get_folder(folder_id)
    while row:
        if row["parent_id"] is None:
            break
        names.append(row["name"])
        row = await repo.get_folder(row["parent_id"])
    return " / ".join(reversed(names))
