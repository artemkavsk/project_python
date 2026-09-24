from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers import context
from handlers.states import Form
from handlers.views import edit_or_answer, show_folder
from keyboards.inline import note_kb, confirm_kb

router = Router()
repo = context.repo

def setup(repository):
    global repo
    repo = repository

@router.callback_query(F.data.startswith("note_new:"))
async def note_new(c: CallbackQuery, state: FSMContext):
    fid = int(c.data.split(":")[1])
    await state.update_data(folder_id=fid)
    await state.set_state(Form.note_text)
    await c.message.answer("Текст записки:")
    await c.answer()

@router.message(Form.note_text)
async def note_text(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    if not text: return await m.answer("Записка не может быть пустой.")
    d = await state.get_data()
    await repo.create_note(d["folder_id"], m.from_user.id, text)
    await state.clear()
    await show_folder(m, d["folder_id"], m.from_user.id)

@router.callback_query(F.data.startswith("note:"))
async def note_open(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    if not await repo.note_owned(nid, c.from_user.id): return await c.answer("Нет доступа", show_alert=True)
    n = await repo.get_note(nid)
    await edit_or_answer(c, f"📝 {n['created_at']}\n\n{n['text']}", note_kb(nid, n["folder_id"]))

@router.callback_query(F.data.startswith("note_deleteask:"))
async def note_deleteask(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    n = await repo.get_note(nid)
    await edit_or_answer(c, "Удалить записку?", confirm_kb(f"note_delete:{nid}", f"note:{nid}"))

@router.callback_query(F.data.startswith("note_delete:"))
async def note_delete(c: CallbackQuery):
    nid = int(c.data.split(":")[1])
    n = await repo.get_note(nid)
    await repo.delete_note(nid)
    await show_folder(c, n["folder_id"], c.from_user.id)
