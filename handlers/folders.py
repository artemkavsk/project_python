from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers import context
from handlers.states import Form
from handlers.views import edit_or_answer, show_folder
from keyboards.inline import confirm_kb

router = Router()
repo = context.repo

def setup(repository):
    global repo
    repo = repository

@router.callback_query(F.data.startswith("folder:"))
async def folder_open(c: CallbackQuery):
    await show_folder(c, int(c.data.split(":")[1]), c.from_user.id)

@router.callback_query(F.data.startswith("folder_new:"))
async def folder_new(c: CallbackQuery, state: FSMContext):
    parent = int(c.data.split(":")[1])
    f = await repo.get_folder(parent)
    await state.update_data(parent_id=parent, project_id=f["project_id"])
    await state.set_state(Form.folder_name)
    await c.message.answer("Название папки:")
    await c.answer()

@router.message(Form.folder_name)
async def folder_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if not name: return await m.answer("Введите название.")
    d = await state.get_data()
    await repo.create_folder(d["project_id"], d["parent_id"], name)
    await state.clear()
    await show_folder(m, d["parent_id"], m.from_user.id)

@router.callback_query(F.data.startswith("folder_settings:"))
async def folder_settings(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    f = await repo.get_folder(fid)
    await edit_or_answer(c, f"⚙️ Папка «{f['name']}»", confirm_kb(f"folder_delete:{fid}", f"folder:{fid}"))

@router.callback_query(F.data.startswith("folder_delete:"))
async def folder_delete(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    f = await repo.get_folder(fid)
    parent = f["parent_id"]
    await repo.delete_folder(fid)
    await show_folder(c, parent, c.from_user.id)
