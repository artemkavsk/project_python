from aiogram.types import CallbackQuery
from keyboards.inline import projects_kb, folder_kb
from services.weight import folder_mass, fmt_mass
from services.navigation import folder_path
from handlers import context

async def edit_or_answer(event, text, markup=None):
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=markup)
        except Exception:
            await event.message.answer(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)

async def show_projects(event, user_id):
    ps = await context.repo.list_projects(user_id)
    await edit_or_answer(event, "Инженерное хранилище\n\nВыберите проект:", projects_kb(ps))

async def show_folder(event, folder_id, user_id):
    if not await context.repo.folder_owned(folder_id, user_id):
        return await edit_or_answer(event, "Нет доступа.")
    folder = await context.repo.get_folder(folder_id)
    project = await context.repo.get_project(folder["project_id"], user_id)
    folders, files, comps, notes = await context.repo.list_folder_content(folder_id)
    mass = await folder_mass(repo, folder_id)
    path = await folder_path(repo, folder_id)
    title = f"📦 {project['name']}"
    if path:
        title += f"\n› {path}"
    title += f"\n\n⚖️ {fmt_mass(mass)}"
    if folder["parent_id"] is None and project["weight_limit_g"] is not None:
        limit = float(project["weight_limit_g"])
        title += f" / {fmt_mass(limit)}\nЗапас: {fmt_mass(limit-mass)}"
    title += "\n\nВыберите элемент:"
    await edit_or_answer(event, title, folder_kb(folder, folders, files, comps, notes, folder["parent_id"] is None))
