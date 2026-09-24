from __future__ import annotations
from typing import Optional
from .db import Database

class Repository:
    def __init__(self, database: Database):
        self.database = database

    async def _fetchone(self, sql, params=()):
        db = await self.database.connect()
        try:
            cur = await db.execute(sql, params)
            return await cur.fetchone()
        finally:
            await db.close()

    async def _fetchall(self, sql, params=()):
        db = await self.database.connect()
        try:
            cur = await db.execute(sql, params)
            return await cur.fetchall()
        finally:
            await db.close()

    async def _execute(self, sql, params=()):
        db = await self.database.connect()
        try:
            cur = await db.execute(sql, params)
            await db.commit()
            return cur.lastrowid
        finally:
            await db.close()

    async def ensure_user(self, telegram_id: int) -> int:
        await self._execute("INSERT OR IGNORE INTO users(telegram_id) VALUES(?)", (telegram_id,))
        row = await self._fetchone("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
        return row["id"]

    async def get_user_id(self, telegram_id: int) -> Optional[int]:
        row = await self._fetchone("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
        return row["id"] if row else None

    async def create_project(self, telegram_id: int, name: str, description=None, weight_limit_g=None) -> int:
        uid = await self.ensure_user(telegram_id)
        pid = await self._execute(
            "INSERT INTO projects(owner_id,name,description,weight_limit_g) VALUES(?,?,?,?)",
            (uid, name, description, weight_limit_g),
        )
        await self._execute("INSERT INTO folders(project_id,parent_id,name) VALUES(?,NULL,?)", (pid, "__ROOT__"))
        return pid

    async def list_projects(self, telegram_id: int):
        uid = await self.ensure_user(telegram_id)
        return await self._fetchall("SELECT * FROM projects WHERE owner_id=? ORDER BY id DESC", (uid,))

    async def get_project(self, project_id: int, telegram_id: int):
        uid = await self.ensure_user(telegram_id)
        return await self._fetchone("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id, uid))

    async def rename_project(self, project_id: int, telegram_id: int, name: str):
        uid = await self.ensure_user(telegram_id)
        await self._execute("UPDATE projects SET name=? WHERE id=? AND owner_id=?", (name, project_id, uid))

    async def set_project_limit(self, project_id: int, telegram_id: int, limit_g):
        uid = await self.ensure_user(telegram_id)
        await self._execute("UPDATE projects SET weight_limit_g=? WHERE id=? AND owner_id=?", (limit_g, project_id, uid))

    async def delete_project(self, project_id: int, telegram_id: int):
        uid = await self.ensure_user(telegram_id)
        await self._execute("DELETE FROM projects WHERE id=? AND owner_id=?", (project_id, uid))

    async def root_folder(self, project_id: int):
        return await self._fetchone("SELECT * FROM folders WHERE project_id=? AND parent_id IS NULL", (project_id,))

    async def get_folder(self, folder_id: int):
        return await self._fetchone("SELECT * FROM folders WHERE id=?", (folder_id,))

    async def folder_owned(self, folder_id: int, telegram_id: int) -> bool:
        uid = await self.ensure_user(telegram_id)
        row = await self._fetchone(
            """SELECT f.id FROM folders f JOIN projects p ON p.id=f.project_id
               WHERE f.id=? AND p.owner_id=?""", (folder_id, uid)
        )
        return bool(row)

    async def create_folder(self, project_id: int, parent_id: int, name: str) -> int:
        return await self._execute(
            "INSERT INTO folders(project_id,parent_id,name) VALUES(?,?,?)",
            (project_id, parent_id, name)
        )

    async def rename_folder(self, folder_id: int, name: str):
        await self._execute("UPDATE folders SET name=? WHERE id=?", (name, folder_id))

    async def delete_folder(self, folder_id: int):
        row = await self.get_folder(folder_id)
        if row and row["parent_id"] is not None:
            await self._execute("DELETE FROM folders WHERE id=?", (folder_id,))

    async def list_folder_content(self, folder_id: int):
        folders = await self._fetchall("SELECT * FROM folders WHERE parent_id=? ORDER BY name COLLATE NOCASE", (folder_id,))
        fls = await self._fetchall(
            """SELECT f.*, 
                      (SELECT version_number FROM file_versions v WHERE v.file_id=f.id ORDER BY version_number DESC LIMIT 1) current_version,
                      (SELECT mass_g FROM file_versions v WHERE v.file_id=f.id ORDER BY version_number DESC LIMIT 1) current_mass
               FROM files f WHERE f.folder_id=? ORDER BY f.name COLLATE NOCASE""", (folder_id,)
        )
        comps = await self._fetchall("SELECT * FROM components WHERE folder_id=? ORDER BY name COLLATE NOCASE", (folder_id,))
        notes = await self._fetchall("SELECT * FROM notes WHERE folder_id=? ORDER BY id DESC", (folder_id,))
        return folders, fls, comps, notes

    async def create_file(self, folder_id: int, name: str, quantity=1) -> int:
        return await self._execute("INSERT INTO files(folder_id,name,quantity) VALUES(?,?,?)", (folder_id, name, quantity))

    async def find_file_by_name(self, folder_id: int, name: str):
        return await self._fetchone("SELECT * FROM files WHERE folder_id=? AND name=?", (folder_id, name))

    async def get_file(self, file_id: int):
        return await self._fetchone("SELECT * FROM files WHERE id=?", (file_id,))

    async def file_owned(self, file_id: int, telegram_id: int) -> bool:
        uid = await self.ensure_user(telegram_id)
        row = await self._fetchone(
            """SELECT f.id FROM files f JOIN folders d ON d.id=f.folder_id
               JOIN projects p ON p.id=d.project_id WHERE f.id=? AND p.owner_id=?""",
            (file_id, uid)
        )
        return bool(row)

    async def add_file_version(self, file_id: int, tg_file_id: str, unique_id: str, size: int | None, mass_g=None, comment=None):
        row = await self._fetchone("SELECT COALESCE(MAX(version_number),0)+1 n FROM file_versions WHERE file_id=?", (file_id,))
        n = row["n"]
        vid = await self._execute(
            """INSERT INTO file_versions(file_id,version_number,telegram_file_id,telegram_file_unique_id,size,mass_g,comment)
               VALUES(?,?,?,?,?,?,?)""",
            (file_id, n, tg_file_id, unique_id, size, mass_g, comment)
        )
        return vid, n

    async def list_versions(self, file_id: int):
        return await self._fetchall("SELECT * FROM file_versions WHERE file_id=? ORDER BY version_number DESC", (file_id,))

    async def get_version(self, version_id: int):
        return await self._fetchone("SELECT * FROM file_versions WHERE id=?", (version_id,))

    async def latest_version(self, file_id: int):
        return await self._fetchone("SELECT * FROM file_versions WHERE file_id=? ORDER BY version_number DESC LIMIT 1", (file_id,))

    async def set_file_quantity(self, file_id: int, quantity: int):
        await self._execute("UPDATE files SET quantity=? WHERE id=?", (quantity, file_id))

    async def set_version_mass(self, version_id: int, mass_g):
        await self._execute("UPDATE file_versions SET mass_g=? WHERE id=?", (mass_g, version_id))

    async def set_version_comment(self, version_id: int, comment: str | None):
        await self._execute("UPDATE file_versions SET comment=? WHERE id=?", (comment, version_id))

    async def delete_file(self, file_id: int):
        await self._execute("DELETE FROM files WHERE id=?", (file_id,))

    async def create_component(self, folder_id: int, name: str, mass_g=None, quantity=1) -> int:
        return await self._execute(
            "INSERT INTO components(folder_id,name,mass_g,quantity) VALUES(?,?,?,?)",
            (folder_id, name, mass_g, quantity)
        )

    async def get_component(self, component_id: int):
        return await self._fetchone("SELECT * FROM components WHERE id=?", (component_id,))

    async def component_owned(self, component_id: int, telegram_id: int) -> bool:
        uid = await self.ensure_user(telegram_id)
        row = await self._fetchone(
            """SELECT c.id FROM components c JOIN folders d ON d.id=c.folder_id
               JOIN projects p ON p.id=d.project_id WHERE c.id=? AND p.owner_id=?""",
            (component_id, uid)
        )
        return bool(row)

    async def update_component(self, component_id: int, *, name=None, mass_marker=False, mass_g=None, quantity=None):
        if name is not None:
            await self._execute("UPDATE components SET name=? WHERE id=?", (name, component_id))
        if mass_marker:
            await self._execute("UPDATE components SET mass_g=? WHERE id=?", (mass_g, component_id))
        if quantity is not None:
            await self._execute("UPDATE components SET quantity=? WHERE id=?", (quantity, component_id))

    async def delete_component(self, component_id: int):
        await self._execute("DELETE FROM components WHERE id=?", (component_id,))

    async def create_note(self, folder_id: int, telegram_id: int, text: str) -> int:
        uid = await self.ensure_user(telegram_id)
        return await self._execute("INSERT INTO notes(folder_id,author_id,text) VALUES(?,?,?)", (folder_id, uid, text))

    async def get_note(self, note_id: int):
        return await self._fetchone("SELECT * FROM notes WHERE id=?", (note_id,))

    async def note_owned(self, note_id: int, telegram_id: int) -> bool:
        uid = await self.ensure_user(telegram_id)
        row = await self._fetchone(
            """SELECT n.id FROM notes n JOIN folders d ON d.id=n.folder_id
               JOIN projects p ON p.id=d.project_id WHERE n.id=? AND p.owner_id=?""",
            (note_id, uid)
        )
        return bool(row)

    async def delete_note(self, note_id: int):
        await self._execute("DELETE FROM notes WHERE id=?", (note_id,))
