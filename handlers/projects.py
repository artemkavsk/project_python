from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers import context
from handlers.states import Form
from handlers.views import edit_or_answer, show_projects, show_folder
from keyboards.inline import confirm_kb
from services.weight import fmt_mass

router = Router()
repo = context.repo

def setup(repository):
    global repo
    repo = repository

@router.callback_query(F.data == "projects")
async def projects(c: CallbackQuery):
    await show_projects(c, c.from_user.id)

@router.callback_query(F.data == "project_new")
async def project_new(c: CallbackQuery, state: FSMContext):
    await state.set_state(Form.project_name)
    await c.message.answer("Название нового проекта:")
    await c.answer()

@router.message(Form.project_name)
async def project_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if not name:
        return await m.answer("Введите непустое название.")
    pid = await repo.create_project(m.from_user.id, name)
    await state.clear()
    root = await repo.root_folder(pid)
    await show_folder(m, root["id"], m.from_user.id)

@router.callback_query(F.data.startswith("project:"))
async def project_open(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await repo.get_project(pid, c.from_user.id)
    if not p:
        return await c.answer("Нет доступа", show_alert=True)
    root = await repo.root_folder(pid)
    await show_folder(c, root["id"], c.from_user.id)

@router.callback_query(F.data.startswith("project_settings:"))
async def project_settings(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await repo.get_project(pid, c.from_user.id)
    if not p:
        return await c.answer("Нет доступа", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ Задать лимит массы", callback_data=f"project_limit:{pid}")],
        [InlineKeyboardButton(text="🗑 Удалить проект", callback_data=f"project_deleteask:{pid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"project:{pid}")]
    ])
    await edit_or_answer(c, f"⚙️ {p['name']}\nЛимит: {fmt_mass(p['weight_limit_g'])}", kb)

@router.callback_query(F.data.startswith("project_limit:"))
async def project_limit(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    await state.update_data(project_id=pid)
    await state.set_state(Form.project_limit)
    await c.message.answer("Введите лимит в граммах или 0, чтобы убрать:")
    await c.answer()

@router.message(Form.project_limit)
async def project_limit_value(m: Message, state: FSMContext):
    try:
        x = float((m.text or "").replace(",", "."))
        if x < 0: raise ValueError
    except ValueError:
        return await m.answer("Нужно неотрицательное число.")
    data = await state.get_data()
    pid = data["project_id"]
    await repo.set_project_limit(pid, m.from_user.id, None if x == 0 else x)
    await state.clear()
    root = await repo.root_folder(pid)
    await show_folder(m, root["id"], m.from_user.id)

@router.callback_query(F.data.startswith("project_deleteask:"))
async def project_deleteask(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await edit_or_answer(c, "Удалить проект целиком?", confirm_kb(f"project_delete:{pid}", f"project:{pid}"))

@router.callback_query(F.data.startswith("project_delete:"))
async def project_delete(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await repo.delete_project(pid, c.from_user.id)
    await show_projects(c, c.from_user.id)
